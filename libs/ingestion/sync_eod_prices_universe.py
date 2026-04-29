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

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal


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


def execute_sync(plan: SyncPlan, session=None) -> dict:
    """Execute the sync plan. ONLY callable when write_mode != DRY_RUN.

    This function intentionally raises ``NotImplementedError`` until the
    daily incremental sync code path is reviewed and approved per
    docs/scanner-research-universe-production-plan.md Section 8 acceptance
    criteria. It exists so the planner type contract is complete.
    """
    if plan.write_mode == "DRY_RUN":
        raise ValueError("execute_sync called with DRY_RUN plan. Refusing.")
    raise NotImplementedError(
        "Universe-mode EOD sync execution is gated on acceptance criteria "
        "#5-#10. Until those are signed off, execute_sync is intentionally "
        "unimplemented. Use build_sync_plan + render_plan_report for "
        "dry-run planning."
    )
