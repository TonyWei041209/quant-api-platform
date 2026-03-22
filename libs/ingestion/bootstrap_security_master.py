"""Bootstrap security master from SEC + OpenFIGI."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from libs.adapters.sec_adapter import SECAdapter
from libs.adapters.openfigi_adapter import OpenFIGIAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.instrument import Instrument
from libs.db.models.identifier import InstrumentIdentifier
from libs.db.models.ticker_history import TickerHistory
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def bootstrap_security_master(session: Session, limit: int | None = None) -> dict:
    """Bootstrap instruments from SEC company tickers + OpenFIGI mapping.

    Args:
        session: SQLAlchemy sync session
        limit: Max number of companies to process (None = all)

    Returns:
        Counters dict with inserted/skipped/errors counts.
    """
    run = SourceRun(
        run_id=new_id(),
        source="sec",
        job_name="bootstrap_security_master",
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()

    counters = {"instruments_created": 0, "identifiers_created": 0, "errors": 0}

    try:
        sec = SECAdapter()
        tickers_data = await sec.get_company_tickers()

        if limit:
            tickers_data = tickers_data[:limit]

        for entry in tickers_data:
            try:
                normalized = sec.normalize(entry)
                cik = normalized["cik"]
                ticker = normalized["ticker"]
                name = normalized["issuer_name"]

                if not ticker or not name:
                    continue

                instrument_id = new_id()
                instrument = Instrument(
                    instrument_id=instrument_id,
                    asset_type="common_stock",
                    issuer_name_current=name,
                    exchange_primary="US",
                    currency="USD",
                    country_code="US",
                    is_active=True,
                )
                session.add(instrument)

                # CIK identifier
                session.add(InstrumentIdentifier(
                    instrument_id=instrument_id,
                    id_type="cik",
                    id_value=cik,
                    source="sec",
                    valid_from=date(2000, 1, 1),
                    is_primary=True,
                ))

                # Ticker identifier
                session.add(InstrumentIdentifier(
                    instrument_id=instrument_id,
                    id_type="ticker",
                    id_value=ticker,
                    source="sec",
                    valid_from=date(2000, 1, 1),
                    is_primary=True,
                ))

                # Ticker history
                session.add(TickerHistory(
                    instrument_id=instrument_id,
                    ticker=ticker,
                    effective_from=date(2000, 1, 1),
                    issuer_name=name,
                    exchange="US",
                    source="sec",
                ))

                counters["instruments_created"] += 1
                counters["identifiers_created"] += 2

                if counters["instruments_created"] % 500 == 0:
                    session.flush()
                    logger.info("bootstrap.progress", count=counters["instruments_created"])

            except Exception as e:
                counters["errors"] += 1
                logger.error("bootstrap.entry_error", error=str(e), entry=str(entry)[:200])

        # Attempt OpenFIGI enrichment for first batch
        try:
            figi_adapter = OpenFIGIAdapter()
            sample_tickers = tickers_data[:10] if len(tickers_data) > 10 else tickers_data
            jobs = [{"idType": "TICKER", "idValue": sec.normalize(t)["ticker"], "exchCode": "US"}
                    for t in sample_tickers if sec.normalize(t)["ticker"]]
            if jobs:
                figi_results = await figi_adapter.map_identifiers(jobs[:100])
                logger.info("bootstrap.figi_enrichment", results_count=len(figi_results))
                # TODO: match FIGI results back to instruments and insert identifiers
        except Exception as e:
            logger.warning("bootstrap.figi_failed", error=str(e))

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()

        logger.info("bootstrap.complete", **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
