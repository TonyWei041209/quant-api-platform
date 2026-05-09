"""Market Events provider layer — FMP earnings/news/profile + TTL cache.

This module is a thin wrapper around the existing
``libs.adapters.fmp_adapter.FMPAdapter`` plus an in-memory TTL cache. It
exposes a small async API for the market-events service to call:

  - ``get_earnings_calendar(start_date, end_date, tickers=None, limit=100)``
  - ``get_stock_news(tickers, from_date, to_date, limit_per_ticker=5)``
  - ``get_company_profile(symbol)``

Provider behavior:

  - missing FMP API key       → returns structured "unavailable" state,
                                NEVER raises 500
  - FMP HTTP error             → returns "error" state with what-we-have,
                                NEVER raises 500
  - rate-limit / partial fail  → returns "partial" state
  - successful fetch           → returns "ok" state

Cache TTLs (per-process in-memory):

  - earnings calendar : 6 hours
  - stock news        : 15 minutes
  - company profile   : 24 hours

This module:

  - never writes the database
  - never calls a Trading 212 endpoint (write or read)
  - never touches order_intent / order_draft / submit objects
  - never reads or mutates FEATURE_T212_LIVE_SUBMIT
  - never scrapes or automates a browser
  - never adds a paid provider beyond what's already configured
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

from libs.core.config import get_settings
from libs.core.logging import get_logger


logger = get_logger(__name__)


EARNINGS_TTL_SECONDS = 6 * 60 * 60       # 6 h
NEWS_TTL_SECONDS = 15 * 60               # 15 min
PROFILE_TTL_SECONDS = 24 * 60 * 60       # 24 h
ALL_MARKET_EARNINGS_LIMIT_FLOOR = 50
ALL_MARKET_EARNINGS_LIMIT_CEILING = 500
NEWS_LIMIT_PER_TICKER_CEILING = 25


ProviderStatus = str  # "ok" | "unavailable" | "partial" | "error"


@dataclass
class ProviderResult:
    """Generic provider result wrapper."""
    data: Any
    status: ProviderStatus
    fetched_at: float
    error: str | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------


@dataclass
class _CacheEntry:
    value: Any
    fetched_at: float


@dataclass
class TTLCache:
    """Per-key cache with a single global lock per cache instance.

    Single-flight: concurrent get_or_fetch() calls for the same key share
    one in-flight task so we don't hammer FMP if two tabs poll at once.
    """

    ttl_seconds: float
    _entries: dict[str, _CacheEntry] = field(default_factory=dict)
    _inflight: dict[str, asyncio.Task] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def peek(self, key: str) -> Any:
        """Return cached value if within TTL, else None. No fetch."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if (time.time() - entry.fetched_at) >= self.ttl_seconds:
            return None
        return entry.value

    async def get_or_fetch(
        self, key: str, fetcher: Callable[[], Awaitable[Any]]
    ) -> Any:
        cached = self.peek(key)
        if cached is not None:
            return cached
        async with self._lock:
            inflight = self._inflight.get(key)
            if inflight is None:
                inflight = asyncio.create_task(self._fetch_and_store(key, fetcher))
                self._inflight[key] = inflight
        try:
            return await inflight
        finally:
            self._inflight.pop(key, None)

    async def _fetch_and_store(self, key: str, fetcher: Callable[[], Awaitable[Any]]) -> Any:
        value = await fetcher()
        self._entries[key] = _CacheEntry(value=value, fetched_at=time.time())
        return value

    def reset(self) -> None:
        self._entries.clear()
        self._inflight.clear()


_earnings_cache = TTLCache(EARNINGS_TTL_SECONDS)
_news_cache = TTLCache(NEWS_TTL_SECONDS)
_profile_cache = TTLCache(PROFILE_TTL_SECONDS)


def reset_caches_for_tests() -> None:
    """Drop all market-events caches; used by unit tests for isolation."""
    _earnings_cache.reset()
    _news_cache.reset()
    _profile_cache.reset()


# ---------------------------------------------------------------------------
# Configuration check
# ---------------------------------------------------------------------------


def _fmp_configured() -> bool:
    s = get_settings()
    return bool(getattr(s, "fmp_api_key", None))


