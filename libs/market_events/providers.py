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
from datetime import date, timedelta
from typing import Any, Awaitable, Callable, Iterable

from libs.core.config import get_settings
from libs.core.logging import get_logger


logger = get_logger(__name__)


EARNINGS_TTL_SECONDS = 6 * 60 * 60       # 6 h
NEWS_TTL_SECONDS = 15 * 60               # 15 min
PROFILE_TTL_SECONDS = 24 * 60 * 60       # 24 h
PER_SYMBOL_EARNINGS_TTL_SECONDS = 6 * 60 * 60  # 6 h


# Defense-in-depth secret redaction for any error string we surface to
# logs or HTTP responses. httpx's HTTPStatusError message embeds the
# request URL — which for FMP includes ?apikey=... in the query string.
# We must scrub before showing the message to anyone.
_APIKEY_REDACT_RE = __import__("re").compile(
    r"(api[_-]?key|apikey|token|bearer)=[^&\s'\"]+", __import__("re").IGNORECASE
)


def _redact(msg: object) -> str:
    s = str(msg) if msg is not None else ""
    return _APIKEY_REDACT_RE.sub(r"\1=<REDACTED>", s)
ALL_MARKET_EARNINGS_LIMIT_FLOOR = 50
ALL_MARKET_EARNINGS_LIMIT_CEILING = 500
NEWS_LIMIT_PER_TICKER_CEILING = 25

# Per-upstream-HTTP-call timeout for news + profile. Frontend apiFetch
# aborts at 30s so each section-level provider call must complete (or
# fail fast) well inside that budget. 4s is the spec floor and is
# observed to be enough for FMP /stable/news/stock and /stable/profile.
PROVIDER_CALL_TIMEOUT_SECONDS = 4.0
# Earnings-calendar timeout is wider because the response is the whole
# /stable/earning-calendar payload for the date range (potentially
# hundreds of rows even when ticker-filtered downstream). 4s was too
# tight in practice on cold-cache requests; 7s is a safe upper bound
# that still leaves headroom under the 30s frontend cap. After the
# first successful fetch, all callers within the 6h TTL serve from
# cache and the timeout never matters again.
EARNINGS_CALL_TIMEOUT_SECONDS = 7.0
# Upper bound on how long the news section can spend across all per-ticker
# calls. Past this, return what we have with cache_status=timeout/partial.
NEWS_SECTION_BUDGET_SECONDS = 10.0
# Max number of in-flight FMP news calls at once. Backend has its own
# RateLimiter (5 req/s) so this just prevents head-of-line blocking when
# many tabs poll concurrently.
NEWS_CONCURRENCY = 3
# Soft cap on tickers per news call before mirror feed truncates (matches
# the spec: news goes against the top-N tickers only).
NEWS_TOP_N_TICKERS_DEFAULT = 5
NEWS_TOP_N_TICKERS_CEILING = 50


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

    def peek_entry(self, key: str) -> _CacheEntry | None:
        """Return the raw cache entry regardless of TTL, or None.

        Used by the stale-on-refresh-fail fallback so we can serve a
        slightly-stale payload instead of an empty error envelope.
        """
        return self._entries.get(key)

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
_per_symbol_earnings_cache = TTLCache(PER_SYMBOL_EARNINGS_TTL_SECONDS)


