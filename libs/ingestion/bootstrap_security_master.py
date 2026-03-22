"""Bootstrap security master from SEC + OpenFIGI."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

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


async def bootstrap_security_master(
    session: Session,
    limit: int | None = None,
    tickers_filter: list[str] | None = None,
) -> dict:
    """Bootstrap instruments from SEC company tickers + OpenFIGI mapping.

    Args:
        session: SQLAlchemy sync session
        limit: Max number of companies to process (None = all)
        tickers_filter: If provided, only bootstrap these tickers
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

    counters = {"instruments_created": 0, "identifiers_created": 0, "figi_enriched": 0, "skipped": 0, "errors": 0}

    try:
        sec = SECAdapter()
        tickers_data = await sec.get_company_tickers()

        # Filter to specific tickers if requested
        if tickers_filter:
            filter_set = {t.upper() for t in tickers_filter}
            tickers_data = [e for e in tickers_data if sec.normalize(e).get("ticker", "").upper() in filter_set]
            logger.info("bootstrap.filtered", requested=len(filter_set), matched=len(tickers_data))

        if limit:
            tickers_data = tickers_data[:limit]

        # Build a map of ticker -> instrument_id for FIGI enrichment
        ticker_to_instrument: dict[str, uuid.UUID] = {}

        # Check existing tickers to avoid duplicates
        existing_tickers_result = session.execute(
            select(InstrumentIdentifier.id_value).where(
                InstrumentIdentifier.id_type == "ticker",
                InstrumentIdentifier.source == "sec",
            )
        )
        existing_tickers = {row[0].upper() for row in existing_tickers_result}

        for entry in tickers_data:
            try:
                normalized = sec.normalize(entry)
                cik = normalized["cik"]
                ticker = normalized["ticker"]
                name = normalized["issuer_name"]

                if not ticker or not name:
                    continue

                if ticker.upper() in existing_tickers:
                    counters["skipped"] += 1
                    # Find existing instrument_id for FIGI enrichment
                    existing = session.execute(
                        select(InstrumentIdentifier.instrument_id).where(
                            InstrumentIdentifier.id_type == "ticker",
                            InstrumentIdentifier.id_value == ticker.upper(),
                            InstrumentIdentifier.source == "sec",
                        )
                    ).first()
                    if existing:
                        ticker_to_instrument[ticker.upper()] = existing[0]
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
                    id_value=ticker.upper(),
                    source="sec",
                    valid_from=date(2000, 1, 1),
                    is_primary=True,
                ))

                # Ticker history
                session.add(TickerHistory(
                    instrument_id=instrument_id,
                    ticker=ticker.upper(),
                    effective_from=date(2000, 1, 1),
                    issuer_name=name,
                    exchange="US",
                    source="sec",
                ))

                ticker_to_instrument[ticker.upper()] = instrument_id
                counters["instruments_created"] += 1
                counters["identifiers_created"] += 2

            except Exception as e:
                counters["errors"] += 1
                logger.error("bootstrap.entry_error", error=str(e), entry=str(entry)[:200])

        session.flush()

        # OpenFIGI enrichment — complete write-back
        if ticker_to_instrument:
            try:
                figi_adapter = OpenFIGIAdapter()
                tickers_to_enrich = list(ticker_to_instrument.keys())

                # Process in batches of 100 (OpenFIGI limit)
                for batch_start in range(0, len(tickers_to_enrich), 100):
                    batch = tickers_to_enrich[batch_start:batch_start + 100]
                    jobs = [{"idType": "TICKER", "idValue": t, "exchCode": "US"} for t in batch]

                    figi_results = await figi_adapter.map_identifiers(jobs)

                    for i, result_set in enumerate(figi_results):
                        if i >= len(batch):
                            break
                        ticker = batch[i]
                        instrument_id = ticker_to_instrument.get(ticker)
                        if not instrument_id:
                            continue

                        if isinstance(result_set, dict) and "data" in result_set:
                            for figi_item in result_set["data"][:1]:  # Take first match
                                normalized = figi_adapter.normalize(figi_item)
                                today = date.today()

                                # Write FIGI
                                if normalized.get("figi"):
                                    session.merge(InstrumentIdentifier(
                                        instrument_id=instrument_id,
                                        id_type="figi",
                                        id_value=normalized["figi"],
                                        source="openfigi",
                                        valid_from=today,
                                        is_primary=True,
                                    ))
                                    counters["figi_enriched"] += 1

                                # Write composite FIGI
                                if normalized.get("composite_figi"):
                                    session.merge(InstrumentIdentifier(
                                        instrument_id=instrument_id,
                                        id_type="composite_figi",
                                        id_value=normalized["composite_figi"],
                                        source="openfigi",
                                        valid_from=today,
                                        is_primary=False,
                                    ))

                                # Write share class FIGI
                                if normalized.get("share_class_figi"):
                                    session.merge(InstrumentIdentifier(
                                        instrument_id=instrument_id,
                                        id_type="share_class_figi",
                                        id_value=normalized["share_class_figi"],
                                        source="openfigi",
                                        valid_from=today,
                                        is_primary=False,
                                    ))

                    logger.info("bootstrap.figi_batch", batch_size=len(batch), enriched=counters["figi_enriched"])

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