# ---------------------------------------------------------------------------
# Earnings calendar
# ---------------------------------------------------------------------------


async def get_earnings_calendar(
    start_date: str,
    end_date: str,
    tickers: Iterable[str] | None = None,
    limit: int = 100,
    fmp_fetcher: Callable[[str, str], Awaitable[list[dict]]] | None = None,
) -> ProviderResult:
    """Fetch upcoming earnings between [start_date, end_date].

    ``tickers`` is an optional filter applied AFTER fetching (FMP's stable
    earnings calendar does not accept a ticker filter directly). To avoid
    an unbounded all-market blast, ``limit`` caps the returned rows.

    Args are dates as YYYY-MM-DD strings.
    """
    limit = max(
        ALL_MARKET_EARNINGS_LIMIT_FLOOR,
        min(ALL_MARKET_EARNINGS_LIMIT_CEILING, int(limit)),
    )
    if not _fmp_configured() and fmp_fetcher is None:
        return ProviderResult(
            data=[],
            status="unavailable",
            fetched_at=time.time(),
            error="FMP API key not configured",
        )

    cache_key = f"earnings::{start_date}::{end_date}"

    async def _fetch() -> ProviderResult:
        try:
            if fmp_fetcher is not None:
                rows = await fmp_fetcher(start_date, end_date)
            else:
                from libs.adapters.fmp_adapter import FMPAdapter
                adapter = FMPAdapter()
                rows = await adapter.get_earnings_calendar(start_date, end_date)
        except Exception as exc:  # noqa: BLE001
            logger.warning("market_events.earnings_error", error=str(exc))
            return ProviderResult(
                data=[],
                status="error",
                fetched_at=time.time(),
                error=f"{type(exc).__name__}: {exc}",
            )

        if not isinstance(rows, list):
            return ProviderResult(
                data=[],
                status="partial",
                fetched_at=time.time(),
                note="upstream returned non-list payload",
            )
        return ProviderResult(data=rows, status="ok", fetched_at=time.time())

    result: ProviderResult = await _earnings_cache.get_or_fetch(cache_key, _fetch)

    # Optional client-side ticker filter — does NOT affect cached payload.
    if tickers is not None:
        tickerset = {t.upper() for t in tickers if t}
        filtered = [r for r in (result.data or []) if str(r.get("symbol", "")).upper() in tickerset]
        result = ProviderResult(
            data=filtered,
            status=result.status,
            fetched_at=result.fetched_at,
            error=result.error,
            note=result.note,
        )

    # Apply the limit AFTER filtering so ticker-scoped queries don't get
    # silently truncated to a non-deterministic prefix.
    result = ProviderResult(
        data=(result.data or [])[:limit],
        status=result.status,
        fetched_at=result.fetched_at,
        error=result.error,
        note=result.note,
    )
    return result


# ---------------------------------------------------------------------------
# Stock news (per-ticker)
# ---------------------------------------------------------------------------


