"""Production bootstrap planner — scaffolding rows for Scanner Research Universe.

================================================================================
DRY-RUN FIRST. PRODUCTION WRITES REQUIRE FOUR EXPLICIT FLAGS.
================================================================================

This module bootstraps the **scaffolding** (instrument + instrument_identifier
+ ticker_history) for the 32 tickers that did NOT have parent rows when the
B2 EOD seed ran. Without these rows, ``sync_eod_prices_universe.execute_sync``
correctly refuses the tickers because their ``instrument_id`` cannot be
resolved.

This module is INTENTIONALLY NARROW. It DOES NOT touch:
  - ``price_bar_raw`` (handled by ``sync_eod_prices_universe``)
  - ``corporate_action`` / ``earnings_event`` / financial-fact tables
  - ``watchlist_*`` tables
  - any broker / execution / order_intent / order_draft objects
  - the Trading 212 readonly snapshots

The four-flag handshake is identical to ``sync_eod_prices_universe``:
  - ``write_mode == "WRITE_PRODUCTION"``
  - ``confirm_production_write is True``
  - ``plan.db_target == "production"`` (URL classifies as Cloud SQL OR
    ``DB_TARGET_OVERRIDE=production``)
  - CLI passed ``--no-dry-run --write --db-target=production
    --confirm-production-write``

Source policy:
  - FMP profile API for issuer name / exchange / currency / country
  - **yfinance_dev MUST NOT appear here** — yfinance is dev-only by project
    policy (see ``scripts/bootstrap_research_universe_dev.py`` for the dev
    path)
  - Polygon and Trading 212 are NOT consulted here — bootstrap is an
    instrument-master operation, not a price/quote operation
  - When FMP returns missing fields, fallbacks are deterministic:
      issuer_name_current → ticker symbol
      exchange_primary    → "UNKNOWN"
      currency            → "USD"
      country_code        → "US"

Per-ticker isolation: failure of one ticker (FMP error, DB conflict, etc.)
does NOT abort the rest. Each successful ticker commits its own transaction;
each failure rolls back only its own transaction.

Idempotency: bootstrap uses ``INSERT ... ON CONFLICT DO NOTHING`` semantics
via composite-key inserts. Tickers that already have an instrument_identifier
row (id_type='ticker') are skipped at planning time and never touched.

Guardrails:
  - Protected tickers (NVDA / AAPL / MSFT / SPY) are HARD-EXCLUDED from the
    plan even if explicitly requested via ``tickers=`` argument
  - No execution objects (intent / draft / order)
  - No broker write
  - No live submit changes
  - No yfinance_dev usage
  - DB target verification before any write
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Awaitable, Callable, Literal, Optional


# Default pacing between FMP profile calls (FMP free tier is more permissive
# than Polygon free tier; 1 s is conservative and finishes 32 tickers in ~32 s)
DEFAULT_FMP_DELAY_SECONDS = 1.0

# Effective_from / valid_from anchor for new bootstrap rows. Matches the dev
# bootstrap and avoids "now()" which would be non-deterministic across reruns.
DEFAULT_EFFECTIVE_FROM = date(2020, 1, 1)


WriteMode = Literal["DRY_RUN", "WRITE_LOCAL", "WRITE_PRODUCTION"]
DbTarget = Literal["local", "production", "unknown"]


@dataclass
class TickerBootstrap:
    """Per-ticker bootstrap descriptor — pure data, no side effects."""
    ticker: str
    already_exists: bool  # True if instrument_identifier row was found at plan time
    asset_type: str  # "EQUITY" or "ETF"
    note: str  # Human-readable status: "scaffold needed", "already scaffolded", "PROTECTED"


@dataclass
class BootstrapPlan:
    """Aggregate plan for a bootstrap run. Pure data — no side effects."""
    universe_name: str
    target_tickers: tuple[str, ...]  # Final target after protected exclusion
    requested_tickers: tuple[str, ...]  # What the caller originally asked for
    protected_excluded: tuple[str, ...]  # Tickers removed because they are protected
    write_mode: WriteMode
    db_target: DbTarget
    db_url_label: str
    fmp_delay_seconds: float
    effective_from: date
    today: date
    per_ticker: list[TickerBootstrap] = field(default_factory=list)

    @property
    def estimated_fmp_calls(self) -> int:
        """One profile call per ticker that actually needs scaffolding.
        Already-scaffolded tickers are skipped at execute time."""
        return sum(1 for p in self.per_ticker if not p.already_exists)

    @property
    def estimated_runtime_seconds(self) -> float:
        return self.estimated_fmp_calls * self.fmp_delay_seconds

    @property
    def banned_phrases_check(self) -> list[str]:
        """Plan descriptors must contain no trading-action language."""
        haystack = " ".join([
            self.universe_name, self.write_mode, self.db_target,
        ]).lower()
        banned = [
            "buy", "sell", "enter long", "enter short", "target price",
            "position size", "leverage", "guaranteed",
        ]
        return [b for b in banned if b in haystack]


# ---------------------------------------------------------------------------
# DB target classification — mirrors sync_eod_prices_universe semantics so the
# operator only has to learn one model.
# ---------------------------------------------------------------------------


def _classify_db_url(url_str: str) -> DbTarget:
    """Classify a DB URL as local / production / unknown.

    Resolution order:
      1. ``DB_TARGET_OVERRIDE`` environment variable, if set, takes
         precedence. Allowed values: "local", "production".
      2. URL pattern: localhost/127.0.0.1 → local; cloudsql/`/cloudsql/`
         → production; otherwise unknown.

    See ``libs.ingestion.sync_eod_prices_universe._classify_db_url`` for the
    reasoning behind the override mechanism (production Cloud SQL
    sometimes uses public-IP form ``host=34.x.x.x`` which does not pattern-
    match as cloudsql).
    """
    import os
    override = os.environ.get("DB_TARGET_OVERRIDE", "").strip().lower()
    if override:
        if override == "local":
            return "local"
        if override == "production":
            return "production"
        raise ValueError(
            f"DB_TARGET_OVERRIDE must be 'local' or 'production' (or unset), "
            f"got '{override}'. Refusing to proceed with ambiguous classification."
        )

    s = url_str.lower()
    if "localhost" in s or "127.0.0.1" in s:
        return "local"
    if "/cloudsql/" in s or "cloudsql" in s:
        return "production"
    return "unknown"


def _resolve_db_target_label(session_or_engine) -> tuple[DbTarget, str]:
    """Read-only DB URL inspection. Never logs the password."""
    import os
    override = os.environ.get("DB_TARGET_OVERRIDE", "").strip().lower()
    try:
        url = session_or_engine.get_bind().url if hasattr(session_or_engine, "get_bind") \
            else session_or_engine.url
        url_str = str(url)
        import re
        masked = re.sub(r":[^:@]+@", ":***@", url_str)
        target = _classify_db_url(url_str)
        if override:
            masked = f"{masked} (via DB_TARGET_OVERRIDE={override})"
        return target, masked
    except Exception:
        if override:
            target = _classify_db_url("")
            return target, f"(unable to inspect URL; override={override})"
        return "unknown", "(unable to inspect)"


# ---------------------------------------------------------------------------
# Existing-instrument lookup
# ---------------------------------------------------------------------------


def _existing_ticker_set(session, tickers: tuple[str, ...]) -> set[str]:
    """Read-only: which of the requested tickers already have an
    instrument_identifier row (id_type='ticker')?"""
    if not tickers:
        return set()
    from sqlalchemy import text
    rows = session.execute(
        text(
            """
            SELECT DISTINCT id_value
            FROM instrument_identifier
            WHERE id_type = 'ticker' AND id_value = ANY(:tickers)
            """
        ),
        {"tickers": list(tickers)},
    ).fetchall()
    return {r[0] for r in rows if r[0]}


# ---------------------------------------------------------------------------
# Plan building
# ---------------------------------------------------------------------------


def build_bootstrap_plan(
    *,
    universe_name: str,
    tickers: tuple[str, ...],
    write_mode: WriteMode,
    confirm_production_write: bool,
    fmp_delay_seconds: float = DEFAULT_FMP_DELAY_SECONDS,
    effective_from: date = DEFAULT_EFFECTIVE_FROM,
    session=None,
    today: date | None = None,
) -> BootstrapPlan:
    """Compute a bootstrap plan. PURE PLANNING — no DB writes, no API calls.

    Protected tickers are removed from the target list at this layer; even if
    a caller passes them in explicitly, the plan will not include them.

    If ``session`` is provided, the planner queries which tickers already have
    instrument_identifier rows and marks those as ``already_exists=True`` so
    execute_bootstrap can skip them.
    """
    from libs.scanner.scanner_universe import (
        PROTECTED_TICKERS,
        asset_type_for,
    )

    today = today or date.today()

    # Normalize input
    requested = tuple(t.upper() for t in tickers)

    # Filter out protected tickers — defense-in-depth at plan time
    protected_excluded = tuple(t for t in requested if t in PROTECTED_TICKERS)
    target_tickers = tuple(t for t in requested if t not in PROTECTED_TICKERS)

    # Validate write_mode → confirm_production_write coupling
    if write_mode == "WRITE_PRODUCTION" and not confirm_production_write:
        raise ValueError(
            "WRITE_PRODUCTION requires confirm_production_write=True. "
            "Single-flag production writes are not allowed by policy."
        )

    # Identify DB target if session present
    if session is not None:
        db_target, db_url_label = _resolve_db_target_label(session)
        existing = _existing_ticker_set(session, target_tickers)
    else:
        db_target, db_url_label = "unknown", "(no session — pure dry-run)"
        existing = set()

    # Refuse production writes against non-production DB target
    if write_mode == "WRITE_PRODUCTION" and db_target != "production":
        raise ValueError(
            f"WRITE_PRODUCTION requested but db_target={db_target}. Refusing."
        )
    # Refuse local writes against non-local DB target
    if write_mode == "WRITE_LOCAL" and db_target != "local":
        raise ValueError(
            f"WRITE_LOCAL requested but db_target={db_target}. Refusing."
        )

    per_ticker: list[TickerBootstrap] = []
    for tkr in target_tickers:
        already = tkr in existing
        per_ticker.append(TickerBootstrap(
            ticker=tkr,
            already_exists=already,
            asset_type=asset_type_for(tkr),
            note="already scaffolded" if already else "scaffold needed",
        ))

    return BootstrapPlan(
        universe_name=universe_name,
        target_tickers=target_tickers,
        requested_tickers=requested,
        protected_excluded=protected_excluded,
        write_mode=write_mode,
        db_target=db_target,
        db_url_label=db_url_label,
        fmp_delay_seconds=fmp_delay_seconds,
        effective_from=effective_from,
        today=today,
        per_ticker=per_ticker,
    )


def render_bootstrap_plan_report(plan: BootstrapPlan) -> str:
    """Build a human-readable plan summary. Pure string output. No side effects."""
    lines = []
    lines.append("=" * 78)
    lines.append("  BOOTSTRAP PLAN — universe='{u}'  mode={m}".format(
        u=plan.universe_name, m=plan.write_mode))
    if plan.write_mode == "DRY_RUN":
        lines.append("  DRY RUN — NO DB WRITES — NO API CALLS — NO CLOUD CHANGES")
    elif plan.write_mode == "WRITE_LOCAL":
        lines.append("  LOCAL WRITE MODE — would write to localhost DB only")
    elif plan.write_mode == "WRITE_PRODUCTION":
        lines.append("  PRODUCTION WRITE MODE — REQUIRES confirm_production_write=True")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"  universe                : {plan.universe_name}")
    lines.append(f"  requested_count         : {len(plan.requested_tickers)}")
    lines.append(f"  protected_excluded      : {len(plan.protected_excluded)}  "
                 f"({', '.join(plan.protected_excluded) or '—'})")
    lines.append(f"  target_count            : {len(plan.target_tickers)}")
    lines.append(f"  primary_source          : fmp (profile API)")
    lines.append(f"  yfinance_dev allowed    : NO (dev-only path; forbidden in production bootstrap)")
    lines.append(f"  fmp_delay_seconds       : {plan.fmp_delay_seconds:.1f}")
    lines.append(f"  effective_from          : {plan.effective_from.isoformat()}")
    lines.append(f"  estimated_fmp_calls     : {plan.estimated_fmp_calls}")
    lines.append(f"  estimated_runtime_secs  : {plan.estimated_runtime_seconds:.0f}  "
                 f"(~{plan.estimated_runtime_seconds/60:.2f} min)")
    lines.append(f"  today                   : {plan.today.isoformat()}")
    lines.append("")
    lines.append(f"  db_target               : {plan.db_target}")
    lines.append(f"  db_url_label            : {plan.db_url_label}")
    lines.append("")
    needs_scaffold = sum(1 for p in plan.per_ticker if not p.already_exists)
    already = len(plan.per_ticker) - needs_scaffold
    lines.append("  per-ticker plan:")
    lines.append(f"    needs scaffolding         : {needs_scaffold}")
    lines.append(f"    already scaffolded (skip) : {already}")
    if plan.per_ticker:
        lines.append("    sample (first 5):")
        for p in plan.per_ticker[:5]:
            status = "SCAFFOLD" if not p.already_exists else "SKIP_EXISTS"
            lines.append(
                f"      {p.ticker:6s} {status:11s} asset_type={p.asset_type}  ({p.note})"
            )
    lines.append("")
    lines.append("  Tables to be written (when not DRY_RUN):")
    lines.append("    instrument              : new row per scaffolded ticker")
    lines.append("    instrument_identifier   : 1 row per ticker (id_type='ticker')")
    lines.append("    ticker_history          : 1 row per ticker")
    lines.append("")
    lines.append("  Tables NOT touched by this module:")
    lines.append("    price_bar_raw           : NO  (handled by sync_eod_prices_universe)")
    lines.append("    corporate_action        : NO")
    lines.append("    earnings_event          : NO")
    lines.append("    financial_fact_std      : NO")
    lines.append("    watchlist_*             : NO")
    lines.append("    broker_*                : NO")
    lines.append("    order_intent / order_draft : NO")
    lines.append("")
    lines.append("  Side-effect summary:")
    lines.append(f"    DB writes performed     : NONE  (this module is plan-only "
                 "until execute_bootstrap is called)")
    lines.append(f"    Cloud Run jobs created  : NONE")
    lines.append(f"    Scheduler changes       : NONE")
    lines.append(f"    Production deploy       : NONE")
    lines.append(f"    Execution objects       : NONE  (Layer 1 Research-open)")
    lines.append(f"    Broker write            : NONE")
    lines.append(f"    Live submit             : LOCKED (FEATURE_T212_LIVE_SUBMIT=false)")
    lines.append("")
    lines.append("  Banned-phrase check on plan descriptors: " +
                 ("NONE" if not plan.banned_phrases_check else f"VIOLATIONS: {plan.banned_phrases_check}"))
    lines.append("")
    lines.append("  Production bootstrap: see")
    lines.append("    docs/scanner-research-universe-production-plan.md Section B3")
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class TickerBootstrapResult:
    """Per-ticker outcome from execute_bootstrap."""
    ticker: str
    instrument_id: str | None
    asset_type: str
    issuer_name: str | None
    exchange: str | None
    currency: str | None
    country_code: str | None
    fmp_attempted: bool
    fmp_error: str | None
    used_fallback_issuer: bool
    used_fallback_exchange: bool
    used_fallback_currency: bool
    used_fallback_country: bool
    skipped_existing: bool  # True if ticker already had instrument_identifier
    written: bool  # True if instrument + identifier + history all inserted
    runtime_seconds: float


@dataclass
class BootstrapResult:
    """Aggregate result of an execute_bootstrap run."""
    mode: WriteMode
    db_target: DbTarget
    db_url_label: str
    universe_name: str
    requested_count: int
    target_count: int
    succeeded: list[str]
    skipped_already_exists: list[str]
    failed: list[tuple[str, str]]  # (ticker, last_error)
    instruments_inserted: int
    identifiers_inserted: int
    ticker_histories_inserted: int
    runtime_seconds: float
    per_ticker: list[TickerBootstrapResult]
    # Side-effect attestations — explicit string values for log + test pinning
    db_writes_performed: str = "instrument + instrument_identifier + ticker_history only (LOCAL)"
    cloud_run_jobs_created: str = "NONE"
    scheduler_changes: str = "NONE"
    production_deploy: str = "NONE"
    execution_objects: str = "NONE"
    broker_write: str = "NONE"
    live_submit: str = "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)"


def render_bootstrap_result(res: BootstrapResult) -> str:
    """Human-readable bootstrap result. Pure string, no side effects."""
    lines = []
    lines.append("=" * 78)
    lines.append(f"  BOOTSTRAP RESULT — universe='{res.universe_name}'  mode={res.mode}")
    lines.append("=" * 78)
    lines.append(f"  requested_count               : {res.requested_count}")
    lines.append(f"  target_count                  : {res.target_count}")
    lines.append(f"  succeeded                     : {len(res.succeeded)}")
    lines.append(f"  skipped (already existed)     : {len(res.skipped_already_exists)}")
    lines.append(f"  failed                        : {len(res.failed)}")
    lines.append(f"  instruments_inserted          : {res.instruments_inserted}")
    lines.append(f"  identifiers_inserted          : {res.identifiers_inserted}")
    lines.append(f"  ticker_histories_inserted     : {res.ticker_histories_inserted}")
    lines.append(f"  runtime_seconds               : {res.runtime_seconds:.1f}")
    lines.append(f"  db_target                     : {res.db_target}")
    lines.append(f"  db_url_label                  : {res.db_url_label}")
    lines.append("")
    lines.append("  Side-effect attestations:")
    lines.append(f"    DB writes performed          : {res.db_writes_performed}")
    lines.append(f"    Cloud Run jobs created       : {res.cloud_run_jobs_created}")
    lines.append(f"    Scheduler changes            : {res.scheduler_changes}")
    lines.append(f"    Production deploy            : {res.production_deploy}")
    lines.append(f"    Execution objects            : {res.execution_objects}")
    lines.append(f"    Broker write                 : {res.broker_write}")
    lines.append(f"    Live submit                  : {res.live_submit}")
    if res.failed:
        lines.append("")
        lines.append("  Failed tickers:")
        for tkr, err in res.failed[:10]:
            lines.append(f"    {tkr}: {err[:80]}")
    if res.skipped_already_exists:
        lines.append("")
        lines.append(f"  Skipped (already existed): "
                     f"{', '.join(res.skipped_already_exists[:10])}"
                     + (" ..." if len(res.skipped_already_exists) > 10 else ""))
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Profile normalization with deterministic FMP fallbacks
# ---------------------------------------------------------------------------


def _normalize_profile(ticker: str, raw: dict | None) -> dict:
    """Map an FMP profile dict (or empty/None) to the four scaffolding fields.

    Deterministic fallbacks when fields are missing:
      issuer_name_current → ticker
      exchange_primary    → "UNKNOWN"
      currency            → "USD"
      country_code        → "US"

    The returned dict additionally carries flags for which fallbacks were used,
    so per-ticker results record provenance.
    """
    raw = raw or {}

    # FMP stable profile uses these field names; we accept both common spellings
    issuer = (
        raw.get("companyName")
        or raw.get("name")
        or raw.get("company_name")
        or None
    )
    exchange = (
        raw.get("exchange")
        or raw.get("exchangeShortName")
        or raw.get("primaryExchange")
        or None
    )
    currency = raw.get("currency") or raw.get("currency_code") or None
    country = raw.get("country") or raw.get("country_code") or None

    used_fallback_issuer = not bool(issuer)
    used_fallback_exchange = not bool(exchange)
    used_fallback_currency = not bool(currency)
    used_fallback_country = not bool(country)

    return {
        "issuer_name_current": issuer or ticker,
        "exchange_primary": exchange or "UNKNOWN",
        "currency": currency or "USD",
        "country_code": country or "US",
        "used_fallback_issuer": used_fallback_issuer,
        "used_fallback_exchange": used_fallback_exchange,
        "used_fallback_currency": used_fallback_currency,
        "used_fallback_country": used_fallback_country,
    }


# ---------------------------------------------------------------------------
# Default FMP profile fetcher — overridable by tests
# ---------------------------------------------------------------------------


async def _fetch_profile_via_fmp(ticker: str) -> dict | None:
    """Default FMP profile fetcher used in production. Tests pass a mock."""
    from libs.adapters.fmp_adapter import FMPAdapter

    adapter = FMPAdapter()
    try:
        return await adapter.get_profile(ticker)
    finally:
        # Defensive close — adapter may hold an aiohttp session
        close = getattr(adapter, "close", None)
        if close is not None:
            try:
                if asyncio.iscoroutinefunction(close):
                    await close()
                else:
                    close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Single-ticker scaffolding write
# ---------------------------------------------------------------------------


def _write_scaffolding_rows(
    session,
    *,
    ticker: str,
    asset_type: str,
    profile: dict,
    effective_from: date,
) -> tuple[str, int, int, int]:
    """INSERT instrument + instrument_identifier + ticker_history rows.

    Idempotent via composite-key conflict handling. Returns
    ``(instrument_id, instruments_inserted, identifiers_inserted, histories_inserted)``.
    Raises on adapter / DB errors so the caller can rollback per-ticker.
    """
    from libs.core.ids import new_id
    from libs.db.models.instrument import Instrument
    from libs.db.models.identifier import InstrumentIdentifier
    from libs.db.models.ticker_history import TickerHistory
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    iid = new_id()

    instr_stmt = pg_insert(Instrument).values(
        instrument_id=iid,
        asset_type=asset_type,
        issuer_name_current=profile["issuer_name_current"],
        exchange_primary=profile["exchange_primary"],
        currency=profile["currency"],
        country_code=profile["country_code"],
        is_active=True,
    )
    # If a row with this UUID somehow already exists, no-op (we generated the
    # UUID, so collision is astronomically unlikely; this guard is purely
    # defensive).
    instr_stmt = instr_stmt.on_conflict_do_nothing(index_elements=["instrument_id"])
    res_instr = session.execute(instr_stmt)
    instruments_inserted = 1 if (res_instr.rowcount and res_instr.rowcount > 0) else 0

    id_stmt = pg_insert(InstrumentIdentifier).values(
        instrument_id=iid,
        id_type="ticker",
        id_value=ticker,
        source="bootstrap_prod",
        valid_from=effective_from,
        is_primary=True,
    ).on_conflict_do_nothing(
        index_elements=["instrument_id", "id_type", "id_value", "source", "valid_from"],
    )
    res_id = session.execute(id_stmt)
    identifiers_inserted = 1 if (res_id.rowcount and res_id.rowcount > 0) else 0

    hist_stmt = pg_insert(TickerHistory).values(
        instrument_id=iid,
        ticker=ticker,
        effective_from=effective_from,
        issuer_name=profile["issuer_name_current"],
        exchange=profile["exchange_primary"],
        source="bootstrap_prod",
    ).on_conflict_do_nothing(
        index_elements=["instrument_id", "ticker", "effective_from"],
    )
    res_hist = session.execute(hist_stmt)
    histories_inserted = 1 if (res_hist.rowcount and res_hist.rowcount > 0) else 0

    return str(iid), instruments_inserted, identifiers_inserted, histories_inserted


# ---------------------------------------------------------------------------
# execute_bootstrap — gated on plan.write_mode + db_target
# ---------------------------------------------------------------------------


async def execute_bootstrap(
    plan: BootstrapPlan,
    session,
    *,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
    fmp_profile_fetch: Optional[Callable[[str], Awaitable[dict | None]]] = None,
) -> BootstrapResult:
    """Execute a bootstrap plan against the configured DB target.

    WRITE_LOCAL writes to the local dev DB.
    WRITE_PRODUCTION writes to Cloud SQL (Phase B3) — only entered when all
    four flags pass AND ``db_target == "production"``.
    DRY_RUN is rejected — use ``render_bootstrap_plan_report`` for that.

    Args:
        plan: The plan from build_bootstrap_plan.
        session: Active DB session.
        sleep_fn: Override for inter-ticker pacing. Default = asyncio.sleep.
            Tests should pass an instant no-op.
        fmp_profile_fetch: Override for the FMP profile fetcher. Tests pass
            a mock to verify isolation, fallback handling, and idempotency.
    """
    if plan.write_mode == "DRY_RUN":
        raise ValueError(
            "execute_bootstrap called with DRY_RUN plan. "
            "Use render_bootstrap_plan_report instead."
        )

    if plan.write_mode not in ("WRITE_LOCAL", "WRITE_PRODUCTION"):
        raise ValueError(f"Unsupported write_mode: {plan.write_mode}")

    # Defense-in-depth: db_target must match write_mode.
    if plan.write_mode == "WRITE_LOCAL" and plan.db_target != "local":
        raise ValueError(
            f"REFUSED: WRITE_LOCAL requires db_target=local, got '{plan.db_target}'. "
            "Aborting before any DB writes."
        )
    if plan.write_mode == "WRITE_PRODUCTION" and plan.db_target != "production":
        raise ValueError(
            f"REFUSED: WRITE_PRODUCTION requires db_target=production, "
            f"got '{plan.db_target}'. Aborting before any DB writes."
        )

    _sleep = sleep_fn or asyncio.sleep
    _fetch = fmp_profile_fetch or _fetch_profile_via_fmp

    succeeded: list[str] = []
    skipped: list[str] = []
    failed: list[tuple[str, str]] = []
    per_ticker: list[TickerBootstrapResult] = []
    instruments_inserted = 0
    identifiers_inserted = 0
    histories_inserted = 0
    overall_start = time.monotonic()

    fmp_call_index = 0
    for tkp in plan.per_ticker:
        ticker_start = time.monotonic()
        tkr = tkp.ticker

        # Skip already-scaffolded tickers (idempotency)
        if tkp.already_exists:
            per_ticker.append(TickerBootstrapResult(
                ticker=tkr,
                instrument_id=None,
                asset_type=tkp.asset_type,
                issuer_name=None,
                exchange=None,
                currency=None,
                country_code=None,
                fmp_attempted=False,
                fmp_error=None,
                used_fallback_issuer=False,
                used_fallback_exchange=False,
                used_fallback_currency=False,
                used_fallback_country=False,
                skipped_existing=True,
                written=False,
                runtime_seconds=time.monotonic() - ticker_start,
            ))
            skipped.append(tkr)
            continue

        # Pace between FMP calls
        if fmp_call_index > 0:
            await _sleep(plan.fmp_delay_seconds)
        fmp_call_index += 1

        # Fetch profile (or mock)
        raw_profile: dict | None = None
        fmp_error: str | None = None
        try:
            raw_profile = await _fetch(tkr)
        except Exception as e:
            fmp_error = f"{type(e).__name__}: {str(e)[:160]}"

        # Apply deterministic fallbacks even if FMP failed entirely
        norm = _normalize_profile(tkr, raw_profile if fmp_error is None else None)

        # Try to write scaffolding rows
        write_error: str | None = None
        instrument_id_str: str | None = None
        try:
            (
                instrument_id_str,
                ins_i, ins_id, ins_h,
            ) = _write_scaffolding_rows(
                session,
                ticker=tkr,
                asset_type=tkp.asset_type,
                profile=norm,
                effective_from=plan.effective_from,
            )
            session.commit()
            instruments_inserted += ins_i
            identifiers_inserted += ins_id
            histories_inserted += ins_h
        except Exception as e:
            write_error = f"WriteError: {type(e).__name__}: {str(e)[:160]}"
            try:
                session.rollback()
            except Exception:
                pass

        runtime = time.monotonic() - ticker_start
        if write_error is None:
            succeeded.append(tkr)
            per_ticker.append(TickerBootstrapResult(
                ticker=tkr,
                instrument_id=instrument_id_str,
                asset_type=tkp.asset_type,
                issuer_name=norm["issuer_name_current"],
                exchange=norm["exchange_primary"],
                currency=norm["currency"],
                country_code=norm["country_code"],
                fmp_attempted=True,
                fmp_error=fmp_error,
                used_fallback_issuer=norm["used_fallback_issuer"],
                used_fallback_exchange=norm["used_fallback_exchange"],
                used_fallback_currency=norm["used_fallback_currency"],
                used_fallback_country=norm["used_fallback_country"],
                skipped_existing=False,
                written=True,
                runtime_seconds=runtime,
            ))
        else:
            per_ticker.append(TickerBootstrapResult(
                ticker=tkr,
                instrument_id=None,
                asset_type=tkp.asset_type,
                issuer_name=None,
                exchange=None,
                currency=None,
                country_code=None,
                fmp_attempted=True,
                fmp_error=fmp_error,
                used_fallback_issuer=False,
                used_fallback_exchange=False,
                used_fallback_currency=False,
                used_fallback_country=False,
                skipped_existing=False,
                written=False,
                runtime_seconds=runtime,
            ))
            err = write_error
            if fmp_error:
                err = f"{err} ; fmp_error={fmp_error}"
            failed.append((tkr, err))

    overall_runtime = time.monotonic() - overall_start

    if plan.write_mode == "WRITE_PRODUCTION":
        db_writes_label = "instrument + instrument_identifier + ticker_history only (PRODUCTION Cloud SQL)"
    else:
        db_writes_label = "instrument + instrument_identifier + ticker_history only (LOCAL)"

    return BootstrapResult(
        mode=plan.write_mode,
        db_target=plan.db_target,
        db_url_label=plan.db_url_label,
        universe_name=plan.universe_name,
        requested_count=len(plan.requested_tickers),
        target_count=len(plan.target_tickers),
        succeeded=succeeded,
        skipped_already_exists=skipped,
        failed=failed,
        instruments_inserted=instruments_inserted,
        identifiers_inserted=identifiers_inserted,
        ticker_histories_inserted=histories_inserted,
        runtime_seconds=overall_runtime,
        per_ticker=per_ticker,
        db_writes_performed=db_writes_label,
    )


# Production write entry conditions (defense-in-depth notes)
# ---------------------------------------------------------------------------
#
# WRITE_PRODUCTION here mirrors sync_eod_prices_universe semantics:
#
#   1. plan.write_mode == "WRITE_PRODUCTION"
#   2. confirm_production_write was True at build_bootstrap_plan time
#   3. plan.db_target == "production" (URL classified as Cloud SQL OR
#      DB_TARGET_OVERRIDE=production)
#   4. CLI invoked with all four flags:
#         --no-dry-run --write --db-target=production --confirm-production-write
#
# Defense-in-depth at TWO layers:
#   - build_bootstrap_plan refuses to construct a plan if any of (1) (2) (3)
#     is missing or contradictory
#   - execute_bootstrap re-verifies (1) and (3) before any DB write
#
# Protected ticker enforcement also at TWO layers:
#   - build_bootstrap_plan filters out PROTECTED_TICKERS at plan time
#   - The target_tickers list is the authoritative source for execute_bootstrap;
#     PROTECTED tickers cannot reach the FMP/DB write path

PRODUCTION_WRITE_GUARD_MESSAGE = (
    "WRITE_PRODUCTION requires all four CLI flags simultaneously: "
    "--no-dry-run --write --db-target=production --confirm-production-write. "
    "The DB URL must classify as production (Cloud SQL or DB_TARGET_OVERRIDE=production). "
    "See docs/runbook.md 'Scanner Universe Production Bootstrap (Phase B3 Execution)' "
    "for the operator playbook."
)
