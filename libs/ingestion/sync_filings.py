"""Sync SEC filings for an instrument."""
from __future__ import annotations

from datetime import date, datetime, UTC

from sqlalchemy.orm import Session

from libs.adapters.sec_adapter import SECAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.filing import Filing
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def sync_filings(session: Session, cik: str, instrument_id: str) -> dict:
    """Sync SEC filings for a given CIK."""
    run = SourceRun(
        run_id=new_id(), source="sec", job_name="sync_filings",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"inserted": 0, "skipped": 0, "errors": 0}

    try:
        adapter = SECAdapter()
        submissions = await adapter.get_submissions(cik)

        recent = submissions.get("filings", {}).get("recent", {})
        accession_numbers = recent.get("accessionNumber", [])
        form_types = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        primary_docs = recent.get("primaryDocument", [])
        period_ends = recent.get("reportDate", [])

        for i in range(len(accession_numbers)):
            try:
                accession_no = accession_numbers[i].replace("-", "")
                form_type = form_types[i] if i < len(form_types) else ""
                filing_date_str = filing_dates[i] if i < len(filing_dates) else ""
                period_end_str = period_ends[i] if i < len(period_ends) else ""

                filing = Filing(
                    filing_id=new_id(),
                    instrument_id=instrument_id,
                    cik=cik,
                    accession_no=accession_no,
                    form_type=form_type,
                    filing_date=date.fromisoformat(filing_date_str) if filing_date_str else date.today(),
                    period_end=date.fromisoformat(period_end_str) if period_end_str else None,
                    primary_doc_url=primary_docs[i] if i < len(primary_docs) else None,
                    source="sec",
                    raw_payload={"index": i, "accession": accession_numbers[i]},
                )
                session.add(filing)
                counters["inserted"] += 1

            except Exception as e:
                counters["errors"] += 1
                logger.error("sync_filings.entry_error", error=str(e), index=i)

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()
        logger.info("sync_filings.complete", cik=cik, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