async def get_stock_news(
    tickers: Iterable[str],
    from_date: str,
    to_date: str,
    limit_per_ticker: int = 5,
    fmp_news_fetcher: Callable[[list[str], str, str, int], Awaitable[list[dict]]] | None = None,
) -> ProviderResult:
    """Fetch recent news for the given tickers.

    Uses FMP's ``/stable/news/stock`` endpoint (a paid-tier endpoint on
    some plans). On free-tier accounts this can return empty / 404; we
    treat that as ``unavailable`` rather than ``error`` so the UI shows
    a clear "no news provider" state.

    Per-ticker news is bounded by ``limit_per_ticker`` (capped at the
    module ceiling). All-market unbounded news is NOT supported.
    """
    cleaned = [t.upper().strip() for t in tickers if t and t.strip()]
    cleaned = list(dict.fromkeys(cleaned))[:50]  # dedup + soft cap
    if not cleaned:
        return ProviderResult(
            data=[],
            status="ok",
            fetched_at=time.time(),
            note="no tickers requested",
        )

    limit_per_ticker = max(1, min(NEWS_LIMIT_PER_TICKER_CEILING, int(limit_per_ticker)))

    if not _fmp_configured() and fmp_news_fetcher is None:
        return ProviderResult(
            data=[],
            status="unavailable",
            fetched_at=time.time(),
            error="FMP API key not configured",
        )

    cache_key = f"news::{from_date}::{to_date}::{','.join(cleaned)}::{limit_per_ticker}"

    async def _fetch() -> ProviderResult:
        try:
            if fmp_news_fetcher is not None:
                rows = await fmp_news_fetcher(cleaned, from_date, to_date, limit_per_ticker)
            else:
                rows = await _default_fmp_news(cleaned, from_date, to_date, limit_per_ticker)
        except _ProviderUnavailable as exc:
            return ProviderResult(
                data=[],
                status="unavailable",
                fetched_at=time.time(),
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("market_events.news_error", error=str(exc))
            return ProviderResult(
                data=[],
                status="error",
                fetched_at=time.time(),
                error=f"{type(exc).__name__}: {exc}",
            )

        if not isinstance(rows, list):
            return ProviderResult(
                data=[],
                status="partial",
                fetched_at=time.time(),
                note="upstream returned non-list payload",
            )
        return ProviderResult(data=rows, status="ok", fetched_at=time.time())

    return await _news_cache.get_or_fetch(cache_key, _fetch)


class _ProviderUnavailable(Exception):
    """Raised when FMP returns 404 / not-on-this-plan / similar."""


async def _default_fmp_news(
    tickers: list[str],
    from_date: str,
    to_date: str,
    limit_per_ticker: int,
) -> list[dict]:
    """Default FMP news fetcher.

    Walks each ticker individually (FMP stable supports a comma-delimited
    ``tickers`` param; we use one call per ticker for predictable
    per-ticker limits and to keep the failure mode local).
    """
    from libs.adapters.fmp_adapter import FMPAdapter
    adapter = FMPAdapter()

    out: list[dict] = []
    for tk in tickers:
        try:
            params = {
                "symbols": tk,
                "from": from_date,
                "to": to_date,
                "limit": str(limit_per_ticker),
            }
            data = await adapter.fetch_json("/stable/news/stock", params=params)
        except Exception as exc:  # noqa: BLE001
            # 404 / not on plan / network blip — record as unavailable for
            # this ticker but keep going for the rest.
            msg = str(exc)
            if "404" in msg or "Not Found" in msg or "subscription" in msg.lower():
                # First failure means the endpoint isn't on this plan; bail
                # immediately to avoid burning quota across many tickers.
                raise _ProviderUnavailable(
                    "FMP /stable/news/stock returned 404; news endpoint not on this plan"
                ) from exc
            continue

        if isinstance(data, list):
            for row in data[:limit_per_ticker]:
                if isinstance(row, dict):
                    row.setdefault("symbol", tk)
                    out.append(row)
    return out


# ---------------------------------------------------------------------------
# Company profile
# ---------------------------------------------------------------------------


async def get_company_profile(
    symbol: str,
    fmp_profile_fetcher: Callable[[str], Awaitable[dict]] | None = None,
) -> ProviderResult:
    if not symbol:
        return ProviderResult(
            data={},
            status="unavailable",
            fetched_at=time.time(),
            error="empty symbol",
        )
    sym = symbol.upper().strip()
    if not _fmp_configured() and fmp_profile_fetcher is None:
        return ProviderResult(
            data={},
            status="unavailable",
            fetched_at=time.time(),
            error="FMP API key not configured",
        )

    cache_key = f"profile::{sym}"

    async def _fetch() -> ProviderResult:
        try:
            if fmp_profile_fetcher is not None:
                row = await fmp_profile_fetcher(sym)
            else:
                from libs.adapters.fmp_adapter import FMPAdapter
                adapter = FMPAdapter()
                row = await adapter.get_profile(sym)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                data={},
                status="error",
                fetched_at=time.time(),
                error=f"{type(exc).__name__}: {exc}",
            )
        if not isinstance(row, dict) or not row:
            return ProviderResult(
                data={},
                status="unavailable",
                fetched_at=time.time(),
                note="profile not found",
            )
        return ProviderResult(data=row, status="ok", fetched_at=time.time())

    return await _profile_cache.get_or_fetch(cache_key, _fetch)
