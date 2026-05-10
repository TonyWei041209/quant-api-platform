"""Overnight Market Brief — read-only composed view.

Combines existing modules into a single research-only brief:

  * Scanner Research-36 daily-EOD candidates  (libs.scanner.stock_scanner_service)
  * Trading 212 Mirror tickers + mapping plan (libs.portfolio.mirror_watchlist_service,
                                                libs.instruments.mirror_instrument_mapper)
  * Taxonomy classification                   (libs.scanner.market_taxonomy)
  * Multi-provider news                       (libs.market_events.providers.get_merged_news)
  * Per-symbol upcoming earnings              (libs.market_events.providers.
                                                get_upcoming_earnings_for_tickers)

This module:
  * never writes the database
  * never calls a Trading 212 write endpoint
  * never touches order_intent / order_draft / submit objects
  * never reads or mutates FEATURE_T212_LIVE_SUBMIT
  * never scrapes or automates a browser
  * never produces a trading recommendation — every candidate carries
    a research-only explanation

The brief is generated on demand from the route. There is intentionally
NO scheduler in this phase; a scheduled persistent job is documented in
``docs/overnight-taxonomy-market-brief-plan.md`` but not created here.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Awaitable, Callable, Iterable

from sqlalchemy.orm import Session

from libs.core.time import utc_now


DISCLAIMER = (
    "Research events only. The brief surfaces candidates that may be "
    "worth deeper investigation — it does NOT recommend any trade and "
    "does NOT provide buy/sell instructions, target prices, or position "
    "sizing. All matches require independent validation."
)

DEFAULT_DAYS = 7
# Interactive preview default. Lower than the prior 10 to keep news
# fan-out below the Polygon free-tier ~1 req/s ceiling and reduce the
# probability of FMP/Polygon rate-limit responses for an on-demand
# brief. A future scheduled persistence job — explicitly NOT wired up
# in this phase — may use a higher value with controlled pacing.
DEFAULT_NEWS_TOP_N = 5
# Maximum news fan-out for the interactive preview. The route also
# clamps news_top_n to 25 in case a higher value is requested.
MAX_NEWS_TOP_N_INTERACTIVE = 25
DEFAULT_NEWS_LIMIT_PER_TICKER = 3
DEFAULT_SCANNER_LIMIT = 50

# Research priority buckets — used for sorting the unified candidate
# list so the most-research-worthy items appear first.
PRIORITY_HIGHEST = 5
PRIORITY_HIGH = 4
PRIORITY_MEDIUM = 3
PRIORITY_LOW = 2
PRIORITY_LOWEST = 1


@dataclass
class _CandidateRow:
    ticker: str
    company_name: str | None = None
    instrument_id: str | None = None
    source_tags: tuple[str, ...] = ()
    taxonomy_broad: str | None = None
    taxonomy_subs: tuple[str, ...] = ()
    change_1d_pct: float | None = None
    change_5d_pct: float | None = None
    change_1m_pct: float | None = None
    week52_position_pct: float | None = None
    volume_ratio: float | None = None
    scan_types: tuple[str, ...] = ()
    signal_strength: str | None = None
    risk_flags: tuple[str, ...] = ()
    scanner_explanation: str | None = None
    upcoming_earnings: list[dict] | None = None
    recent_news: list[dict] | None = None
    mapping_status: str = "unmapped"
    research_priority: int = PRIORITY_LOWEST

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "company_name": self.company_name,
            "instrument_id": self.instrument_id,
            "source_tags": list(self.source_tags),
            "taxonomy": {
                "broad": self.taxonomy_broad,
                "subs": list(self.taxonomy_subs),
            },
            "price_move": {
                "change_1d_pct": self.change_1d_pct,
                "change_5d_pct": self.change_5d_pct,
                "change_1m_pct": self.change_1m_pct,
                "week52_position_pct": self.week52_position_pct,
                "volume_ratio": self.volume_ratio,
            },
            "scanner": {
                "scan_types": list(self.scan_types),
                "signal_strength": self.signal_strength,
                "risk_flags": list(self.risk_flags),
                "explanation": self.scanner_explanation,
            },
            "upcoming_earnings": self.upcoming_earnings or [],
            "recent_news": self.recent_news or [],
            "mapping_status": self.mapping_status,
            "research_priority": self.research_priority,
            # Structured factor list — chips the UI can render. Each
            # factor is a stable string ID + a human label. NEVER a
            # buy/sell/target signal.
            "research_priority_factors": self._compose_priority_factors(),
            "why_it_matters": self._compose_why_it_matters(),
            "explanation": self._compose_explanation(),
        }

    def _compose_priority_factors(self) -> list[dict]:
        """Return the deterministic factor list that produced the
        current research_priority bucket.

        Each entry is `{"id": "held", "label": "Currently held",
        "weight": "high"}`. The weight tier is informational; the
        priority bucket itself is the canonical sort key.

        Strict rule: NEVER include any factor that implies a trade,
        a target price, a position size, or directional language.
        """
        factors: list[dict] = []
        if "HELD" in self.source_tags:
            factors.append({"id": "held",
                            "label": "Currently held",
                            "weight": "high"})
        if "SCANNER" in self.source_tags:
            label = "Scanner candidate"
            if self.signal_strength:
                label = f"Scanner candidate ({self.signal_strength})"
            factors.append({
                "id": "scanner",
                "label": label,
                "weight": ("high" if self.signal_strength == "high"
                           else "medium" if self.signal_strength == "medium"
                           else "low"),
            })
        if self.recent_news:
            factors.append({
                "id": "news",
                "label": f"Recent news ({len(self.recent_news)})",
                "weight": "medium",
            })
        if self.upcoming_earnings:
            factors.append({
                "id": "earnings",
                "label": f"Upcoming earnings ({len(self.upcoming_earnings)})",
                "weight": "medium",
            })
        if "RECENTLY_TRADED" in self.source_tags:
            factors.append({"id": "recently_traded",
                            "label": "Recently traded",
                            "weight": "low"})
        if "WATCHED" in self.source_tags:
            factors.append({"id": "watched",
                            "label": "On your watch list",
                            "weight": "low"})
        if self.mapping_status == "newly_resolvable":
            factors.append({"id": "newly_resolvable",
                            "label": "Provider profile available",
                            "weight": "info"})
        elif self.mapping_status in ("unmapped", "unresolved"):
            factors.append({"id": "unmapped",
                            "label": "Not yet mapped",
                            "weight": "info"})
        if self.risk_flags:
            factors.append({
                "id": "risk_flags",
                "label": f"Risk flags ({len(self.risk_flags)})",
                "weight": "info",
            })
        return factors

    def _compose_why_it_matters(self) -> str:
        """Research-only one-liner explaining why the priority bucket
        was chosen. Strict ban on trade/target/position language."""
        bucket_label = {
            PRIORITY_HIGHEST: "Highest research priority",
            PRIORITY_HIGH: "High research priority",
            PRIORITY_MEDIUM: "Medium research priority",
            PRIORITY_LOW: "Low research priority",
            PRIORITY_LOWEST: "Lowest research priority",
        }.get(self.research_priority, "Research priority")
        # Highest combo case
        if (
            "HELD" in self.source_tags
            and self.recent_news
            and "SCANNER" in self.source_tags
        ):
            return (f"{bucket_label}: held position with scanner signal "
                    "and recent news — worth a closer look. Independent "
                    "validation required.")
        # Held + earnings combo
        if "HELD" in self.source_tags and self.upcoming_earnings:
            return (f"{bucket_label}: held position with earnings in the "
                    "next window. Independent validation required.")
        # Pure SCANNER high
        if "SCANNER" in self.source_tags and self.signal_strength == "high":
            return (f"{bucket_label}: scanner returned a high-strength "
                    "signal. Research the underlying conditions before "
                    "any decision.")
        # News-only
        if self.recent_news and "SCANNER" not in self.source_tags:
            return (f"{bucket_label}: provider news mentions this ticker. "
                    "Research the headlines before forming a view.")
        # Watched-only
        if (
            self.source_tags == ("WATCHED",)
            or self.source_tags == ("WATCHED", "UNMAPPED")
        ):
            return (f"{bucket_label}: on your watch list with no other "
                    "signals in this window.")
        return (f"{bucket_label}. Independent validation required.")

    def _compose_explanation(self) -> str:
        """Research-only natural-language summary. Banned-phrase clean."""
        bits: list[str] = []
        if "HELD" in self.source_tags:
            bits.append("currently held")
        if "RECENTLY_TRADED" in self.source_tags:
            bits.append("recently traded")
        if "WATCHED" in self.source_tags:
            bits.append("on your watch list")
        if "SCANNER" in self.source_tags and self.signal_strength:
            bits.append(f"scanner candidate ({self.signal_strength} signal)")
        if self.recent_news:
            bits.append(f"{len(self.recent_news)} recent provider headlines")
        if self.upcoming_earnings:
            bits.append(f"{len(self.upcoming_earnings)} upcoming earnings")
        if self.mapping_status == "unmapped" or self.mapping_status == "unresolved":
            bits.append("not yet mapped to platform instrument master")
        if self.mapping_status == "newly_resolvable":
            bits.append("provider profile available; mappable on next bootstrap")
        if not bits:
            bits.append("no notable signals in the current window")
        prefix = self.ticker
        if self.company_name:
            prefix = f"{self.ticker} ({self.company_name})"
        return f"{prefix}: " + ", ".join(bits) + ". Requires independent validation."


# ---------------------------------------------------------------------------
# Public composition function
# ---------------------------------------------------------------------------


async def build_overnight_brief(
    db: Session,
    *,
    days: int = DEFAULT_DAYS,
    scanner_limit: int = DEFAULT_SCANNER_LIMIT,
    news_top_n: int = DEFAULT_NEWS_TOP_N,
    news_limit_per_ticker: int = DEFAULT_NEWS_LIMIT_PER_TICKER,
    manual_tickers: Iterable[str] | None = None,
    fmp_news_fetcher: Callable[..., Awaitable[list[dict]]] | None = None,
    polygon_news_fetcher: Callable[..., Awaitable[list[dict]]] | None = None,
    fmp_per_symbol_fetcher: Callable[..., Awaitable[list[dict]]] | None = None,
    today: date | None = None,
) -> dict:
    """Compose the overnight brief.

    All upstream calls go through the existing read-only services. No
    DB write, no provider write, no scheduler, no live submit.
    """
    # Late imports to keep module import cycle-free
    from libs.scanner.stock_scanner_service import scan_stocks
    from libs.scanner import market_taxonomy as tax
    from libs.portfolio.mirror_watchlist_service import build_mirror_watchlist
    from libs.instruments.mirror_instrument_mapper import build_mirror_mapping_plan
    from libs.market_events import providers as p

    today = today or date.today()
    news_from = (today - timedelta(days=days)).isoformat()
    news_to = today.isoformat()

    # ---------- 1. Scanner candidates ----------
    try:
        scanner_response = scan_stocks(
            db, universe="all", limit=scanner_limit,
            sort_by="signal_strength",
            include_needs_research=False,
        )
        scanner_items = scanner_response.get("items", [])
    except Exception as exc:  # noqa: BLE001
        scanner_items = []
        scanner_response = {
            "scanned": 0, "matched": 0, "as_of": None,
            "error": f"{type(exc).__name__}",
        }

    # ---------- 2. Mirror tickers ----------
    mirror = build_mirror_watchlist(
        db, manual_tickers=list(manual_tickers) if manual_tickers else None,
    )
    mirror_index: dict[str, dict] = {}
    for it in mirror.get("items", []):
        sym = (it.get("display_ticker") or "").upper()
        if not sym:
            continue
        mirror_index[sym] = {
            "broker_ticker": it.get("broker_ticker"),
            "company_name": it.get("company_name"),
            "instrument_id": it.get("instrument_id"),
            "mapping_status": it.get("mapping_status") or "unmapped",
            "source_tags": tuple(it.get("source_tags") or ()),
        }

    # ---------- 3. Mapping plan (for newly_resolvable detection) ----------
    try:
        mapping_plan = await build_mirror_mapping_plan(
            db, fetch_profiles=False,
        )
        mapping_index: dict[str, str] = {}
        for it in mapping_plan.items:
            mapping_index[it.display_ticker] = it.mapping_status
    except Exception:  # noqa: BLE001
        mapping_index = {}

    # ---------- 4. Build unified ticker set ----------
    # Scanner candidates + Mirror tickers (held + recent + watched). Cap
    # the brief at scanner_limit so the news/earnings fan-out stays
    # bounded.
    candidate_rows: dict[str, _CandidateRow] = {}

    for s in scanner_items:
        ticker = (s.get("ticker") or "").upper()
        if not ticker:
            continue
        row = _CandidateRow(
            ticker=ticker,
            company_name=s.get("issuer_name"),
            instrument_id=s.get("instrument_id"),
            source_tags=("SCANNER",),
            change_1d_pct=s.get("change_1d_pct"),
            change_5d_pct=s.get("change_5d_pct"),
            change_1m_pct=s.get("change_1m_pct"),
            week52_position_pct=s.get("week52_position_pct"),
            volume_ratio=s.get("volume_ratio"),
            scan_types=tuple(s.get("scan_types") or ()),
            signal_strength=s.get("signal_strength"),
            risk_flags=tuple(s.get("risk_flags") or ()),
            scanner_explanation=s.get("explanation"),
            mapping_status="mapped" if s.get("instrument_id") else "unmapped",
        )
        candidate_rows[ticker] = row

    for ticker, meta in mirror_index.items():
        existing = candidate_rows.get(ticker)
        merged_tags = list(existing.source_tags) if existing else []
        for tag in meta.get("source_tags") or ():
            if tag in ("HELD", "RECENTLY_TRADED", "WATCHED") and tag not in merged_tags:
                merged_tags.append(tag)
        if existing:
            existing.source_tags = tuple(merged_tags)
            existing.company_name = existing.company_name or meta.get("company_name")
            existing.instrument_id = existing.instrument_id or meta.get("instrument_id")
            existing.mapping_status = (
                meta.get("mapping_status") or existing.mapping_status
            )
        else:
            candidate_rows[ticker] = _CandidateRow(
                ticker=ticker,
                company_name=meta.get("company_name"),
                instrument_id=meta.get("instrument_id"),
                source_tags=tuple(merged_tags) if merged_tags else (),
                mapping_status=meta.get("mapping_status") or "unmapped",
            )

    # Refine mapping_status using the mapping plan (newly_resolvable tag)
    for ticker, row in candidate_rows.items():
        plan_status = mapping_index.get(ticker)
        if plan_status and plan_status != "mapped":
            row.mapping_status = plan_status

    # Add UNMAPPED tag for visibility in the source_tags array
    for row in candidate_rows.values():
        if row.mapping_status in ("unmapped", "unresolved", "newly_resolvable"):
            tags = list(row.source_tags)
            if "UNMAPPED" not in tags:
                tags.append("UNMAPPED")
            row.source_tags = tuple(tags)

    # ---------- 5. Taxonomy classification ----------
    for row in candidate_rows.values():
        static = tax.classify_by_static_theme(row.ticker)
        if static:
            row.taxonomy_broad = static.get("broad")
            row.taxonomy_subs = tuple(static.get("subs") or ())

    # ---------- 6. News fan-out for top-N tickers ----------
    # Pick top-N by source priority (held first, then scanner, then
    # recently traded, then watched, then unmapped). News fan-out is
    # bounded to news_top_n to respect Polygon's 1 req/sec ceiling.
    def _news_priority_key(row: _CandidateRow) -> tuple:
        score = 0
        if "HELD" in row.source_tags:
            score += 100
        if "SCANNER" in row.source_tags and row.signal_strength == "high":
            score += 80
        if "SCANNER" in row.source_tags and row.signal_strength == "medium":
            score += 50
        if "RECENTLY_TRADED" in row.source_tags:
            score += 30
        if "WATCHED" in row.source_tags:
            score += 10
        return (-score, row.ticker)

    sorted_for_news = sorted(candidate_rows.values(), key=_news_priority_key)
    # Cap interactive preview fan-out at MAX_NEWS_TOP_N_INTERACTIVE.
    effective_news_top_n = max(1, min(int(news_top_n), MAX_NEWS_TOP_N_INTERACTIVE))
    news_tickers = [r.ticker for r in sorted_for_news[:effective_news_top_n]]
    requested_news_tickers: list[str] = list(news_tickers)

    # news_section_state values:
    #   ok                     — data present, no rate-limit anywhere
    #   cached                 — data present, served from cache (TTL refresh)
    #   rate_limited_cached    — at least one provider 429, but cache served data
    #   rate_limited_no_cache  — at least one provider 429 and no cached data
    #   timeout / error / empty / partial — propagated from merged_status
    #
    # Cache age is reported when any per-provider status == "cached".
    news_section_state = "ok"
    used_cached_news_count = 0
    skipped_due_to_rate_limit: list[str] = []
    cached_news_age_seconds: float | None = None

    if news_tickers:
        merged = await p.get_merged_news(
            tickers=news_tickers,
            from_date=news_from,
            to_date=news_to,
            limit_per_ticker=news_limit_per_ticker,
            fmp_news_fetcher=fmp_news_fetcher,
            polygon_news_fetcher=polygon_news_fetcher,
        )
        news_diagnostics = merged.diagnostics
        # Group news by ticker
        news_by_ticker: dict[str, list[dict]] = {}
        for item in merged.merged_items:
            sym = (item.get("ticker") or "").upper()
            if sym:
                news_by_ticker.setdefault(sym, []).append(item)
        for ticker, items in news_by_ticker.items():
            row = candidate_rows.get(ticker)
            if row is not None:
                row.recent_news = items[:news_limit_per_ticker]

        # Derive brief-level news section state. The per-provider
        # ProviderResult.status of "cached" means stale-on-refresh-fail
        # served the prior payload. providers.py was extended to fall
        # back on status="rate_limited" too — when that happens, the
        # status flips to "cached" but the note string preserves the
        # original cause as e.g. "refresh failed (rate_limited), serving
        # stale cache". We inspect that note to surface
        # "rate_limited_cached" instead of plain "cached".
        fmp_status = merged.fmp.status
        polygon_status = merged.polygon.status
        fmp_note = (merged.fmp.note or "")
        polygon_note = (merged.polygon.note or "")
        any_cached = "cached" in (fmp_status, polygon_status)
        any_rate_limited = "rate_limited" in (fmp_status, polygon_status)
        # Cache fallback that was specifically caused by a rate-limit
        # response on this fetch attempt.
        rl_caused_cache = (
            (fmp_status == "cached" and "rate_limited" in fmp_note)
            or (polygon_status == "cached" and "rate_limited" in polygon_note)
        )
        any_data = bool(merged.merged_items)

        # Estimate "used cached news count" — the number of items that
        # came from a cached provider. Conservative: if either provider
        # is "cached" we count ALL items it contributed.
        if any_cached:
            for item in merged.merged_items:
                provider = item.get("provider")
                if provider == "fmp" and fmp_status == "cached":
                    used_cached_news_count += 1
                elif provider == "polygon" and polygon_status == "cached":
                    used_cached_news_count += 1

        # Cache age — older of the cached providers' fetched_at.
        cached_fetched_ats: list[float] = []
        if fmp_status == "cached" and merged.fmp.fetched_at:
            cached_fetched_ats.append(merged.fmp.fetched_at)
        if polygon_status == "cached" and merged.polygon.fetched_at:
            cached_fetched_ats.append(merged.polygon.fetched_at)
        if cached_fetched_ats:
            import time as _time
            cached_news_age_seconds = max(
                0.0,
                _time.time() - min(cached_fetched_ats),
            )

        # Skipped due to rate-limit: the brief consumes merged news
        # already, so the "skipped" set is the requested tickers that
        # appear in NEITHER returned provider, IF the merged status is
        # rate_limited (no cache to fall back on).
        if any_rate_limited and not any_data:
            skipped_due_to_rate_limit = list(requested_news_tickers)

        if any_rate_limited and any_data:
            # One provider rate_limited (no cache available for it) but
            # the OTHER provided data — surface the rate-limit signal so
            # the user sees the partial-cache messaging.
            news_section_state = "rate_limited_cached"
        elif any_rate_limited and not any_data:
            news_section_state = "rate_limited_no_cache"
        elif rl_caused_cache and any_data:
            # Cache fallback was triggered specifically because the
            # provider returned 429 — show the rate-limit messaging so
            # the user understands news is from cache, not fresh.
            news_section_state = "rate_limited_cached"
        elif any_cached and any_data:
            news_section_state = "cached"
        else:
            # Otherwise mirror merged_status (ok / empty / unavailable / timeout / error / partial)
            news_section_state = merged.merged_status
    else:
        news_diagnostics = {
            "fmp": {"status": "ok", "raw_count": 0, "parsed_count": 0,
                    "skipped_count": 0, "note": "no tickers in scope", "error": None},
            "polygon": {"status": "ok", "raw_count": 0, "parsed_count": 0,
                        "skipped_count": 0, "note": "no tickers in scope", "error": None},
            "merged": {"status": "empty", "pre_dedup_count": 0,
                       "deduped_count": 0, "dropped_duplicates": 0},
        }
        news_section_state = "empty"

    # ---------- 7. Earnings fan-out (per-symbol, top-N) ----------
    if news_tickers:
        earnings_result = await p.get_upcoming_earnings_for_tickers(
            news_tickers,
            today=today,
            horizon_days=days,
            fmp_per_symbol_fetcher=fmp_per_symbol_fetcher,
        )
        earnings_status = earnings_result.status
        earnings_by_ticker: dict[str, list[dict]] = {}
        for raw in earnings_result.data or []:
            if isinstance(raw, dict):
                sym = str(raw.get("symbol") or "").upper()
                if sym:
                    earnings_by_ticker.setdefault(sym, []).append(raw)
        for ticker, items in earnings_by_ticker.items():
            row = candidate_rows.get(ticker)
            if row is not None:
                row.upcoming_earnings = items
    else:
        earnings_status = "ok"

    # ---------- 8. Compute research_priority ----------
    for row in candidate_rows.values():
        priority = PRIORITY_LOWEST
        if "HELD" in row.source_tags:
            priority = max(priority, PRIORITY_LOW)
        if "SCANNER" in row.source_tags:
            if row.signal_strength == "high":
                priority = max(priority, PRIORITY_HIGH)
            elif row.signal_strength == "medium":
                priority = max(priority, PRIORITY_MEDIUM)
            else:
                priority = max(priority, PRIORITY_LOW)
        if row.recent_news:
            priority = max(priority, PRIORITY_MEDIUM)
        if row.upcoming_earnings:
            priority = max(priority, PRIORITY_MEDIUM)
        # Highest: held + has news + scanner candidate
        if (
            "HELD" in row.source_tags
            and row.recent_news
            and "SCANNER" in row.source_tags
        ):
            priority = PRIORITY_HIGHEST
        # Highest also: held + upcoming earnings within window
        if "HELD" in row.source_tags and row.upcoming_earnings:
            priority = max(priority, PRIORITY_HIGH)
        row.research_priority = priority

    # ---------- 9. Build derived sections ----------
    all_rows = sorted(
        candidate_rows.values(),
        key=lambda r: (-r.research_priority, r.ticker),
    )

    top_price_anomaly_candidates = sorted(
        [r for r in all_rows if "SCANNER" in r.source_tags],
        key=lambda r: (
            -(r.research_priority),
            -(abs(r.change_1d_pct) if r.change_1d_pct is not None else 0),
            r.ticker,
        ),
    )[:10]

    top_news_linked_candidates = sorted(
        [r for r in all_rows if r.recent_news],
        key=lambda r: (-r.research_priority, -len(r.recent_news or []), r.ticker),
    )[:10]

    earnings_nearby_candidates = sorted(
        [r for r in all_rows if r.upcoming_earnings],
        key=lambda r: (-r.research_priority, r.ticker),
    )[:10]

    unmapped_candidates = sorted(
        [r for r in all_rows
         if r.mapping_status in ("unmapped", "unresolved", "newly_resolvable")],
        key=lambda r: (
            0 if r.mapping_status == "newly_resolvable" else 1,
            r.ticker,
        ),
    )[:20]

    # Categories summary
    categories_summary: dict[str, dict] = {}
    for row in all_rows:
        broad = row.taxonomy_broad or "Uncategorized"
        bucket = categories_summary.setdefault(broad, {
            "broad": broad,
            "ticker_count": 0,
            "tickers": [],
            "subs": {},
        })
        bucket["ticker_count"] += 1
        if len(bucket["tickers"]) < 10:
            bucket["tickers"].append(row.ticker)
        for sub in row.taxonomy_subs:
            bucket["subs"][sub] = bucket["subs"].get(sub, 0) + 1
    categories_summary_list = sorted(
        categories_summary.values(),
        key=lambda b: (-b["ticker_count"], b["broad"]),
    )

    # Enrich news diagnostics with brief-level fan-out + cache fields so
    # the UI can render "Using cached news from X minutes ago" and
    # rate-limited messaging without inferring it from raw counts.
    enriched_news_diagnostics = dict(news_diagnostics)
    enriched_news_diagnostics["section_state"] = news_section_state
    enriched_news_diagnostics["requested_news_tickers"] = list(requested_news_tickers)
    enriched_news_diagnostics["effective_news_top_n"] = effective_news_top_n
    enriched_news_diagnostics["requested_news_top_n"] = int(news_top_n)
    enriched_news_diagnostics["used_cached_news_count"] = used_cached_news_count
    enriched_news_diagnostics["skipped_due_to_rate_limit"] = list(skipped_due_to_rate_limit)
    enriched_news_diagnostics["cached_news_age_seconds"] = (
        round(cached_news_age_seconds, 1)
        if cached_news_age_seconds is not None else None
    )

    return {
        "generated_at": utc_now().isoformat(),
        "universe_scope": {
            "scanner_universe": "scanner-research-36",
            "scanner_matched": scanner_response.get("matched", 0),
            "scanner_scanned": scanner_response.get("scanned", 0),
            "mirror_ticker_count": len(mirror_index),
            "merged_ticker_count": len(candidate_rows),
            "news_fanout_top_n": len(news_tickers),
            "effective_news_top_n": effective_news_top_n,
            "requested_news_top_n": int(news_top_n),
            "days_window": days,
        },
        "ticker_count": len(candidate_rows),
        "candidates": [r.to_dict() for r in all_rows[:scanner_limit]],
        "top_price_anomaly_candidates": [r.to_dict() for r in top_price_anomaly_candidates],
        "top_news_linked_candidates": [r.to_dict() for r in top_news_linked_candidates],
        "earnings_nearby_candidates": [r.to_dict() for r in earnings_nearby_candidates],
        "unmapped_candidates": [r.to_dict() for r in unmapped_candidates],
        "categories_summary": categories_summary_list,
        "provider_diagnostics": {
            "scanner": {
                "scanned": scanner_response.get("scanned", 0),
                "matched": scanner_response.get("matched", 0),
                "as_of": scanner_response.get("as_of"),
            },
            "news": enriched_news_diagnostics,
            "earnings_status": earnings_status,
        },
        "side_effects": {
            "db_writes": "NONE",
            "broker_writes": "NONE",
            "execution_objects": "NONE",
            "live_submit": "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)",
            "scheduler_changes": "NONE",
        },
        "disclaimer": DISCLAIMER,
    }
