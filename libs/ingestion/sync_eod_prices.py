"""Sync EOD prices from Massive (raw unadjusted)."""
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from libs.adapters.massive_adapter import MassiveAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.price_bar_raw import PriceBarRaw
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def sync_eod_prices(
    session: Session,
    ticker: str,
    instrument_id: str,
    from_date: str,
    to_date: str,
) -> dict:
    """Sync raw EOD bars for a single ticker.

    IMPORTANT: Always uses adjusted=false for raw prices.
    """
    run = SourceRun(
        run_id=new_id(),
        source="massive",
        job_name="sync_eod_prices",
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()

    counters = {"inserted": 0, "skipped": 0, "errors": 0}

    try:
        adapter = MassiveAdapter()
        bars = await adapter.get_eod_bars(ticker, from_date, to_date, adjusted=False)

        for bar in bars:
            try:
                normalized = adapter.normalize(bar)
                # Convert unix ms timestamp to date
                trade_ts = normalized.get("trade_date")
                if isinstance(trade_ts, (int, float)):
                    from datetime import datetime, UTC
                    trade_date = datetime.fromtimestamp(trade_ts / 1000, tz=UTC).date()
                else:
                    trade_date = date.fromisoformat(str(trade_ts)) if trade_ts else None

                if trade_date is None:
                    counters["errors"] += 1
                    continue

                stmt = pg_insert(PriceBarRaw).values(
                    instrument_id=instrument_id,
                    trade_date=trade_date,
                    source="massive",
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
                session.execute(stmt)
                counters["inserted"] += 1

            except Exception as e:
                counters["errors"] += 1
                logger.error("sync_eod.bar_error", error=str(e))

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()

        logger.info("sync_eod.complete", ticker=ticker, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
