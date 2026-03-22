"""Sync corporate actions (splits, dividends) from Massive."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from libs.adapters.massive_adapter import MassiveAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.corporate_action import CorporateAction
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def sync_corporate_actions(
    session: Session,
    ticker: str,
    instrument_id: str,
) -> dict:
    """Sync splits and dividends for a single ticker."""
    run = SourceRun(
        run_id=new_id(), source="massive", job_name="sync_corporate_actions",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"splits": 0, "dividends": 0, "errors": 0}

    try:
        adapter = MassiveAdapter()

        # Splits
        splits = await adapter.get_splits(ticker)
        for raw in splits:
            try:
                norm = adapter.normalize_split(raw)
                ex_date = date.fromisoformat(norm["ex_date"]) if norm.get("ex_date") else None
                if not ex_date:
                    continue
                session.add(CorporateAction(
                    action_id=new_id(),
                    instrument_id=instrument_id,
                    action_type="split",
                    ex_date=ex_date,
                    split_from=norm.get("split_from"),
                    split_to=norm.get("split_to"),
                    source="massive",
                    raw_payload=raw,
                ))
                counters["splits"] += 1
            except Exception as e:
                counters["errors"] += 1
                logger.error("sync_ca.split_error", error=str(e))

        # Dividends
        dividends = await adapter.get_dividends(ticker)
        for raw in dividends:
            try:
                norm = adapter.normalize_dividend(raw)
                ex_date = date.fromisoformat(norm["ex_date"]) if norm.get("ex_date") else None
                if not ex_date:
                    continue
                session.add(CorporateAction(
                    action_id=new_id(),
                    instrument_id=instrument_id,
                    action_type="cash_dividend",
                    ex_date=ex_date,
                    record_date=date.fromisoformat(norm["record_date"]) if norm.get("record_date") else None,
                    pay_date=date.fromisoformat(norm["pay_date"]) if norm.get("pay_date") else None,
                    cash_amount=norm.get("cash_amount"),
                    currency=norm.get("currency", "USD"),
                    source="massive",
                    raw_payload=raw,
                ))
                counters["dividends"] += 1
            except Exception as e:
                counters["errors"] += 1
                logger.error("sync_ca.dividend_error", error=str(e))

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()
        logger.info("sync_ca.complete", ticker=ticker, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
