"""Sync earnings events from FMP."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from libs.adapters.fmp_adapter import FMPAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.earnings_event import EarningsEvent
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def sync_earnings(session: Session, symbol: str, instrument_id: str) -> dict:
    """Sync earnings calendar events for a symbol."""
    run = SourceRun(
        run_id=new_id(), source="fmp", job_name="sync_earnings",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"inserted": 0, "errors": 0}

    try:
        adapter = FMPAdapter()
        events = await adapter.get_earnings_calendar()

        # Filter for our symbol
        symbol_events = [e for e in events if e.get("symbol", "").upper() == symbol.upper()]

        for raw in symbol_events:
            try:
                report_date_str = raw.get("date", "")
                if not report_date_str:
                    continue

                session.add(EarningsEvent(
                    event_id=new_id(),
                    instrument_id=instrument_id,
                    fiscal_year=raw.get("fiscalYear", 0) or 0,
                    fiscal_quarter=raw.get("fiscalQuarter"),
                    period_end=date.fromisoformat(raw["fiscalDateEnding"]) if raw.get("fiscalDateEnding") else None,
                    report_date=date.fromisoformat(report_date_str),
                    event_time_code=raw.get("time", "UNKNOWN").upper() if raw.get("time") else "UNKNOWN",
                    eps_estimate=raw.get("epsEstimated"),
                    eps_actual=raw.get("eps"),
                    revenue_estimate=raw.get("revenueEstimated"),
                    revenue_actual=raw.get("revenue"),
                    source="fmp",
                    raw_payload=raw,
                ))
                counters["inserted"] += 1

            except Exception as e:
                counters["errors"] += 1
                logger.error("sync_earnings.entry_error", error=str(e))

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()
        logger.info("sync_earnings.complete", symbol=symbol, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
