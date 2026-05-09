"""Market Events composition service — combines provider results into the
4 supported scopes (mirror, scanner, all_supported, ticker).

Design rules:

  - Pure read-only. Never writes the database. Never calls a Trading 212
    write endpoint. Never touches order_intent / order_draft / submit
    objects. Never mutates FEATURE_T212_LIVE_SUBMIT.
  - "all_supported" is the only scope that issues an unfiltered earnings
    call, and it always carries a ``limit`` cap. There is intentionally
    no "all_supported" news scope.
  - Each item carries ``mapping_status`` (mapped / unmapped) and
    ``source_tags`` from the Trading 212 Mirror so the UI can render
    badges consistently with the Mirror Watchlist.
  - The disclaimer text is a STRING literal that the source-grep guard
    in ``tests/unit/test_no_trading_writes.py`` and the i18n-banned
    phrase test ignore — it is research-only language by design.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from libs.core.time import utc_now
from libs.market_events import providers as p


SCOPES = ("mirror", "scanner", "all_supported", "ticker")
DEFAULT_DAYS = 7
DEFAULT_LIMIT = 100
DEFAULT_LIMIT_PER_TICKER = 5

DISCLAIMER = (
    "Research events only. Earnings and news are informational and "
    "require independent validation."
)


def _date_range(days: int) -> tuple[str, str, str, str]:
    """Return (from_iso, to_iso, news_from_iso, news_to_iso) date strings.

    Earnings window is [today, today + days]. News window is
    [today - days, today] — recent news, not future scheduled news.
    """
    today = date.today()
    earnings_to = today + timedelta(days=days)
    news_from = today - timedelta(days=days)
    return (
        today.isoformat(),
        earnings_to.isoformat(),
        news_from.isoformat(),
        today.isoformat(),
    )


def _normalize_earnings_row(
    raw: dict, mirror_index: dict | None = None
) -> dict:
    """Map an FMP earnings row to the platform format.

    FMP stable earnings calendar fields (representative):
      symbol, date, time (bmo|amc), epsEstimated, revenueEstimated, ...

    Some FMP responses use slightly different keys; this function is
    defensive so a schema drift on the upstream side does not break the
    UI.
    """
    sym = str(raw.get("symbol") or raw.get("ticker") or "").upper()
    report_date = raw.get("date") or raw.get("reportDate") or None
    time_code = (raw.get("time") or "unknown").lower()
    if time_code not in ("bmo", "amc", "unknown", "dmh", ""):
        time_code = "unknown"
    if time_code == "":
        time_code = "unknown"

    item = {
        "ticker": sym,
        "company_name": raw.get("companyName") or raw.get("name") or None,
        "report_date": report_date,
        "time": time_code,
        "eps_estimate": raw.get("epsEstimated") or raw.get("epsEstimate") or None,
        "revenue_estimate": (
            raw.get("revenueEstimated")
            or raw.get("revenueEstimate")
            or None
        ),
        "source": "fmp",
        "is_in_mirror": False,
        "source_tags": [],
        "mapping_status": "unmapped",
    }
    if mirror_index is not None:
        meta = mirror_index.get(sym)
        if meta is not None:
            item["is_in_mirror"] = True
            item["source_tags"] = list(meta.get("source_tags") or [])
            item["mapping_status"] = meta.get("mapping_status") or "unmapped"
    return item


def _normalize_news_row(
    raw: dict, mirror_index: dict | None = None
) -> dict:
    """Map an FMP news row to the platform format.

    FMP stable news fields (representative):
      symbol, publishedDate, title, text, site, url, ...
    """
    sym = str(raw.get("symbol") or raw.get("ticker") or "").upper()
    item = {
        "ticker": sym,
        "title": raw.get("title") or "",
        "summary": raw.get("text") or raw.get("summary") or None,
        "published_at": (
            raw.get("publishedDate")
            or raw.get("publishedAt")
            or raw.get("date")
            or None
        ),
        "source_name": raw.get("site") or raw.get("source") or None,
        "url": raw.get("url") or raw.get("link") or None,
        "provider": "fmp",
        "sentiment": None,
        "is_in_mirror": False,
        "source_tags": [],
        "mapping_status": "unmapped",
    }
    if mirror_index is not None:
        meta = mirror_index.get(sym)
        if meta is not None:
            item["is_in_mirror"] = True
            item["source_tags"] = list(meta.get("source_tags") or [])
            item["mapping_status"] = meta.get("mapping_status") or "unmapped"
    return item


def _mirror_index(db: Session) -> tuple[list[str], dict]:
    """Return (tickers, index) for the current Trading 212 Mirror.

    ``index`` is keyed by uppercase display_ticker:
      { "MU": {"source_tags": ["HELD"], "mapping_status": "mapped"}, ... }
    """
    from libs.portfolio.mirror_watchlist_service import build_mirror_watchlist

    mirror = build_mirror_watchlist(db)
    tickers: list[str] = []
    index: dict[str, dict] = {}
    for it in mirror.get("items", []):
        sym = (it.get("display_ticker") or "").upper()
        if not sym:
            continue
        tickers.append(sym)
        index[sym] = {
            "source_tags": tuple(it.get("source_tags") or ()),
            "mapping_status": it.get("mapping_status") or "unmapped",
            "broker_ticker": it.get("broker_ticker"),
            "company_name": it.get("company_name"),
        }
    return tickers, index


def _scanner_tickers() -> list[str]:
    from libs.scanner.scanner_universe import SCANNER_RESEARCH_UNIVERSE
    return list(SCANNER_RESEARCH_UNIVERSE)


def _bound_limit(limit: int) -> int:
    return max(p.ALL_MARKET_EARNINGS_LIMIT_FLOOR,
               min(p.ALL_MARKET_EARNINGS_LIMIT_CEILING, int(limit)))


# ---------------------------------------------------------------------------
# Public composition functions
# ---------------------------------------------------------------------------


async def get_feed(
    db: Session,
    *,
    scope: str = "mirror",
    days: int = DEFAULT_DAYS,
    limit: int = DEFAULT_LIMIT,
    limit_per_ticker: int = DEFAULT_LIMIT_PER_TICKER,
    ticker: str | None = None,
    earnings_provider: callable | None = None,
    news_provider: callable | None = None,
) -> dict:
    """Composed feed: earnings + news within date range, scoped.

    Returns the response shape documented in the plan:

      {
        "scope": "...",
        "generated_at": "...",
        "date_range": {"from": "...", "to": "..."},
        "provider_status": {"fmp": "ok|...|unavailable", ...},
        "counts": {"earnings": N, "news": N, "tickers": N},
        "earnings": [...],
        "news": [...],
        "disclaimer": "...",
      }
    """
    if scope not in SCOPES:
        raise ValueError(f"Unknown scope '{scope}'. Allowed: {SCOPES}")

    days = max(1, min(60, int(days)))
    earnings_from, earnings_to, news_from, news_to = _date_range(days)

    if scope == "mirror":
        tickers, mirror_index = _mirror_index(db)
        # Mirror earnings: ticker-filter is applied by provider
    elif scope == "scanner":
        tickers = _scanner_tickers()
        mirror_index = None  # no source tags for scanner-only feed
    elif scope == "ticker":
        tickers = [(ticker or "").upper()] if ticker else []
        mirror_index = None
    else:  # all_supported
        tickers = []
        mirror_index = None

    # Earnings call — for mirror/scanner/ticker we filter by tickers AT THE
    # PROVIDER LEVEL (so the cache key remains broad but the response is
    # scoped). For all_supported we pass tickers=None and rely on limit.
    earnings_kwargs = dict(
        start_date=earnings_from,
        end_date=earnings_to,
        limit=_bound_limit(limit),
    )
    if scope == "all_supported":
        earnings_kwargs["tickers"] = None
    else:
        earnings_kwargs["tickers"] = tickers
    if earnings_provider is not None:
        earnings_kwargs["fmp_fetcher"] = earnings_provider

    earnings_result = await p.get_earnings_calendar(**earnings_kwargs)

    # News call — only for ticker / mirror / scanner. all_supported
    # explicitly does NOT issue an unbounded news call.
    if scope == "all_supported":
        news_result = p.ProviderResult(
            data=[],
            status="ok",
            fetched_at=earnings_result.fetched_at,
            note="all_supported scope intentionally omits news to respect provider quotas",
        )
    elif tickers:
        news_kwargs = dict(
            tickers=tickers,
            from_date=news_from,
            to_date=news_to,
            limit_per_ticker=limit_per_ticker,
        )
        if news_provider is not None:
            news_kwargs["fmp_news_fetcher"] = news_provider
        news_result = await p.get_stock_news(**news_kwargs)
    else:
        news_result = p.ProviderResult(
            data=[], status="ok", fetched_at=earnings_result.fetched_at,
            note="no tickers in scope",
        )

    # Normalize + tag
    earnings_items = [
        _normalize_earnings_row(r, mirror_index)
        for r in (earnings_result.data or [])
        if isinstance(r, dict)
    ]
    news_items = [
        _normalize_news_row(r, mirror_index)
        for r in (news_result.data or [])
        if isinstance(r, dict)
    ]

    # Sort: earnings by report_date ascending; news by published_at descending
    earnings_items.sort(key=lambda x: (x.get("report_date") or "", x.get("ticker") or ""))
    news_items.sort(
        key=lambda x: (x.get("published_at") or ""),
        reverse=True,
    )

    return {
        "scope": scope,
        "generated_at": utc_now().isoformat(),
        "date_range": {
            "earnings_from": earnings_from,
            "earnings_to": earnings_to,
            "news_from": news_from,
            "news_to": news_to,
        },
        "provider_status": {
            "fmp_earnings": earnings_result.status,
            "fmp_news": news_result.status,
        },
        "provider_errors": {
            "fmp_earnings": earnings_result.error,
            "fmp_news": news_result.error,
        },
        "provider_notes": {
            "fmp_earnings": earnings_result.note,
            "fmp_news": news_result.note,
        },
        "counts": {
            "earnings": len(earnings_items),
            "news": len(news_items),
            "tickers": len(tickers) if tickers else 0,
        },
        "tickers_in_scope": tickers,
        "earnings": earnings_items,
        "news": news_items,
        "disclaimer": DISCLAIMER,
    }


async def get_ticker_detail(
    db: Session,
    *,
    ticker: str,
    days: int = 30,
    profile_provider: callable | None = None,
    earnings_provider: callable | None = None,
    news_provider: callable | None = None,
) -> dict:
    """Composed detail view for one ticker: profile + earnings + news +
    mapping status.
    """
    sym = (ticker or "").upper().strip()
    if not sym:
        raise ValueError("ticker is required and must be non-empty")

    days = max(1, min(120, int(days)))

    # Mapping status
    from libs.instruments.mirror_instrument_mapper import _lookup_existing_mappings
    existing = _lookup_existing_mappings(db, [sym])
    existing_row = existing.get(sym)

    # Mirror metadata for this ticker (so the UI can show source tags)
    _, mirror_index = _mirror_index(db)
    mirror_meta = mirror_index.get(sym)

    # Profile (24h cache)
    profile_kwargs = {}
    if profile_provider is not None:
        profile_kwargs["fmp_profile_fetcher"] = profile_provider
    profile_result = await p.get_company_profile(sym, **profile_kwargs)

    # Earnings + news within window
    earnings_from, earnings_to, news_from, news_to = _date_range(days)
    earnings_kwargs = dict(
        start_date=earnings_from,
        end_date=earnings_to,
        tickers=[sym],
        limit=p.ALL_MARKET_EARNINGS_LIMIT_FLOOR,
    )
    if earnings_provider is not None:
        earnings_kwargs["fmp_fetcher"] = earnings_provider
    earnings_result = await p.get_earnings_calendar(**earnings_kwargs)

    news_kwargs = dict(
        tickers=[sym],
        from_date=news_from,
        to_date=news_to,
        limit_per_ticker=10,
    )
    if news_provider is not None:
        news_kwargs["fmp_news_fetcher"] = news_provider
    news_result = await p.get_stock_news(**news_kwargs)

    earnings_items = [
        _normalize_earnings_row(r, {sym: {
            "source_tags": (mirror_meta or {}).get("source_tags") or (),
            "mapping_status": "mapped" if existing_row else "unmapped",
        }})
        for r in (earnings_result.data or [])
        if isinstance(r, dict)
    ]
    news_items = [
        _normalize_news_row(r, {sym: {
            "source_tags": (mirror_meta or {}).get("source_tags") or (),
            "mapping_status": "mapped" if existing_row else "unmapped",
        }})
        for r in (news_result.data or [])
        if isinstance(r, dict)
    ]

    return {
        "ticker": sym,
        "generated_at": utc_now().isoformat(),
        "mapping_status": "mapped" if existing_row else "unmapped",
        "instrument_id": existing_row["instrument_id"] if existing_row else None,
        "company_name": (
            (existing_row or {}).get("company_name")
            or profile_result.data.get("companyName")
            or profile_result.data.get("name")
        ),
        "exchange_primary": (
            (existing_row or {}).get("exchange_primary")
            or profile_result.data.get("exchangeShortName")
        ),
        "currency": (
            (existing_row or {}).get("currency")
            or profile_result.data.get("currency")
        ),
        "country_code": (
            (existing_row or {}).get("country_code")
            or profile_result.data.get("country")
        ),
        "is_in_mirror": mirror_meta is not None,
        "mirror_source_tags": list((mirror_meta or {}).get("source_tags") or ()),
        "provider_status": {
            "fmp_profile": profile_result.status,
            "fmp_earnings": earnings_result.status,
            "fmp_news": news_result.status,
        },
        "profile": profile_result.data,
        "upcoming_earnings": earnings_items,
        "recent_news": news_items,
        "counts": {
            "earnings": len(earnings_items),
            "news": len(news_items),
        },
        "disclaimer": DISCLAIMER,
    }
