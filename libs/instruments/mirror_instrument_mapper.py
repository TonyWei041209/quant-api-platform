"""Auto Instrument Mapper / Mirror Universe Bootstrap planner.

Discovers tickers that appear in the Trading 212 Mirror watchlist (held +
recently traded + manually watched) and classifies each one's mapping
status against the platform instrument master:

  - mapped              : already has an instrument_identifier (id_type='ticker')
                          row OR a ticker_history row → research path
                          already works.
  - unmapped            : not yet in the master, no provider lookup tried
                          yet (fetch_profiles=False).
  - newly_resolvable    : not yet in the master, FMP profile API returned
                          enough fields to bootstrap on next write.
  - unresolved          : not yet in the master, FMP profile failed or
                          returned nothing.
  - ambiguous           : reserved for future use (multiple plausible
                          provider matches); treated like 'unresolved'
                          in this phase so callers don't accidentally
                          create wrong-issuer rows.

The actual write path (creating instrument + instrument_identifier +
ticker_history rows) is delegated to the well-tested
``libs.ingestion.bootstrap_research_universe_prod`` module — same
four-flag handshake (write_mode + confirm_production_write + db_target
+ CLI flag), same per-ticker isolation, same FMP fallback rules.

This module:
  - never writes the database in plan mode
  - never calls Trading 212
  - never touches order_intent / order_draft / submit objects
  - never reads or mutates FEATURE_T212_LIVE_SUBMIT
  - never scrapes or automates a browser
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Iterable, Literal

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from libs.core.time import utc_now


MappingStatus = Literal[
    "mapped",
    "unmapped",
    "newly_resolvable",
    "unresolved",
    "ambiguous",
]

# Tickers we will NEVER attempt to bootstrap via the mirror path because they
# already have curated rows in production (and re-bootstrapping risks
# duplicate identifier rows or shadowing the existing primary identifier).
# This mirrors libs.scanner.scanner_universe.PROTECTED_TICKERS.
PROTECTED_TICKERS = frozenset({"NVDA", "AAPL", "MSFT", "SPY"})


@dataclass
class MirrorTicker:
    """One ticker observed in the Trading 212 Mirror, before mapping."""
    display_ticker: str
    broker_ticker: str | None
    source_tags: tuple[str, ...]


@dataclass
class MirrorMappingItem:
    """Per-ticker mapping plan entry — pure data, no side effects."""
    display_ticker: str
    broker_ticker: str | None
    mapping_status: MappingStatus
    instrument_id: str | None
    company_name: str | None
    asset_type: str | None
    exchange_primary: str | None
    currency: str | None
    country_code: str | None
    provider_profile: dict | None
    provider_attempted: bool
    provider_error: str | None
    is_protected: bool
    source_tags: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "display_ticker": self.display_ticker,
            "broker_ticker": self.broker_ticker,
            "mapping_status": self.mapping_status,
            "instrument_id": self.instrument_id,
            "company_name": self.company_name,
            "asset_type": self.asset_type,
            "exchange_primary": self.exchange_primary,
            "currency": self.currency,
            "country_code": self.country_code,
            "provider_profile": self.provider_profile,
            "provider_attempted": self.provider_attempted,
            "provider_error": self.provider_error,
            "is_protected": self.is_protected,
            "source_tags": list(self.source_tags),
            "would_create": (
                {
                    "instrument": True,
                    "instrument_identifier": True,
                    "ticker_history": True,
                }
                if self.mapping_status == "newly_resolvable" else
                {
                    "instrument": False,
                    "instrument_identifier": False,
                    "ticker_history": False,
                }
            ),
        }


@dataclass
class MirrorMappingPlan:
    """Aggregate plan output. Pure data, no side effects."""
    generated_at: datetime
    source: str
    dry_run: bool
    fetch_profiles: bool
    items: list[MirrorMappingItem] = field(default_factory=list)

    @property
    def counts(self) -> dict:
        c = {
            "total": len(self.items),
            "mapped": 0,
            "unmapped": 0,
            "newly_resolvable": 0,
            "unresolved": 0,
            "ambiguous": 0,
            "protected_excluded": 0,
        }
        for it in self.items:
            c[it.mapping_status] = c.get(it.mapping_status, 0) + 1
            if it.is_protected:
                c["protected_excluded"] += 1
        return c

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(),
            "source": self.source,
            "dry_run": self.dry_run,
            "fetch_profiles": self.fetch_profiles,
            "counts": self.counts,
            "items": [it.to_dict() for it in self.items],
            "side_effects": {
                "db_writes": "NONE",
                "broker_writes": "NONE",
                "execution_objects": "NONE",
                "live_submit": "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)",
            },
        }


# ---------------------------------------------------------------------------
# Existing-mapping lookup (read-only)
# ---------------------------------------------------------------------------


def _lookup_existing_mappings(
    db: Session, display_tickers: Iterable[str]
) -> dict[str, dict]:
    """For each display ticker, return existing mapping info if any.

    Looks at instrument_identifier (id_type='ticker') primary, falls back
    to ticker_history. Returns dict keyed by uppercase ticker:
    {
       "TICKER": {
            "instrument_id": "uuid-string",
            "company_name": "...",
            "asset_type": "EQUITY",
            "exchange_primary": "NASDAQ",
            "currency": "USD",
            "country_code": "US",
       }, ...
    }
    """
    tickers = sorted({t.upper() for t in display_tickers if t})
    if not tickers:
        return {}

    rows = db.execute(
        sql_text(
            """
            SELECT ii.id_value AS ticker,
                   ii.instrument_id::text AS instrument_id,
                   i.issuer_name_current AS company_name,
                   i.asset_type AS asset_type,
                   i.exchange_primary AS exchange_primary,
                   i.currency AS currency,
                   i.country_code AS country_code
            FROM instrument_identifier ii
            JOIN instrument i ON i.instrument_id = ii.instrument_id
            WHERE ii.id_type = 'ticker' AND ii.id_value = ANY(:tickers)
            """
        ),
        {"tickers": tickers},
    ).fetchall()
    by_ticker: dict[str, dict] = {}
    for r in rows:
        by_ticker[r[0].upper()] = {
            "instrument_id": r[1],
            "company_name": r[2],
            "asset_type": r[3],
            "exchange_primary": r[4],
            "currency": r[5],
            "country_code": r[6],
        }

    # Fallback: ticker_history (for tickers that exist but only via history)
    missing = [t for t in tickers if t not in by_ticker]
    if missing:
        rows2 = db.execute(
            sql_text(
                """
                SELECT th.ticker AS ticker,
                       th.instrument_id::text AS instrument_id,
                       i.issuer_name_current AS company_name,
                       i.asset_type AS asset_type,
                       i.exchange_primary AS exchange_primary,
                       i.currency AS currency,
                       i.country_code AS country_code
                FROM ticker_history th
                JOIN instrument i ON i.instrument_id = th.instrument_id
                WHERE th.ticker = ANY(:tickers)
                  AND (th.effective_to IS NULL OR th.effective_to > CURRENT_DATE)
                """
            ),
            {"tickers": missing},
        ).fetchall()
        for r in rows2:
            by_ticker[r[0].upper()] = {
                "instrument_id": r[1],
                "company_name": r[2],
                "asset_type": r[3],
                "exchange_primary": r[4],
                "currency": r[5],
                "country_code": r[6],
            }
    return by_ticker


# ---------------------------------------------------------------------------
# FMP profile derivation (read-only)
# ---------------------------------------------------------------------------


def _profile_to_fields(ticker: str, raw: dict | None) -> dict:
    """Map an FMP profile dict to the four scaffolding fields.

    Returns {company_name, exchange_primary, currency, country_code,
    asset_type}. None values mean "FMP didn't supply this field" — caller
    decides whether to fall back to deterministic defaults.
    """
    if not isinstance(raw, dict) or not raw:
        return {
            "company_name": None,
            "exchange_primary": None,
            "currency": None,
            "country_code": None,
            "asset_type": None,
        }
    is_etf = bool(raw.get("isEtf") or (raw.get("type", "").lower() == "etf"))
    return {
        "company_name": raw.get("companyName") or raw.get("name") or None,
        "exchange_primary": (
            raw.get("exchangeShortName")
            or raw.get("exchange")
            or None
        ),
        "currency": raw.get("currency") or None,
        "country_code": raw.get("country") or None,
        "asset_type": "ETF" if is_etf else "EQUITY",
    }


# ---------------------------------------------------------------------------
# Plan builder (the main public API)
# ---------------------------------------------------------------------------


async def build_mirror_mapping_plan(
    db: Session,
    *,
    fetch_profiles: bool = False,
    include_recent_orders: bool = True,
    recent_lookback_days: int = 7,
    manual_tickers: Iterable[str] | None = None,
    fmp_profile_fetcher: Callable[[str], Awaitable[dict | None]] | None = None,
) -> MirrorMappingPlan:
    """Compose a mapping plan for the Trading 212 Mirror tickers.

    Pure read-only. Never writes the database. ``fmp_profile_fetcher`` is
    injectable for tests; in production callers should pass a function that
    wraps ``FMPAdapter.get_profile`` (so this module never imports the
    adapter directly and stays fully testable).
    """
    # Local import to avoid an import cycle at module load time.
    from libs.portfolio.mirror_watchlist_service import build_mirror_watchlist

    mirror = build_mirror_watchlist(
        db,
        manual_tickers=manual_tickers,
        include_recent_orders=include_recent_orders,
        recent_lookback_days=recent_lookback_days,
    )

    raw_items = mirror.get("items", [])
    mirror_tickers: list[MirrorTicker] = []
    for it in raw_items:
        display = (it.get("display_ticker") or "").upper()
        if not display:
            continue
        mirror_tickers.append(MirrorTicker(
            display_ticker=display,
            broker_ticker=it.get("broker_ticker"),
            source_tags=tuple(it.get("source_tags") or ()),
        ))

    existing = _lookup_existing_mappings(
        db, [mt.display_ticker for mt in mirror_tickers]
    )

    items: list[MirrorMappingItem] = []
    for mt in mirror_tickers:
        is_protected = mt.display_ticker in PROTECTED_TICKERS
        existing_row = existing.get(mt.display_ticker)

        if existing_row:
            items.append(MirrorMappingItem(
                display_ticker=mt.display_ticker,
                broker_ticker=mt.broker_ticker,
                mapping_status="mapped",
                instrument_id=existing_row["instrument_id"],
                company_name=existing_row["company_name"],
                asset_type=existing_row["asset_type"],
                exchange_primary=existing_row["exchange_primary"],
                currency=existing_row["currency"],
                country_code=existing_row["country_code"],
                provider_profile=None,
                provider_attempted=False,
                provider_error=None,
                is_protected=is_protected,
                source_tags=mt.source_tags,
            ))
            continue

        if not fetch_profiles or fmp_profile_fetcher is None:
            items.append(MirrorMappingItem(
                display_ticker=mt.display_ticker,
                broker_ticker=mt.broker_ticker,
                mapping_status="unmapped",
                instrument_id=None,
                company_name=None,
                asset_type=None,
                exchange_primary=None,
                currency=None,
                country_code=None,
                provider_profile=None,
                provider_attempted=False,
                provider_error=None,
                is_protected=is_protected,
                source_tags=mt.source_tags,
            ))
            continue

        # Fetch FMP profile (one call per unmapped ticker)
        provider_error: str | None = None
        raw_profile: dict | None = None
        try:
            raw_profile = await fmp_profile_fetcher(mt.display_ticker)
        except Exception as exc:  # noqa: BLE001
            provider_error = f"{type(exc).__name__}: {exc}"
            raw_profile = None

        fields = _profile_to_fields(mt.display_ticker, raw_profile)
        if fields["company_name"]:
            status: MappingStatus = "newly_resolvable"
        else:
            status = "unresolved"

        items.append(MirrorMappingItem(
            display_ticker=mt.display_ticker,
            broker_ticker=mt.broker_ticker,
            mapping_status=status,
            instrument_id=None,
            company_name=fields["company_name"],
            asset_type=fields["asset_type"],
            exchange_primary=fields["exchange_primary"],
            currency=fields["currency"],
            country_code=fields["country_code"],
            provider_profile=raw_profile,
            provider_attempted=True,
            provider_error=provider_error,
            is_protected=is_protected,
            source_tags=mt.source_tags,
        ))

    return MirrorMappingPlan(
        generated_at=utc_now(),
        source="trading212_mirror",
        dry_run=True,
        fetch_profiles=fetch_profiles,
        items=items,
    )


# ---------------------------------------------------------------------------
# Plan-time guards used by tests and the CLI
# ---------------------------------------------------------------------------


def filter_for_bootstrap(plan: MirrorMappingPlan) -> tuple[str, ...]:
    """Return the tuple of tickers eligible for the existing
    ``bootstrap_research_universe_prod.execute_bootstrap`` write path.

    Eligibility rules:
      - mapping_status must be 'newly_resolvable' (we have provider data)
      - is_protected must be False (defense-in-depth)
      - the existing bootstrap module also re-checks the protected set
        and re-checks existing identifiers, so this is purely a
        readability filter and cannot weaken the guarantees.

    Pure data — no DB, no network.
    """
    return tuple(
        it.display_ticker
        for it in plan.items
        if it.mapping_status == "newly_resolvable" and not it.is_protected
    )


def render_mapping_plan_report(plan: MirrorMappingPlan) -> str:
    """Human-readable plan summary. Pure string output. No side effects."""
    counts = plan.counts
    lines = []
    lines.append("=" * 78)
    lines.append("  MIRROR INSTRUMENT MAPPING PLAN")
    if plan.dry_run:
        lines.append("  DRY RUN — NO DB WRITES — NO PROVIDER WRITES")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"  generated_at         : {plan.generated_at.isoformat()}")
    lines.append(f"  source               : {plan.source}")
    lines.append(f"  fetch_profiles       : {plan.fetch_profiles}")
    lines.append("")
    lines.append("  counts:")
    for k in ("total", "mapped", "unmapped", "newly_resolvable",
              "unresolved", "ambiguous", "protected_excluded"):
        lines.append(f"    {k:22s}: {counts.get(k, 0)}")
    lines.append("")
    if plan.items:
        lines.append("  per-ticker (first 20):")
        for it in plan.items[:20]:
            tags = ",".join(it.source_tags) or "—"
            extra = ""
            if it.mapping_status == "newly_resolvable":
                extra = f"  → '{it.company_name}'  ({it.exchange_primary or '?'} / {it.currency or '?'})"
            elif it.mapping_status == "mapped":
                extra = f"  → '{it.company_name}'  [existing]"
            elif it.mapping_status == "unresolved" and it.provider_error:
                extra = f"  → provider error: {it.provider_error[:40]}"
            lines.append(
                f"    {it.display_ticker:8s} "
                f"{it.mapping_status:18s} "
                f"tags={tags:30s}{extra}"
            )
    lines.append("")
    lines.append("  Side-effect attestations:")
    lines.append("    DB writes performed   : NONE")
    lines.append("    Broker writes         : NONE")
    lines.append("    Execution objects     : NONE")
    lines.append("    Live submit           : LOCKED (FEATURE_T212_LIVE_SUBMIT=false)")
    lines.append("")
    lines.append("  Production write requires the four-flag handshake on the")
    lines.append("  CLI: --no-dry-run --write --db-target=production")
    lines.append("       --confirm-production-write")
    lines.append("=" * 78)
    return "\n".join(lines)
