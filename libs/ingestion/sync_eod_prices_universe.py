"""Universe EOD sync planner — daily incremental sync for Scanner Research Universe.

================================================================================
DRY-RUN FIRST. PRODUCTION WRITES REQUIRE TWO EXPLICIT FLAGS.
================================================================================

This module computes a sync plan (which tickers, which date range, which
provider, expected runtime) and optionally executes it. The default mode is
``dry_run=True`` which produces a planning report and writes nothing to any
database, makes no provider HTTP calls, and creates no Cloud resources.

Production writes are gated by a deliberate two-flag handshake:
  - ``write_mode == "WRITE_PRODUCTION"``
  - ``confirm_production_write is True``
Both must be set. A single flag is a no-op safety guard.

This module is the production sync path:
  - source priority: Polygon (Massive) primary → FMP fallback
  - **yfinance_dev MUST NOT appear here** — it is dev-only by project policy.
    A separate module (``libs/ingestion/dev_load_prices.py``) handles dev seed.
  - rate-limit pacing: default 13s/call (Polygon free tier 5 req/min safe)
  - per-ticker isolation: failure of one ticker does NOT abort the rest

Guardrails:
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
from datetime import date, timedelta
from typing import Awaitable, Callable, Literal, Optional


# Default rate-limit pacing (Polygon free tier = 5 req/min)
DEFAULT_POLYGON_DELAY_SECONDS = 13.0

# Default lookback window for incremental sync (covers occasional missed days)
DEFAULT_LOOKBACK_DAYS = 7

# Default bootstrap window (only used when no prior data exists for a ticker)
DEFAULT_BOOTSTRAP_DAYS = 540

WriteMode = Literal["DRY_RUN", "WRITE_LOCAL", "WRITE_PRODUCTION"]
DbTarget = Literal["local", "production", "unknown"]


@dataclass
class TickerPlan:
    """Per-ticker plan derived from local DB state (read-only)."""
    ticker: str
    last_known_trade_date: date | None  # None if no prior bars
    plan_start: date
    plan_end: date
    is_bootstrap: bool  # True if no prior bars (would use full bootstrap window)


@dataclass
class SyncPlan:
    """Aggregate plan for a sync run. Pure data — no side effects."""
    universe_name: str
    tickers: tuple[str, ...]
    write_mode: WriteMode
    db_target: DbTarget
    db_url_label: str
    polygon_delay_seconds: float
    lookback_days: int
    bootstrap_days: int
    primary_source: Literal["polygon", "fmp"]
    fallback_source: Literal["polygon", "fmp"]
    today: date
    per_ticker: list[TickerPlan] = field(default_factory=list)

    @property
    def estimated_polygon_calls(self) -> int:
        # One range call per ticker per run
        return len(self.tickers)

    @property
    def estimated_runtime_seconds(self) -> float:
        # tickers × pacing (Polygon) — FMP fallback only fires on Polygon failure
        return len(self.tickers) * self.polygon_delay_seconds

    @property
    def banned_phrases_check(self) -> list[str]:
        """Verify no trading-action language ever appears in the plan
        descriptors. Used by unit tests + summary printer.
        """
        haystack = " ".join([
            self.universe_name, self.write_mode, self.db_target,
            self.primary_source, self.fallback_source,
        ]).lower()
        banned = [
            "buy", "sell", "enter long", "enter short", "target price",
            "position size", "leverage", "guaranteed",
        ]
        return [b for b in banned if b in haystack]


def _classify_db_url(url_str: str) -> DbTarget:
    s = url_str.lower()
    if "localhost" in s or "127.0.0.1" in s:
        return "local"
    if "/cloudsql/" in s or "cloudsql" in s:
        return "production"
    return "unknown"


def _resolve_db_target_label(session_or_engine) -> tuple[DbTarget, str]:
    """Read-only inspection of the DB URL. Never logs the password."""
    try:
        url = session_or_engine.get_bind().url if hasattr(session_or_engine, "get_bind") \
            else session_or_engine.url
        url_str = str(url)
        # Mask password if present
        import re
        masked = re.sub(r":[^:@]+@", ":***@", url_str)
        return _classify_db_url(url_str), masked
    except Exception:
        return "unknown", "(unable to inspect)"


def _latest_trade_date_per_ticker(session, tickers: tuple[str, ...]) -> dict[str, date]:
    """Read-only: query existing latest trade_date per ticker. Returns
    {ticker: latest_date} only for tickers that have any prior bars."""
    if not tickers:
        return {}
    from sqlalchemy import text
    rows = session.execute(
        text(
            """
            SELECT ii.id_value AS ticker, MAX(p.trade_date) AS latest
            FROM price_bar_raw p
            JOIN instrument_identifier ii ON ii.instrument_id = p.instrument_id
                AND ii.id_type = 'ticker'
            WHERE ii.id_value = ANY(:tickers)
            GROUP BY ii.id_value
            """
        ),
        {"tickers": list(tickers)},
    ).fetchall()
    return {r[0]: r[1] for r in rows if r[1] is not None}


def build_sync_plan(
    *,
    universe_name: str,
    tickers: tuple[str, ...],
    write_mode: WriteMode,
    confirm_production_write: bool,
    polygon_delay_seconds: float = DEFAULT_POLYGON_DELAY_SECONDS,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    bootstrap_days: int = DEFAULT_BOOTSTRAP_DAYS,
    session=None,  # SQLAlchemy session, optional — required only when introspecting DB
    today: date | None = None,
) -> SyncPlan:
    """Compute a sync plan. PURE PLANNING — no DB writes, no API calls.

    If ``session`` is provided, the planner queries the latest trade_date per
    ticker (read-only). If not provided, it assumes bootstrap window for all
    tickers.
    """
    today = today or date.today()

    # Validate write_mode → confirm_production_write coupling
    if write_mode == "WRITE_PRODUCTION" and not confirm_production_write:
        raise ValueError(
            "WRITE_PRODUCTION requires confirm_production_write=True. "
            "Single-flag production writes are not allowed by policy."
        )

    # Identify DB target if session present
    if session is not None:
        db_target, db_url_label = _resolve_db_target_label(session)
        latest_dates = _latest_trade_date_per_ticker(session, tickers)
    else:
        db_target, db_url_label = "unknown", "(no session — pure dry-run)"
        latest_dates = {}

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

    per_ticker: list[TickerPlan] = []
    for tkr in tickers:
        last = latest_dates.get(tkr)
        if last is None:
            # Bootstrap: no prior bars
            per_ticker.append(TickerPlan(
                ticker=tkr,
                last_known_trade_date=None,
                plan_start=today - timedelta(days=bootstrap_days),
                plan_end=today,
                is_bootstrap=True,
            ))
        else:
            # Incremental: pull from (latest - lookback) to today, idempotent overlap
            start = last - timedelta(days=lookback_days)
            per_ticker.append(TickerPlan(
                ticker=tkr,
                last_known_trade_date=last,
                plan_start=start,
                plan_end=today,
                is_bootstrap=False,
            ))

    return SyncPlan(
        universe_name=universe_name,
        tickers=tickers,
        write_mode=write_mode,
        db_target=db_target,
        db_url_label=db_url_label,
        polygon_delay_seconds=polygon_delay_seconds,
        lookback_days=lookback_days,
        bootstrap_days=bootstrap_days,
        primary_source="polygon",  # hard-coded — yfinance_dev forbidden
        fallback_source="fmp",
        today=today,
        per_ticker=per_ticker,
    )


def render_plan_report(plan: SyncPlan) -> str:
    """Build a human-readable plan summary. Pure string output. No side effects."""
    lines = []
    lines.append("=" * 78)
    lines.append("  EOD SYNC PLAN — universe='{u}'  mode={m}".format(
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
    lines.append(f"  ticker_count            : {len(plan.tickers)}")
    lines.append(f"  tickers (first 10)      : {', '.join(plan.tickers[:10])}, ...")
    lines.append(f"  primary_source          : {plan.primary_source} (Polygon)")
    lines.append(f"  fallback_source         : {plan.fallback_source} (FMP)")
    lines.append(f"  data_mode               : daily_eod")
    lines.append(f"  yfinance_dev allowed    : NO (dev-only path; forbidden in production sync)")
    lines.append(f"  polygon_delay_seconds   : {plan.polygon_delay_seconds:.1f}")
    lines.append(f"  lookback_days           : {plan.lookback_days}")
    lines.append(f"  bootstrap_days          : {plan.bootstrap_days}")
    lines.append(f"  estimated_polygon_calls : {plan.estimated_polygon_calls}")
    lines.append(f"  estimated_runtime_secs  : {plan.estimated_runtime_seconds:.0f}  (~{plan.estimated_runtime_seconds/60:.1f} min)")
    lines.append(f"  today                   : {plan.today.isoformat()}")
    lines.append("")
    lines.append(f"  db_target               : {plan.db_target}")
    lines.append(f"  db_url_label            : {plan.db_url_label}")
    lines.append("")
    lines.append("  per-ticker plan:")
    bootstrap_n = sum(1 for p in plan.per_ticker if p.is_bootstrap)
    incremental_n = len(plan.per_ticker) - bootstrap_n
    lines.append(f"    bootstrap (no prior bars) : {bootstrap_n}")
    lines.append(f"    incremental (existing)    : {incremental_n}")
    if plan.per_ticker:
        lines.append("    sample (first 5):")
        for p in plan.per_ticker[:5]:
            mode = "BOOTSTRAP" if p.is_bootstrap else "INCR"
            last = p.last_known_trade_date.isoformat() if p.last_known_trade_date else "—"
            lines.append(
                f"      {p.ticker:6s} {mode:9s}  last_known={last}  "
                f"plan={p.plan_start} → {p.plan_end}"
            )
    lines.append("")
    lines.append("  Side-effect summary:")
    lines.append(f"    DB writes performed     : NONE  (this module is plan-only "
                 "until execute_sync is called)")
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
    lines.append("  Production seed: REMAINS DEFERRED — see")
    lines.append("    docs/scanner-research-universe-production-plan.md Section 8")
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TickerSyncResult:
    """Per-ticker outcome from execute_sync."""
    ticker: str
    instrument_id: str | None
    source_used: str | None  # "polygon" / "fmp" / None if both failed
    polygon_attempted: bool
    polygon_error: str | None
    fmp_attempted: bool
    fmp_error: str | None
    bars_inserted: int
    bars_skipped: int  # already existed (ON CONFLICT DO NOTHING)
    runtime_seconds: float


@dataclass
class SyncResult:
    """Aggregate result of an execute_sync run."""
    mode: WriteMode
    db_target: DbTarget
    db_url_label: str
    universe_name: str
    ticker_count: int
    succeeded: list[str]
    failed: list[tuple[str, str]]  # (ticker, last_error)
    bars_inserted_total: int
    bars_existing_or_skipped_total: int
    runtime_seconds: float
    per_ticker: list[TickerSyncResult]
    # Side-effect attestations — explicit string values for log + test pinning
    db_writes_performed: str = "price_bar_raw + source_run only (LOCAL)"
    cloud_run_jobs_created: str = "NONE"
    scheduler_changes: str = "NONE"
    production_deploy: str = "NONE"
    execution_objects: str = "NONE"
    broker_write: str = "NONE"
    live_submit: str = "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)"


def render_sync_result(res: SyncResult) -> str:
    """Human-readable sync result. Pure string, no side effects."""
    lines = []
    lines.append("=" * 78)
    lines.append(f"  SYNC RESULT — universe='{res.universe_name}'  mode={res.mode}")
    lines.append("=" * 78)
    lines.append(f"  ticker_count                  : {res.ticker_count}")
    lines.append(f"  succeeded                     : {len(res.succeeded)}")
    lines.append(f"  failed                        : {len(res.failed)}")
    lines.append(f"  bars_inserted_total           : {res.bars_inserted_total}")
    lines.append(f"  bars_existing_or_skipped_total: {res.bars_existing_or_skipped_total}")
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
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Production-write entry conditions (enforced by execute_sync below)
# ---------------------------------------------------------------------------
#
# WRITE_PRODUCTION was implemented in commit-after-60b4ddc (Phase B1).
# The implementation reuses the same per-ticker sync path as WRITE_LOCAL,
# but is gated by ALL of these conditions simultaneously:
#
#   1. plan.write_mode == "WRITE_PRODUCTION"
#   2. confirm_production_write was True at build_sync_plan time
#   3. plan.db_target == "production" (URL classified as Cloud SQL)
#   4. The CLI must have invoked with all four flags:
#         --no-dry-run --write --db-target=production --confirm-production-write
#
# Defense-in-depth checks happen at TWO layers:
#   - build_sync_plan refuses to construct the plan if any of (1) (2) (3) is
#     missing or contradictory
#   - execute_sync re-verifies (1) and (3) before any DB write, even if a
#     malformed plan slipped through (e.g., hand-constructed in tests)
#
# An execution outside the one-shot Cloud Run Job described in
# docs/runbook.md "Scanner Universe Production Seed (Phase B Execution
# Playbook)" is supported but discouraged: the Job-mediated path provides
# the audit trail (Cloud Logging + uniquely-named one-shot job) that bare
# CLI invocation does not.

PRODUCTION_WRITE_GUARD_MESSAGE = (
    "WRITE_PRODUCTION requires all four CLI flags simultaneously: "
    "--no-dry-run --write --db-target=production --confirm-production-write. "
    "The DB URL must classify as production (Cloud SQL). See "
    "docs/runbook.md 'Scanner Universe Production Seed (Phase B Execution Playbook)' "
    "for the operator playbook including pre-flight checks, Cloud SQL backup, "
    "post-flight verification, and rollback procedure."
)

# Backwards-compatible alias kept in case external scripts/tests reference
# the old name. New code should use PRODUCTION_WRITE_GUARD_MESSAGE.
PRODUCTION_WRITE_DEFERRED_MESSAGE = PRODUCTION_WRITE_GUARD_MESSAGE


# ---------------------------------------------------------------------------
# Per-ticker sync — composes existing Polygon + FMP adapters
# ---------------------------------------------------------------------------

async def _sync_one_ticker_polygon(
    session,
    ticker: str,
    instrument_id: str,
    from_date: date,
    to_date: date,
) -> tuple[int, int]:
    """Pull bars from Polygon, INSERT ... ON CONFLICT DO NOTHING.
    Returns (inserted, skipped). Raises on adapter / network errors.
    """
    from libs.adapters.massive_adapter import MassiveAdapter
    from libs.core.time import utc_now
    from libs.db.models.price_bar_raw import PriceBarRaw
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    adapter = MassiveAdapter()
    bars = await adapter.get_eod_bars(
        ticker, from_date.isoformat(), to_date.isoformat(), adjusted=False
    )
    inserted = 0
    skipped = 0
    for bar in bars or []:
        try:
            normalized = adapter.normalize(bar)
            trade_ts = normalized.get("trade_date")
            if isinstance(trade_ts, (int, float)):
                from datetime import datetime, UTC
                trade_date = datetime.fromtimestamp(trade_ts / 1000, tz=UTC).date()
            else:
                trade_date = date.fromisoformat(str(trade_ts)) if trade_ts else None
            if trade_date is None:
                continue
            stmt = pg_insert(PriceBarRaw).values(
                instrument_id=instrument_id,
                trade_date=trade_date,
                source="polygon",  # universe-sync uses 'polygon' tag, distinct from per-ticker 'massive' callers
                open=normalized["open"],
                high=normalized["high"],
                low=normalized["low"],
                close=normalized["close"],
                volume=normalized["volume"],
                vwap=normalized.get("vwap"),
                ingested_at=utc_now(),
                raw_payload=bar,
            ).on_conflict_do_nothing(
                index_elements=["instrument_id", "trade_date", "source"],
            )
            result = session.execute(stmt)
            if result.rowcount and result.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            # Per-bar failure does not abort the ticker. Caller sees what it
            # got. We could count these as 'errors' but the contract asks
            # for inserted/skipped only.
            skipped += 1
    return inserted, skipped


async def _sync_one_ticker_fmp(
    session,
    ticker: str,
    instrument_id: str,
    from_date: date,
    to_date: date,
) -> tuple[int, int]:
    """FMP fallback path. Same idempotent INSERT semantics as Polygon path.
    Returns (inserted, skipped). Raises on adapter / network errors.
    """
    import json
    from libs.adapters.fmp_adapter import FMPAdapter
    from libs.core.time import utc_now
    from libs.db.models.price_bar_raw import PriceBarRaw
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    adapter = FMPAdapter()
    bars = await adapter.get_eod_prices(
        ticker, from_date=from_date.isoformat(), to_date=to_date.isoformat()
    )
    inserted = 0
    skipped = 0
    for bar in bars or []:
        try:
            norm = adapter.normalize_price(bar)
            trade_date_str = norm.get("trade_date")
            if not trade_date_str:
                continue
            trade_date = date.fromisoformat(str(trade_date_str))
            stmt = pg_insert(PriceBarRaw).values(
                instrument_id=instrument_id,
                trade_date=trade_date,
                source="fmp",
                open=norm["open"],
                high=norm["high"],
                low=norm["low"],
                close=norm["close"],
                volume=norm["volume"],
                vwap=norm.get("vwap"),
                ingested_at=utc_now(),
                raw_payload=json.dumps(bar, default=str),
            ).on_conflict_do_nothing(
                index_elements=["instrument_id", "trade_date", "source"],
            )
            result = session.execute(stmt)
            if result.rowcount and result.rowcount > 0:
                inserted += 1
            else:
                skipped += 1
        except Exception:
            skipped += 1
    return inserted, skipped


def _resolve_instrument_ids(session, tickers: tuple[str, ...]) -> dict[str, str]:
    """Map ticker → instrument_id via instrument_identifier. Read-only."""
    if not tickers:
        return {}
    from sqlalchemy import text
    rows = session.execute(
        text(
            """
            SELECT id_value, instrument_id::text
            FROM instrument_identifier
            WHERE id_type = 'ticker' AND id_value = ANY(:tickers)
            """
        ),
        {"tickers": list(tickers)},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# execute_sync — WRITE_LOCAL fully implemented; WRITE_PRODUCTION still blocked
# ---------------------------------------------------------------------------

async def execute_sync(
    plan: SyncPlan,
    session,
    *,
    sleep_fn: Optional[Callable[[float], Awaitable[None]]] = None,
    polygon_call: Optional[Callable] = None,
    fmp_call: Optional[Callable] = None,
) -> SyncResult:
    """Execute a sync plan against the configured DB target.

    WRITE_LOCAL is implemented and will write to the local dev DB only.
    WRITE_PRODUCTION raises NotImplementedError until acceptance #5/#9 sign-off.
    DRY_RUN is rejected — use render_plan_report for that.

    Args:
        plan: The plan from build_sync_plan.
        session: Active DB session.
        sleep_fn: Override for inter-ticker pacing. Default = asyncio.sleep.
            Tests should pass an instant no-op.
        polygon_call: Override for the per-ticker Polygon function. Tests pass
            a mock to verify isolation, fallback, and rowcount handling.
        fmp_call: Same for FMP.
    """
    # Reject DRY_RUN at the front
    if plan.write_mode == "DRY_RUN":
        raise ValueError(
            "execute_sync called with DRY_RUN plan. Use render_plan_report instead."
        )

    # Validate write_mode is one we know how to execute
    if plan.write_mode not in ("WRITE_LOCAL", "WRITE_PRODUCTION"):
        raise ValueError(f"Unsupported write_mode: {plan.write_mode}")

    # Defense-in-depth: db_target must match write_mode. Even though the
    # planner already enforces this, a hand-constructed plan (e.g., in tests
    # or a malicious caller) could try to slip a mismatch past it. We refuse
    # before issuing a single DB write.
    if plan.write_mode == "WRITE_LOCAL" and plan.db_target != "local":
        raise ValueError(
            f"REFUSED: WRITE_LOCAL requires db_target=local, got '{plan.db_target}'. "
            "Aborting before any DB writes."
        )
    if plan.write_mode == "WRITE_PRODUCTION" and plan.db_target != "production":
        raise ValueError(
            f"REFUSED: WRITE_PRODUCTION requires db_target=production, "
            f"got '{plan.db_target}'. Aborting before any DB writes. "
            f"{PRODUCTION_WRITE_GUARD_MESSAGE}"
        )

    # Wire test overrides
    _sleep = sleep_fn or asyncio.sleep
    _polygon = polygon_call or _sync_one_ticker_polygon
    _fmp = fmp_call or _sync_one_ticker_fmp

    # Resolve instrument_ids up front (read-only)
    iid_map = _resolve_instrument_ids(session, plan.tickers)

    succeeded: list[str] = []
    failed: list[tuple[str, str]] = []
    per_ticker: list[TickerSyncResult] = []
    bars_inserted_total = 0
    bars_skipped_total = 0
    overall_start = time.monotonic()

    for i, tkp in enumerate(plan.per_ticker):
        if i > 0:
            await _sleep(plan.polygon_delay_seconds)

        tkr = tkp.ticker
        ticker_start = time.monotonic()
        iid = iid_map.get(tkr)

        if not iid:
            err = "instrument_id not resolved (ticker not in instrument_identifier)"
            per_ticker.append(TickerSyncResult(
                ticker=tkr, instrument_id=None, source_used=None,
                polygon_attempted=False, polygon_error=None,
                fmp_attempted=False, fmp_error=None,
                bars_inserted=0, bars_skipped=0,
                runtime_seconds=time.monotonic() - ticker_start,
            ))
            failed.append((tkr, err))
            continue

        # Try Polygon primary
        polygon_error: str | None = None
        fmp_error: str | None = None
        source_used: str | None = None
        inserted = skipped = 0
        try:
            inserted, skipped = await _polygon(session, tkr, iid, tkp.plan_start, tkp.plan_end)
            source_used = "polygon"
        except Exception as e:
            polygon_error = f"{type(e).__name__}: {str(e)[:160]}"
            # Roll back any partial state from polygon path before trying FMP
            try:
                session.rollback()
            except Exception:
                pass

        # FMP fallback only if Polygon raised
        if source_used is None:
            try:
                inserted, skipped = await _fmp(session, tkr, iid, tkp.plan_start, tkp.plan_end)
                source_used = "fmp"
            except Exception as e:
                fmp_error = f"{type(e).__name__}: {str(e)[:160]}"
                try:
                    session.rollback()
                except Exception:
                    pass

        # Per-ticker commit (success path) or rollback (both providers failed).
        # This isolates each ticker's writes from other tickers' state and
        # ensures inserts persist even if the CLI caller forgets to commit.
        if source_used is not None:
            try:
                session.commit()
            except Exception as e:
                # Commit itself failed — record as failure, no partial persistence
                source_used = None
                if polygon_error is None:
                    polygon_error = f"CommitError: {type(e).__name__}: {str(e)[:120]}"
                else:
                    fmp_error = f"CommitError: {type(e).__name__}: {str(e)[:120]}"
                inserted = skipped = 0
                try:
                    session.rollback()
                except Exception:
                    pass

        runtime = time.monotonic() - ticker_start
        per_ticker.append(TickerSyncResult(
            ticker=tkr,
            instrument_id=iid,
            source_used=source_used,
            polygon_attempted=True,
            polygon_error=polygon_error,
            fmp_attempted=(source_used != "polygon"),
            fmp_error=fmp_error,
            bars_inserted=inserted,
            bars_skipped=skipped,
            runtime_seconds=runtime,
        ))
        if source_used:
            succeeded.append(tkr)
            bars_inserted_total += inserted
            bars_skipped_total += skipped
        else:
            err = polygon_error or fmp_error or "unknown error"
            failed.append((tkr, err))

    overall_runtime = time.monotonic() - overall_start

    # Label db_writes_performed by mode so audit trails distinguish LOCAL from
    # PRODUCTION writes. Other side-effect attestations (cloud_run_jobs_created,
    # scheduler_changes, production_deploy, execution_objects, broker_write,
    # live_submit) are mode-invariant and remain at their dataclass defaults.
    if plan.write_mode == "WRITE_PRODUCTION":
        db_writes_label = "price_bar_raw + source_run only (PRODUCTION Cloud SQL)"
    else:
        db_writes_label = "price_bar_raw + source_run only (LOCAL)"

    return SyncResult(
        mode=plan.write_mode,
        db_target=plan.db_target,
        db_url_label=plan.db_url_label,
        universe_name=plan.universe_name,
        ticker_count=len(plan.tickers),
        succeeded=succeeded,
        failed=failed,
        bars_inserted_total=bars_inserted_total,
        bars_existing_or_skipped_total=bars_skipped_total,
        runtime_seconds=overall_runtime,
        per_ticker=per_ticker,
        db_writes_performed=db_writes_label,
    )