def reset_caches_for_tests() -> None:
    """Drop all market-events caches; used by unit tests for isolation."""
    _earnings_cache.reset()
    _news_cache.reset()
    _profile_cache.reset()
    _per_symbol_earnings_cache.reset()


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
                coro = fmp_fetcher(start_date, end_date)
            else:
                from libs.adapters.fmp_adapter import FMPAdapter
                adapter = FMPAdapter()
                coro = adapter.get_earnings_calendar(start_date, end_date)
            rows = await asyncio.wait_for(coro, timeout=EARNINGS_CALL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            logger.warning("market_events.earnings_timeout",
                           timeout=EARNINGS_CALL_TIMEOUT_SECONDS)
            return ProviderResult(
                data=[],
                status="timeout",
                fetched_at=time.time(),
                error=f"upstream timeout > {EARNINGS_CALL_TIMEOUT_SECONDS}s",
            )
        except Exception as exc:  # noqa: BLE001
            redacted = _redact(exc)
            logger.warning("market_events.earnings_error", error=redacted)
            # Detect plan-blocked / payment-required as "unavailable" so the
            # UI can show a clear message rather than a noisy "error" badge.
            low = redacted.lower()
            if (
                "402" in redacted
                or "payment required" in low
                or "subscription" in low
                or "not on this plan" in low
            ):
                return ProviderResult(
                    data=[],
                    status="unavailable",
                    fetched_at=time.time(),
                    error="earnings calendar endpoint not on this provider plan",
                )
            return ProviderResult(
                data=[],
                status="error",
                fetched_at=time.time(),
                error=f"{type(exc).__name__}: {redacted[:200]}",
            )

        if not isinstance(rows, list):
            return ProviderResult(
                data=[],
                status="partial",
                fetched_at=time.time(),
                note="upstream returned non-list payload",
            )
        return ProviderResult(data=rows, status="ok", fetched_at=time.time())

    # Stale-on-refresh-fail: if the fetcher returns timeout/error and we
    # have a previous cached payload, serve that with cache_status="cached"
    # and a stale note rather than the empty error envelope.
    stale_entry = _earnings_cache.peek_entry(cache_key)
    result: ProviderResult = await _earnings_cache.get_or_fetch(cache_key, _fetch)
    if (result.status in ("timeout", "error", "partial")
            and not result.data
            and stale_entry is not None
            and isinstance(stale_entry.value, ProviderResult)
            and stale_entry.value.data):
        result = ProviderResult(
            data=stale_entry.value.data,
            status="cached",
            fetched_at=stale_entry.fetched_at,
            error=None,
            note=f"refresh failed ({result.status}), serving stale cache",
        )

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
# Per-symbol earnings fallback
# ---------------------------------------------------------------------------
#
# FMP's /stable/earning-calendar endpoint is plan-blocked on free tier
# (silently returns []). The /stable/earnings?symbol=X endpoint IS
# available on free tier and returns historical + future earnings rows
# for one ticker. We use it as a per-symbol fallback for ticker-scoped
# scopes (mirror / scanner / ticker) when the all-market calendar is
# empty or unavailable. The result is cached per-symbol for 6h.


async def get_per_symbol_upcoming_earnings(
    symbol: str,
    *,
    today: date | None = None,
    horizon_days: int = 30,
    fmp_per_symbol_fetcher: Callable[[str], Awaitable[list[dict]]] | None = None,
) -> ProviderResult:
    """Return future-dated earnings rows from /stable/earnings?symbol=X.

    Works on free FMP plans where the all-market calendar is restricted.
    Filters rows to ``today <= date <= today + horizon_days`` after fetch.
    Result is cached for 6h per symbol.
    """
    sym = (symbol or "").upper().strip()
    if not sym:
        return ProviderResult(data=[], status="unavailable",
                              fetched_at=time.time(),
                              error="empty symbol")
    if not _fmp_configured() and fmp_per_symbol_fetcher is None:
        return ProviderResult(data=[], status="unavailable",
                              fetched_at=time.time(),
                              error="FMP API key not configured")

    today = today or date.today()
    horizon_end = today + timedelta(days=max(1, int(horizon_days)))
    cache_key = f"per_symbol_earnings::{sym}"

    async def _fetch() -> ProviderResult:
        try:
            if fmp_per_symbol_fetcher is not None:
                coro = fmp_per_symbol_fetcher(sym)
            else:
                from libs.adapters.fmp_adapter import FMPAdapter
                adapter = FMPAdapter()
                coro = adapter.fetch_json("/stable/earnings", params={"symbol": sym})
            rows = await asyncio.wait_for(coro, timeout=EARNINGS_CALL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return ProviderResult(data=[], status="timeout",
                                  fetched_at=time.time(),
                                  error=f"upstream timeout > {EARNINGS_CALL_TIMEOUT_SECONDS}s")
        except Exception as exc:  # noqa: BLE001
            redacted = _redact(exc)
            low = redacted.lower()
            if (
                "402" in redacted
                or "404" in redacted
                or "payment required" in low
                or "subscription" in low
            ):
                return ProviderResult(
                    data=[], status="unavailable",
                    fetched_at=time.time(),
                    error="per-symbol earnings endpoint not on this provider plan",
                )
            return ProviderResult(data=[], status="error",
                                  fetched_at=time.time(),
                                  error=f"{type(exc).__name__}: {redacted[:200]}")

        if not isinstance(rows, list):
            return ProviderResult(data=[], status="partial",
                                  fetched_at=time.time(),
                                  note="upstream returned non-list payload")
        return ProviderResult(data=rows, status="ok", fetched_at=time.time())

    stale_entry = _per_symbol_earnings_cache.peek_entry(cache_key)
    result = await _per_symbol_earnings_cache.get_or_fetch(cache_key, _fetch)
    if (result.status in ("timeout", "error", "partial")
            and not result.data
            and stale_entry is not None
            and isinstance(stale_entry.value, ProviderResult)
            and stale_entry.value.data):
        result = ProviderResult(
            data=stale_entry.value.data,
            status="cached",
            fetched_at=stale_entry.fetched_at,
            error=None,
            note=f"refresh failed ({result.status}), serving stale per-symbol earnings",
        )

    # Always normalize symbol field + filter to the requested horizon BEFORE
    # returning so the service layer doesn't have to repeat date math.
    upcoming: list[dict] = []
    for r in (result.data or []):
        if not isinstance(r, dict):
            continue
        d_str = r.get("date") or r.get("reportDate")
        if not d_str:
            continue
        try:
            d = date.fromisoformat(str(d_str)[:10])
        except (TypeError, ValueError):
            continue
        if today <= d <= horizon_end:
            row = dict(r)
            row.setdefault("symbol", sym)
            upcoming.append(row)
    return ProviderResult(
        data=upcoming,
        status=result.status,
        fetched_at=result.fetched_at,
        error=result.error,
        note=result.note,
    )


async def get_upcoming_earnings_for_tickers(
    tickers: Iterable[str],
    *,
    today: date | None = None,
    horizon_days: int = 30,
    fmp_per_symbol_fetcher: Callable[[str], Awaitable[list[dict]]] | None = None,
) -> ProviderResult:
    """Fan-out wrapper: per-symbol earnings for a list of tickers.

    Bounded by NEWS_CONCURRENCY (3) and the news section budget so the
    earnings fan-out cannot stall a slow request indefinitely. Returns a
    single ProviderResult with all upcoming rows merged. ``status`` is
    the worst of the per-call statuses (unavailable wins; timeout next;
    then error; then ok).
    """
    cleaned = [t.upper().strip() for t in tickers if t and t.strip()]
    cleaned = list(dict.fromkeys(cleaned))[:NEWS_TOP_N_TICKERS_CEILING]
    if not cleaned:
        return ProviderResult(data=[], status="ok", fetched_at=time.time(),
                              note="no tickers requested")

    semaphore = asyncio.Semaphore(NEWS_CONCURRENCY)
    deadline = time.time() + NEWS_SECTION_BUDGET_SECONDS
    out: list[dict] = []
    statuses: list[str] = []
    rows_lock = asyncio.Lock()
    plan_unavailable = asyncio.Event()

    async def _one(tk: str) -> None:
        if plan_unavailable.is_set():
            statuses.append("unavailable")
            return
        if time.time() >= deadline:
            statuses.append("timeout")
            return
        async with semaphore:
            if plan_unavailable.is_set() or time.time() >= deadline:
                statuses.append("timeout")
                return
            r = await get_per_symbol_upcoming_earnings(
                tk, today=today, horizon_days=horizon_days,
                fmp_per_symbol_fetcher=fmp_per_symbol_fetcher,
            )
            statuses.append(r.status)
            if r.status == "unavailable":
                plan_unavailable.set()
                return
            async with rows_lock:
                out.extend(r.data or [])

    tasks = [asyncio.create_task(_one(t)) for t in cleaned]
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=NEWS_SECTION_BUDGET_SECONDS,
        )
    except asyncio.TimeoutError:
        for t in tasks:
            if not t.done():
                t.cancel()

    # Choose the worst status to surface
    priority = {"unavailable": 4, "timeout": 3, "error": 2, "partial": 1, "ok": 0, "cached": 0}
    if not statuses:
        return ProviderResult(data=out, status="timeout",
                              fetched_at=time.time(),
                              note="all per-symbol earnings tasks cancelled")
    worst = max(statuses, key=lambda s: priority.get(s, 0))
    return ProviderResult(data=out, status=worst,
                          fetched_at=time.time(),
                          note=f"per-symbol earnings worst_status={worst}")


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
                # Custom fetcher path: still cap with the section budget so
                # a misbehaving injection cannot stall the route.
                rows = await asyncio.wait_for(
                    fmp_news_fetcher(cleaned, from_date, to_date, limit_per_ticker),
                    timeout=NEWS_SECTION_BUDGET_SECONDS,
                )
            else:
                rows = await _default_fmp_news(cleaned, from_date, to_date, limit_per_ticker)
        except _ProviderUnavailable as exc:
            return ProviderResult(
                data=[],
                status="unavailable",
                fetched_at=time.time(),
                error=_redact(str(exc)),
            )
        except asyncio.TimeoutError:
            logger.warning("market_events.news_section_timeout",
                           budget=NEWS_SECTION_BUDGET_SECONDS)
            return ProviderResult(
                data=[],
                status="timeout",
                fetched_at=time.time(),
                error=f"news section budget {NEWS_SECTION_BUDGET_SECONDS}s exceeded",
            )
        except Exception as exc:  # noqa: BLE001
            redacted = _redact(exc)
            logger.warning("market_events.news_error", error=redacted)
            return ProviderResult(
                data=[],
                status="error",
                fetched_at=time.time(),
                error=f"{type(exc).__name__}: {redacted[:200]}",
            )

        if not isinstance(rows, list):
            return ProviderResult(
                data=[],
                status="partial",
                fetched_at=time.time(),
                note="upstream returned non-list payload",
            )
        return ProviderResult(data=rows, status="ok", fetched_at=time.time())

    stale_entry = _news_cache.peek_entry(cache_key)
    result = await _news_cache.get_or_fetch(cache_key, _fetch)
    if (result.status in ("timeout", "error", "partial")
            and not result.data
            and stale_entry is not None
            and isinstance(stale_entry.value, ProviderResult)
            and stale_entry.value.data):
        result = ProviderResult(
            data=stale_entry.value.data,
            status="cached",
            fetched_at=stale_entry.fetched_at,
            error=None,
            note=f"refresh failed ({result.status}), serving stale cache",
        )
    return result


class _ProviderUnavailable(Exception):
    """Raised when FMP returns 404 / not-on-this-plan / similar."""


async def _default_fmp_news(
    tickers: list[str],
    from_date: str,
    to_date: str,
    limit_per_ticker: int,
) -> list[dict]:
    """Default FMP news fetcher with per-call timeout + bounded concurrency.

    Calls FMP per ticker (stable's news/stock returns per-symbol news).
    Each call is wrapped in ``asyncio.wait_for`` so a single slow ticker
    cannot stall the whole news section, and the section's overall
    elapsed time is capped by ``NEWS_SECTION_BUDGET_SECONDS`` (after
    which we return what we have so far).

    The 404-detection fast path is preserved: if the endpoint isn't on
    the FMP plan at all, we raise ``_ProviderUnavailable`` so the
    upstream cache layer reports ``unavailable`` instead of repeatedly
    retrying per ticker.
    """
    from libs.adapters.fmp_adapter import FMPAdapter
    adapter = FMPAdapter()

    semaphore = asyncio.Semaphore(NEWS_CONCURRENCY)
    section_deadline = time.time() + NEWS_SECTION_BUDGET_SECONDS
    plan_unavailable = asyncio.Event()
    rows_lock = asyncio.Lock()
    out: list[dict] = []

    async def _one(tk: str) -> None:
        if plan_unavailable.is_set():
            return
        if time.time() >= section_deadline:
            return
        async with semaphore:
            if plan_unavailable.is_set() or time.time() >= section_deadline:
                return
            params = {
                "symbols": tk,
                "from": from_date,
                "to": to_date,
                "limit": str(limit_per_ticker),
            }
            try:
                data = await asyncio.wait_for(
                    adapter.fetch_json("/stable/news/stock", params=params),
                    timeout=PROVIDER_CALL_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                logger.warning("market_events.news_per_ticker_timeout", ticker=tk)
                return
            except Exception as exc:  # noqa: BLE001
                redacted = _redact(exc)
                low = redacted.lower()
                # 402 / 404 / "Payment Required" / "subscription" all mean
                # the news endpoint is plan-blocked. First failure flips
                # the unavailable flag so we don't burn quota across N
                # tickers — and we never log the apikey.
                if (
                    "402" in redacted
                    or "404" in redacted
                    or "not found" in low
                    or "payment required" in low
                    or "subscription" in low
                ):
                    plan_unavailable.set()
                    return
                logger.warning("market_events.news_per_ticker_error",
                               ticker=tk, error=redacted[:120])
                return
            if isinstance(data, list):
                async with rows_lock:
                    for row in data[:limit_per_ticker]:
                        if isinstance(row, dict):
                            row.setdefault("symbol", tk)
                            out.append(row)

    tasks = [asyncio.create_task(_one(t)) for t in tickers]
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=NEWS_SECTION_BUDGET_SECONDS,
        )
    except asyncio.TimeoutError:
        # Best-effort cancellation; we keep whatever rows we collected.
        for t in tasks:
            if not t.done():
                t.cancel()

    if plan_unavailable.is_set() and not out:
        raise _ProviderUnavailable(
            "FMP /stable/news/stock returned 404; news endpoint not on this plan"
        )

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
                coro = fmp_profile_fetcher(sym)
            else:
                from libs.adapters.fmp_adapter import FMPAdapter
                adapter = FMPAdapter()
                coro = adapter.get_profile(sym)
            row = await asyncio.wait_for(coro, timeout=PROVIDER_CALL_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            return ProviderResult(
                data={},
                status="timeout",
                fetched_at=time.time(),
                error=f"upstream timeout > {PROVIDER_CALL_TIMEOUT_SECONDS}s",
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(
                data={},
                status="error",
                fetched_at=time.time(),
                error=f"{type(exc).__name__}: {_redact(exc)[:200]}",
            )
        if not isinstance(row, dict) or not row:
            return ProviderResult(
                data={},
                status="unavailable",
                fetched_at=time.time(),
                note="profile not found",
            )
        return ProviderResult(data=row, status="ok", fetched_at=time.time())

    stale_entry = _profile_cache.peek_entry(cache_key)
    result = await _profile_cache.get_or_fetch(cache_key, _fetch)
    if (result.status in ("timeout", "error")
            and not result.data
            and stale_entry is not None
            and isinstance(stale_entry.value, ProviderResult)
            and stale_entry.value.data):
        result = ProviderResult(
            data=stale_entry.value.data,
            status="cached",
            fetched_at=stale_entry.fetched_at,
            error=None,
            note=f"refresh failed ({result.status}), serving stale cache",
        )
    return result
