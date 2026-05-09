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
  - Section-level independence: the earnings call and the news call run
    in parallel; one failing or timing out NEVER hides the other.
  - News is bounded to the top-N tickers by default (N=5) so a 20+ ticker
    Mirror feed can't trigger 20+ sequential FMP news calls.
  - The disclaimer text is a STRING literal that the source-grep guard
    in ``tests/unit/test_no_trading_writes.py`` and the i18n-banned
    phrase test ignore — it is research-only language by design.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Iterable

from sqlalchemy.orm import Session

from libs.core.time import utc_now
from libs.market_events import providers as p


SCOPES = ("mirror", "scanner", "all_supported", "ticker")
DEFAULT_DAYS = 7
DEFAULT_LIMIT = 100
DEFAULT_LIMIT_PER_TICKER = 5
# Top-N tickers used for news in mirror/scanner scopes. Capped here so the
# news fan-out never exceeds the provider's per-call timeout budget.
NEWS_TOP_N_DEFAULT = p.NEWS_TOP_N_TICKERS_DEFAULT
NEWS_TOP_N_CEILING = p.NEWS_TOP_N_TICKERS_CEILING

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
    news_top_n: int = NEWS_TOP_N_DEFAULT,
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

    # Bound the news top-N (no-op for ticker scope where len(tickers)==1).
    bounded_top_n = max(1, min(NEWS_TOP_N_CEILING, int(news_top_n)))
    news_tickers = list(tickers)[:bounded_top_n] if tickers else []

    # Earnings + news run in PARALLEL with section-level isolation. Either
    # call failing/timing out cannot hide the other.
    #
    # Earnings fallback: FMP's /stable/earning-calendar is plan-blocked on
    # the free tier and silently returns []. When the calendar is empty
    # AND we are scoped to a list of tickers (mirror/scanner/ticker), we
    # fan out to /stable/earnings?symbol=X (which IS on the free tier)
    # for the same set of tickers and merge the results. all_supported
    # cannot use the fallback because we have no ticker list.
    async def _earnings_task() -> p.ProviderResult:
        try:
            primary = await p.get_earnings_calendar(**earnings_kwargs)
            if (
                scope != "all_supported"
                and tickers
                and (not primary.data)
                and primary.status in ("ok", "cached", "unavailable")
            ):
                fallback = await p.get_upcoming_earnings_for_tickers(
                    tickers, horizon_days=days,
                )
                if fallback.data:
                    return p.ProviderResult(
                        data=fallback.data,
                        status=fallback.status,
                        fetched_at=fallback.fetched_at,
                        error=fallback.error,
                        note=(
                            "calendar empty/blocked → per-symbol /stable/earnings "
                            f"fallback ({len(fallback.data)} rows)"
                        ),
                    )
            return primary
        except Exception as exc:  # noqa: BLE001
            return p.ProviderResult(
                data=[], status="error",
                fetched_at=utc_now().timestamp(),
                error=f"section-level earnings failure: {type(exc).__name__}",
            )

    async def _news_task() -> p.ProviderResult:
        if scope == "all_supported":
            return p.ProviderResult(
                data=[], status="ok",
                fetched_at=utc_now().timestamp(),
                note="all_supported scope intentionally omits news to respect provider quotas",
            )
        if not news_tickers:
            return p.ProviderResult(
                data=[], status="ok",
                fetched_at=utc_now().timestamp(),
                note="no tickers in scope",
            )
        kwargs = dict(
            tickers=news_tickers,
            from_date=news_from,
            to_date=news_to,
            limit_per_ticker=limit_per_ticker,
        )
        if news_provider is not None:
            kwargs["fmp_news_fetcher"] = news_provider
        try:
            return await p.get_stock_news(**kwargs)
        except Exception as exc:  # noqa: BLE001
            return p.ProviderResult(
                data=[], status="error",
                fetched_at=utc_now().timestamp(),
                error=f"section-level news failure: {type(exc).__name__}",
            )

    earnings_result, news_result = await asyncio.gather(
        _earnings_task(), _news_task()
    )

    # Normalize + tag with diagnostics counts. Track raw vs parsed so the
    # UI can distinguish "provider returned 0 rows" from "parser dropped
    # everything" — a real differential when content is empty.
    raw_earnings_count = len(earnings_result.data or [])
    earnings_items: list[dict] = []
    earnings_skipped: dict[str, int] = {"non_dict": 0, "missing_symbol": 0, "missing_date": 0}
    for r in (earnings_result.data or []):
        if not isinstance(r, dict):
            earnings_skipped["non_dict"] += 1
            continue
        sym_check = str(r.get("symbol") or r.get("ticker") or "").strip()
        if not sym_check:
            earnings_skipped["missing_symbol"] += 1
            continue
        if not (r.get("date") or r.get("reportDate")):
            earnings_skipped["missing_date"] += 1
            continue
        earnings_items.append(_normalize_earnings_row(r, mirror_index))

    raw_news_count = len(news_result.data or [])
    news_items: list[dict] = []
    news_skipped: dict[str, int] = {"non_dict": 0, "missing_title": 0}
    for r in (news_result.data or []):
        if not isinstance(r, dict):
            news_skipped["non_dict"] += 1
            continue
        if not (r.get("title") or "").strip():
            news_skipped["missing_title"] += 1
            continue
        news_items.append(_normalize_news_row(r, mirror_index))

    # Sort: earnings by report_date ascending; news by published_at descending
    earnings_items.sort(key=lambda x: (x.get("report_date") or "", x.get("ticker") or ""))
    news_items.sort(
        key=lambda x: (x.get("published_at") or ""),
        reverse=True,
    )

    # Aggregate "any section unhappy" flag for the frontend banner. The
    # response itself is always HTTP 200 regardless of provider state.
    section_unhappy = (
        earnings_result.status not in ("ok", "cached")
        or news_result.status not in ("ok", "cached")
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
            "news_tickers_used": len(news_tickers),
        },
        "diagnostics": {
            "requested_ticker_count": len(tickers) if tickers else 0,
            "news_ticker_count": len(news_tickers),
            "earnings_raw_item_count": raw_earnings_count,
            "earnings_parsed_item_count": len(earnings_items),
            "earnings_skipped_count": sum(earnings_skipped.values()),
            "earnings_skipped_reasons": earnings_skipped,
            "news_raw_item_count": raw_news_count,
            "news_parsed_item_count": len(news_items),
            "news_skipped_count": sum(news_skipped.values()),
            "news_skipped_reasons": news_skipped,
        },
        "tickers_in_scope": tickers,
        "news_tickers_in_scope": news_tickers,
        "earnings": earnings_items,
        "news": news_items,
        "any_section_partial": section_unhappy,
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
    # Per-symbol fallback: if the calendar returned nothing for this
    # ticker (free-tier blocked or no upcoming events in the window),
    # try /stable/earnings?symbol=X which is on the free tier.
    if (not earnings_result.data
            and earnings_result.status in ("ok", "cached", "unavailable")):
        per_sym = await p.get_per_symbol_upcoming_earnings(
            sym, horizon_days=days,
        )
        if per_sym.data:
            earnings_result = p.ProviderResult(
                data=per_sym.data,
                status=per_sym.status,
                fetched_at=per_sym.fetched_at,
                error=per_sym.error,
                note="calendar empty/blocked → per-symbol /stable/earnings fallback",
            )

    news_kwargs = dict(
        tickers=[sym],
        from_date=news_from,
        to_date=news_to,
        limit_per_ticker=10,
    )
    if news_provider is not None:
        news_kwargs["fmp_news_fetcher"] = news_provider
    news_result = await p.get_stock_news(**news_kwargs)
    # 30-day fallback: if the requested window is < 30 days AND news came
    # back ok-but-empty, retry once with a 30-day window. Spec'd in P3.
    if (not news_result.data
            and news_result.status in ("ok", "cached")
            and days < 30):
        from datetime import date as _date, timedelta as _td
        wide_from = (_date.today() - _td(days=30)).isoformat()
        wide_to = _date.today().isoformat()
        wide_kwargs = dict(news_kwargs)
        wide_kwargs["from_date"] = wide_from
        wide_kwargs["to_date"] = wide_to
        wide_result = await p.get_stock_news(**wide_kwargs)
        if wide_result.data:
            news_result = p.ProviderResult(
                data=wide_result.data,
                status=wide_result.status,
                fetched_at=wide_result.fetched_at,
                error=wide_result.error,
                note=f"7d empty → 30d fallback returned {len(wide_result.data)} items",
            )

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

    # Empty-state hints — surfaced in the response so the UI can
    # explain "no upcoming earnings in horizon" vs "provider blocked"
    # vs "no recent news".
    empty_hints: list[str] = []
    if not earnings_items:
        if earnings_result.status == "unavailable":
            empty_hints.append("earnings: provider plan does not include earnings calendar")
        else:
            empty_hints.append(f"earnings: no upcoming earnings within {days}d horizon")
    if not news_items:
        if news_result.status == "unavailable":
            empty_hints.append("news: provider plan does not include stock news")
        elif days < 30:
            empty_hints.append(f"news: no provider news in {days}d window (30d fallback also empty)")
        else:
            empty_hints.append(f"news: no provider news in {days}d window")

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
        "provider_notes": {
            "fmp_profile": profile_result.note,
            "fmp_earnings": earnings_result.note,
            "fmp_news": news_result.note,
        },
        "diagnostics": {
            "earnings_raw_item_count": len(earnings_result.data or []),
            "earnings_parsed_item_count": len(earnings_items),
            "news_raw_item_count": len(news_result.data or []),
            "news_parsed_item_count": len(news_items),
        },
        "empty_state_hints": empty_hints,
        "profile": profile_result.data,
        "upcoming_earnings": earnings_items,
        "recent_news": news_items,
        "counts": {
            "earnings": len(earnings_items),
            "news": len(news_items),
        },
        "disclaimer": DISCLAIMER,
    }
