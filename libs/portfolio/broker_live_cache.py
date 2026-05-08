"""Server-side cache + rate-limit-aware live read-through for Trading 212.

Trading 212's official rate limits (per account, regardless of API key or IP):
  - GET /equity/positions: 1 request / 1 second
  - GET /equity/account/summary: not officially published; we treat
    conservatively as 1 request / 5 seconds
  - GET /equity/history/orders: 6 requests / 1 minute (= 1 per 10s)

Many concurrent dashboard tabs can issue near-simultaneous polls, so this
cache:

  1. Serves a recent fetched value without re-hitting T212 (TTL window)
  2. Coalesces concurrent in-flight requests so only ONE outbound HTTP
     fetch happens per (key) per fetch window
  3. Tracks T212 `x-ratelimit-*` response headers when present and refuses
     to call upstream when remaining is zero
  4. Falls back to the last successful payload on 429 / RateLimitExceeded

This module never writes to the database. It never calls any T212 write
endpoint. It never touches order_intent / order_draft / submit objects.
It is purely a readonly observability layer for the live Dashboard view.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from libs.core.exceptions import RateLimitExceeded


# ---- Cache TTL defaults (must respect spec minimums) ----

POSITIONS_TTL_SECONDS_DEFAULT = 2.0      # spec floor: 1.1s
SUMMARY_TTL_SECONDS_DEFAULT = 10.0       # spec floor: 5.5s
ORDERS_TTL_SECONDS_DEFAULT = 60.0        # spec floor: 60s

# Floor values — never accept a TTL below these (defends against accidental
# misconfiguration that would breach T212's 1 req/sec positions limit)
POSITIONS_TTL_FLOOR_SECONDS = 1.1
SUMMARY_TTL_FLOOR_SECONDS = 5.5
ORDERS_TTL_FLOOR_SECONDS = 60.0


@dataclass
class LiveFetchResult:
    """Result returned to API callers; safe to JSON-serialize."""

    payload: Any
    cache_status: str           # "fresh" | "cached" | "rate_limited" | "error"
    fetched_at: float           # epoch seconds when payload was obtained from T212
    served_at: float            # epoch seconds when this result was assembled
    provider_latency_ms: int | None  # None when served from cache
    rate_limit: dict[str, str] | None  # captured x-ratelimit-* headers or None
    stale_reason: str | None    # human-readable why payload is not fresh, or None


@dataclass
class _CacheEntry:
    payload: Any
    fetched_at: float
    rate_limit: dict[str, str] | None = None


@dataclass
class BrokerLiveCache:
    """Per-key in-memory cache + single-flight + rate-limit gate.

    Keyed by (broker, account_id, endpoint_name) tuples — for the current
    single-user platform that is effectively just (endpoint_name).
    """

    positions_ttl_seconds: float = POSITIONS_TTL_SECONDS_DEFAULT
    summary_ttl_seconds: float = SUMMARY_TTL_SECONDS_DEFAULT
    orders_ttl_seconds: float = ORDERS_TTL_SECONDS_DEFAULT
    _cache: dict[tuple[str, str, str], _CacheEntry] = field(default_factory=dict)
    _inflight: dict[tuple[str, str, str], asyncio.Task] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        # Defend against misconfiguration that could breach T212 rate limits
        if self.positions_ttl_seconds < POSITIONS_TTL_FLOOR_SECONDS:
            self.positions_ttl_seconds = POSITIONS_TTL_FLOOR_SECONDS
        if self.summary_ttl_seconds < SUMMARY_TTL_FLOOR_SECONDS:
            self.summary_ttl_seconds = SUMMARY_TTL_FLOOR_SECONDS
        if self.orders_ttl_seconds < ORDERS_TTL_FLOOR_SECONDS:
            self.orders_ttl_seconds = ORDERS_TTL_FLOOR_SECONDS

    def _ttl_for(self, endpoint: str) -> float:
        if endpoint == "positions":
            return self.positions_ttl_seconds
        if endpoint == "summary":
            return self.summary_ttl_seconds
        if endpoint == "orders":
            return self.orders_ttl_seconds
        return self.positions_ttl_seconds

    def _ratelimit_blocks(self, entry: _CacheEntry | None) -> bool:
        """Return True if a known x-ratelimit-remaining=0 forbids upstream call.

        Respects reset window if provided. Conservative: any parse error
        treats the limit as not-blocking and lets the normal flow proceed.
        """
        if entry is None or entry.rate_limit is None:
            return False
        remaining = entry.rate_limit.get("x-ratelimit-remaining")
        reset = entry.rate_limit.get("x-ratelimit-reset")
        try:
            if remaining is not None and int(remaining) <= 0:
                if reset is not None:
                    try:
                        if float(reset) > time.time():
                            return True
                    except (TypeError, ValueError):
                        return True
                else:
                    return True
        except (TypeError, ValueError):
            return False
        return False

    async def get_or_fetch(
        self,
        broker: str,
        account_id: str,
        endpoint: str,
        fetcher: Callable[[], Awaitable[tuple[Any, dict[str, str] | None]]],
    ) -> LiveFetchResult:
        """Return cached value if within TTL; else single-flight fetch.

        `fetcher` is an async callable returning `(payload, rate_limit_headers)`
        where the second item is a dict of any captured `x-ratelimit-*`
        response headers (or None). The fetcher is responsible for the actual
        HTTP call to T212. The cache:

          - returns cache_status="cached" if entry age < TTL
          - returns cache_status="fresh" after a successful upstream fetch
          - returns cache_status="rate_limited" if upstream rejects with 429
            OR if remaining=0 forbids calling, and falls back to the last
            cached payload (else cache_status="error")
        """
        key = (broker, account_id, endpoint)
        now = time.time()
        ttl = self._ttl_for(endpoint)

        # 1. Serve from cache when within TTL
        entry = self._cache.get(key)
        if entry is not None and (now - entry.fetched_at) < ttl:
            return LiveFetchResult(
                payload=entry.payload,
                cache_status="cached",
                fetched_at=entry.fetched_at,
                served_at=now,
                provider_latency_ms=None,
                rate_limit=dict(entry.rate_limit) if entry.rate_limit else None,
                stale_reason=None,
            )

        # 2. Honor rate-limit-remaining=0 if upstream said so
        if self._ratelimit_blocks(entry):
            return LiveFetchResult(
                payload=entry.payload if entry else None,
                cache_status="rate_limited",
                fetched_at=entry.fetched_at if entry else now,
                served_at=now,
                provider_latency_ms=None,
                rate_limit=dict(entry.rate_limit) if entry and entry.rate_limit else None,
                stale_reason="upstream rate limit window not yet reset",
            )

        # 3. Coalesce concurrent fetches via single-flight
        async with self._lock:
            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = asyncio.create_task(self._fetch_and_store(key, fetcher))
                self._inflight[key] = inflight

        # 4. Wait for the in-flight fetch and translate into a result
        try:
            payload, rate_limit, latency_ms = await inflight
            return LiveFetchResult(
                payload=payload,
                cache_status="fresh",
                fetched_at=time.time(),
                served_at=time.time(),
                provider_latency_ms=latency_ms,
                rate_limit=dict(rate_limit) if rate_limit else None,
                stale_reason=None,
            )
        except RateLimitExceeded:
            entry = self._cache.get(key)
            return LiveFetchResult(
                payload=entry.payload if entry else None,
                cache_status="rate_limited",
                fetched_at=entry.fetched_at if entry else time.time(),
                served_at=time.time(),
                provider_latency_ms=None,
                rate_limit=dict(entry.rate_limit) if entry and entry.rate_limit else None,
                stale_reason="upstream returned 429",
            )
        except Exception as exc:
            entry = self._cache.get(key)
            return LiveFetchResult(
                payload=entry.payload if entry else None,
                cache_status="cached" if entry else "error",
                fetched_at=entry.fetched_at if entry else time.time(),
                served_at=time.time(),
                provider_latency_ms=None,
                rate_limit=dict(entry.rate_limit) if entry and entry.rate_limit else None,
                stale_reason=f"upstream error: {type(exc).__name__}",
            )

    async def _fetch_and_store(
        self,
        key: tuple[str, str, str],
        fetcher: Callable[[], Awaitable[tuple[Any, dict[str, str] | None]]],
    ) -> tuple[Any, dict[str, str] | None, int]:
        start = time.time()
        try:
            payload, rate_limit = await fetcher()
        finally:
            self._inflight.pop(key, None)
        latency_ms = int((time.time() - start) * 1000)
        self._cache[key] = _CacheEntry(
            payload=payload,
            fetched_at=time.time(),
            rate_limit=dict(rate_limit) if rate_limit else None,
        )
        return payload, rate_limit, latency_ms


# Module-level singleton — one cache per running API process.
_default_cache: BrokerLiveCache | None = None


def get_default_cache() -> BrokerLiveCache:
    global _default_cache
    if _default_cache is None:
        _default_cache = BrokerLiveCache()
    return _default_cache


def reset_default_cache_for_tests() -> None:
    """Test-only helper to drop the module singleton between tests."""
    global _default_cache
    _default_cache = None
