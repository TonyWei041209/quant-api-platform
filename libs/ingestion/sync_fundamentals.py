"""Sync financial statements from FMP into financial_period + financial_fact_std."""
from __future__ import annotations

from datetime import date, datetime, UTC

from sqlalchemy.orm import Session

from libs.adapters.fmp_adapter import FMPAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.financial_period import FinancialPeriod
from libs.db.models.financial_fact_std import FinancialFactStd
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def sync_fundamentals(
    session: Session,
    symbol: str,
    instrument_id: str,
    period: str = "annual",
) -> dict:
    """Sync income/balance/cashflow from FMP.

    reported_at is set from FMP's fillingDate or acceptedDate.
    Future phase: cross-reference with SEC filing acceptance_datetime.
    """
    run = SourceRun(
        run_id=new_id(), source="fmp", job_name="sync_fundamentals",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"periods_created": 0, "facts_created": 0, "errors": 0}

    try:
        adapter = FMPAdapter()
        scope = "annual" if period == "annual" else "quarterly"

        statements = {
            "income": await adapter.get_income_statement(symbol, period),
            "balance": await adapter.get_balance_sheet(symbol, period),
            "cashflow": await adapter.get_cash_flow(symbol, period),
        }

        # Track periods by (fiscal_year, period_end) to avoid duplicates
        period_map: dict[tuple, FinancialPeriod] = {}

        for stmt_type, records in statements.items():
            for raw in records:
                try:
                    period_end_str = raw.get("date", "")
                    if not period_end_str:
                        continue

                    period_end = date.fromisoformat(period_end_str)
                    fiscal_year = int(raw.get("calendarYear", 0) or 0)
                    fiscal_quarter = None
                    if period == "quarter":
                        q_str = raw.get("period", "")
                        fiscal_quarter = int(q_str.replace("Q", "")) if q_str.startswith("Q") else None

                    # Determine reported_at (PIT-critical)
                    reported_at = None
                    for dt_field in ("acceptedDate", "fillingDate"):
                        val = raw.get(dt_field)
                        if val:
                            try:
                                reported_at = datetime.fromisoformat(val).replace(tzinfo=UTC)
                            except ValueError:
                                try:
                                    reported_at = datetime.combine(date.fromisoformat(val), datetime.min.time()).replace(tzinfo=UTC)
                                except ValueError:
                                    pass
                            if reported_at:
                                break

                    if reported_at is None:
                        reported_at = utc_now()
                        logger.warning("sync_fundamentals.missing_reported_at", symbol=symbol, period_end=period_end_str)

                    key = (fiscal_year, period_end)
                    if key not in period_map:
                        fp = FinancialPeriod(
                            financial_period_id=new_id(),
                            instrument_id=instrument_id,
                            statement_scope=scope,
                            fiscal_year=fiscal_year,
                            fiscal_quarter=fiscal_quarter,
                            period_end=period_end,
                            reported_at=reported_at,
                            source="fmp",
                        )
                        session.add(fp)
                        period_map[key] = fp
                        counters["periods_created"] += 1

                    fp = period_map[key]
                    facts = adapter.normalize_financial(raw, stmt_type)
                    for fact in facts:
                        session.add(FinancialFactStd(
                            financial_period_id=fp.financial_period_id,
                            statement_type=fact["statement_type"],
                            metric_code=fact["metric_code"],
                            source="fmp",
                            metric_value=fact["metric_value"],
                            unit=fact.get("unit"),
                        ))
                        counters["facts_created"] += 1

                except Exception as e:
                    counters["errors"] += 1
                    logger.error("sync_fundamentals.entry_error", error=str(e), stmt_type=stmt_type)

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()
        logger.info("sync_fundamentals.complete", symbol=symbol, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
