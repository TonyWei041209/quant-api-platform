"""EOD freshness invariant — post-sync diagnostic.

Pure function. No side effects beyond returning the report dict. The
sync job (libs/ingestion/sync_eod_prices_universe.py) calls
``compute_freshness_report`` after the per-ticker loop finishes, and
the prediction-eval path (and any other downstream consumer) may also
call it stand-alone against the production DB to decide whether
trade-date-N is available yet.

The four ``freshness_status`` values are designed so that downstream
consumers (prediction eval, brief generator, monitoring) can branch
without re-computing the rules:

  * ``fresh``         — DB max(trade_date) == expected_min_trade_date.
                        Eval can proceed.
  * ``provider_lag``  — sync ran successfully but DB max is the prior
                        weekday or older AND fewer than ``stale_after_days``
                        calendar days behind today. Treat as transient.
                        Prediction eval should wait one more sync.
  * ``stale``         — DB max is ``stale_after_days`` or more calendar
                        days behind expected_min_trade_date. Operations
                        should investigate.
  * ``partial``       — Some tickers are fresh, others lag. Common
                        right after a mirror bootstrap before bar
                        backfill.

Strict scope:

  * No broker write, no order_intent/order_draft mention.
  * Does not call provider HTTP.
  * Does not modify any row.
  * Does not change ``FEATURE_T212_LIVE_SUBMIT``.
  * The optional strict-mode flag (``EOD_FRESHNESS_STRICT_MODE``)
    only changes how a CALLER chooses to react (e.g. exit non-zero in
    a Cloud Run Job); the freshness helper itself never raises.

The default sync job behaviour is unchanged: when freshness is
``provider_lag`` (the common case in the first few hours after market
close on the same calendar day as the fire), the job still exits 0.
Only the log line and the SYNC RESULT block surface the warning.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal, Mapping, Sequence


logger = logging.getLogger(__name__)


FreshnessStatus = Literal["fresh", "provider_lag", "stale", "partial"]


# How many calendar days behind today's date counts as "stale" rather than
# "provider lag". A T-1 upstream is normal — a T-3 upstream is investigatable.
DEFAULT_STALE_AFTER_DAYS = 3


def _previous_weekday(d: date, n: int = 1) -> date:
    """Step back ``n`` weekdays from ``d`` (Mon=0..Sun=6).

    This is a calendar approximation, NOT a true exchange calendar — it
    does not subtract NYSE holidays. The freshness invariant only needs
    a conservative T-1/T-2 estimate; the canonical exchange calendar
    lives in ``libs.db.models.exchange_calendar`` and is queried by the
    sync planner, not by this helper.
    """
    cur = d
    weekdays_walked = 0
    while weekdays_walked < n:
        cur = cur - timedelta(days=1)
        # Saturday=5, Sunday=6 → skip
        if cur.weekday() < 5:
            weekdays_walked += 1
    return cur


@dataclass
class TickerFreshness:
    """Per-ticker freshness summary used by the partial-status detection."""
    ticker: str
    latest_trade_date: date | None
    is_fresh: bool
    is_bar_less: bool  # mirror-bootstrap rows have no bars at all by design


@dataclass
class FreshnessReport:
    """Aggregate freshness diagnostic for one EOD sync run."""
    today: date
    expected_min_trade_date: date
    latest_trade_date: date | None
    freshness_status: FreshnessStatus
    fresh_ticker_count: int
    stale_ticker_count: int
    bar_less_ticker_count: int
    inspected_ticker_count: int
    stale_after_days: int
    strict_mode: bool
    warning_message: str | None
    per_ticker: list[TickerFreshness] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "today": self.today.isoformat(),
            "expected_min_trade_date": self.expected_min_trade_date.isoformat(),
            "latest_trade_date": (
                self.latest_trade_date.isoformat()
                if self.latest_trade_date else None
            ),
            "freshness_status": self.freshness_status,
            "fresh_ticker_count": self.fresh_ticker_count,
            "stale_ticker_count": self.stale_ticker_count,
            "bar_less_ticker_count": self.bar_less_ticker_count,
            "inspected_ticker_count": self.inspected_ticker_count,
            "stale_after_days": self.stale_after_days,
            "strict_mode": self.strict_mode,
            "warning_message": self.warning_message,
        }


def is_strict_mode_enabled() -> bool:
    """Strict mode opt-in: when set to a truthy value, callers MAY choose
    to exit non-zero on ``stale``/``provider_lag``. The helper itself
    never reads the flag for control flow — it just surfaces it on the
    report so a caller knows the intent."""
    raw = os.environ.get("EOD_FRESHNESS_STRICT_MODE", "").strip().lower()
    return raw in ("1", "true", "yes", "on")


def expected_min_trade_date_for(today: date) -> date:
    """Conservative expected freshness target: the previous weekday.

    The sync job fires at 21:30Z (after US 20:00Z close). Provider EOD
    feeds typically publish "today's" bar somewhere between T+0 21:00Z
    and T+1 04:00Z. So the post-sync expectation is:

      * If sync just ran on weekday T: expect ``today - 1 weekday`` to
        be present (T-1 provider lag is normal). The sync run that
        will populate ``today`` happens at the NEXT day's 21:30Z.

    A more permissive policy (expect T-0) would over-alert. A stricter
    policy (expect T-2) would under-alert. T-1 is the default contract.
    """
    return _previous_weekday(today, n=1)


def compute_freshness_report(
    *,
    today: date,
    db_max_trade_date: date | None,
    per_ticker_max_trade_date: Mapping[str, date | None] | None = None,
    bar_less_tickers: Sequence[str] | None = None,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    strict_mode: bool | None = None,
) -> FreshnessReport:
    """Classify the freshness of the EOD pipeline as of ``today``.

    Inputs are explicit so this function can be unit-tested without
    any database or provider call. The sync job's
    ``execute_sync`` post-processing step is the production caller.

    Arguments:
      * ``today``: server-clock date in UTC. ``date.today()`` at the
        call site.
      * ``db_max_trade_date``: ``select max(trade_date) from price_bar_raw``.
        Pass ``None`` if the table has zero rows.
      * ``per_ticker_max_trade_date``: optional mapping. When provided
        we can compute the ``partial`` status (some tickers fresh,
        some stale).
      * ``bar_less_tickers``: optional list of tickers that have ZERO
        bars at all. These are NOT counted as stale (e.g. mirror-
        bootstrap scaffolding-only rows). They are reported separately.
      * ``stale_after_days``: calendar days behind
        ``expected_min_trade_date`` to flip from ``provider_lag`` to
        ``stale``. Default 3.
      * ``strict_mode``: if ``None``, reads ``EOD_FRESHNESS_STRICT_MODE``.

    Returns a :class:`FreshnessReport`. Never raises.
    """
    if strict_mode is None:
        strict_mode = is_strict_mode_enabled()

    expected_min = expected_min_trade_date_for(today)

    per_ticker_list: list[TickerFreshness] = []
    bar_less_set = {t.upper() for t in (bar_less_tickers or [])}
    fresh_count = 0
    stale_count = 0
    bar_less_count = 0

    if per_ticker_max_trade_date:
        for ticker, latest in per_ticker_max_trade_date.items():
            tkr_up = ticker.upper()
            is_bar_less = (
                latest is None and tkr_up in bar_less_set
            ) or (latest is None)
            is_fresh = latest is not None and latest >= expected_min
            per_ticker_list.append(TickerFreshness(
                ticker=tkr_up,
                latest_trade_date=latest,
                is_fresh=is_fresh,
                is_bar_less=is_bar_less,
            ))
            if is_bar_less:
                bar_less_count += 1
            elif is_fresh:
                fresh_count += 1
            else:
                stale_count += 1

    # Days behind expectation (negative = ahead, 0 = on target).
    days_behind: int
    if db_max_trade_date is None:
        days_behind = (expected_min - date(1970, 1, 1)).days
    else:
        days_behind = (expected_min - db_max_trade_date).days

    # Decide aggregate status.
    if per_ticker_list and fresh_count > 0 and stale_count > 0:
        status: FreshnessStatus = "partial"
        warning = (
            f"freshness partial: {fresh_count} fresh, {stale_count} stale, "
            f"{bar_less_count} bar-less (expected_min={expected_min.isoformat()})"
        )
    elif db_max_trade_date is None:
        status = "stale"
        warning = (
            "freshness stale: no bars in DB at all "
            f"(expected_min={expected_min.isoformat()})"
        )
    elif db_max_trade_date >= expected_min:
        status = "fresh"
        warning = None
    elif days_behind <= stale_after_days:
        status = "provider_lag"
        warning = (
            "freshness provider_lag: db_max=%s, expected_min=%s, "
            "%d days behind. Likely upstream provider T-1 delivery — "
            "typically clears by the next scheduled sync." % (
                db_max_trade_date.isoformat(),
                expected_min.isoformat(),
                days_behind,
            )
        )
    else:
        status = "stale"
        warning = (
            "freshness stale: db_max=%s, expected_min=%s, "
            "%d days behind. Investigate the EOD pipeline." % (
                db_max_trade_date.isoformat(),
                expected_min.isoformat(),
                days_behind,
            )
        )

    if warning:
        # Warning, not error — the sync job still exits 0 by default.
        # Callers in strict mode may upgrade to a non-zero exit.
        logger.warning("eod_freshness_check %s", warning)

    return FreshnessReport(
        today=today,
        expected_min_trade_date=expected_min,
        latest_trade_date=db_max_trade_date,
        freshness_status=status,
        fresh_ticker_count=fresh_count,
        stale_ticker_count=stale_count,
        bar_less_ticker_count=bar_less_count,
        inspected_ticker_count=len(per_ticker_list),
        stale_after_days=stale_after_days,
        strict_mode=strict_mode,
        warning_message=warning,
        per_ticker=per_ticker_list,
    )


def render_freshness_block(report: FreshnessReport) -> str:
    """Pretty-print the freshness report for inclusion in the
    SYNC RESULT block. Pure string, no side effects."""
    lines = []
    lines.append("  Freshness invariant:")
    lines.append(f"    today                        : {report.today.isoformat()}")
    lines.append(f"    expected_min_trade_date      : {report.expected_min_trade_date.isoformat()}")
    lines.append(
        f"    latest_trade_date            : "
        f"{report.latest_trade_date.isoformat() if report.latest_trade_date else 'NONE'}"
    )
    lines.append(f"    freshness_status             : {report.freshness_status}")
    if report.inspected_ticker_count:
        lines.append(
            f"    per-ticker: fresh={report.fresh_ticker_count} "
            f"stale={report.stale_ticker_count} "
            f"bar_less={report.bar_less_ticker_count} "
            f"inspected={report.inspected_ticker_count}"
        )
    lines.append(f"    stale_after_days             : {report.stale_after_days}")
    lines.append(f"    strict_mode                  : {report.strict_mode}")
    if report.warning_message:
        lines.append(f"    warning                      : {report.warning_message}")
    return "\n".join(lines)


def query_db_freshness(session) -> tuple[date | None, dict[str, date | None]]:
    """Read-only DB query: returns (overall_max, per_ticker_max).

    Pulled out of ``compute_freshness_report`` so the pure function
    can be tested without a database; this helper bridges to the real
    schema. Never writes.
    """
    from sqlalchemy import text
    overall = session.execute(
        text("select max(trade_date) from price_bar_raw")
    ).scalar()
    rows = session.execute(text(
        "select ii.id_value as ticker, max(pbr.trade_date) as latest "
        "from instrument_identifier ii "
        "left join price_bar_raw pbr on pbr.instrument_id = ii.instrument_id "
        "where ii.id_type = 'ticker' "
        "group by ii.id_value"
    )).fetchall()
    per_ticker: dict[str, date | None] = {}
    for r in rows:
        per_ticker[str(r[0]).upper()] = r[1]
    return overall, per_ticker
