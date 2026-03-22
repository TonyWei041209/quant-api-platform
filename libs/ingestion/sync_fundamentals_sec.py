"""Sync fundamentals from SEC companyfacts (XBRL) — no API key required."""
from __future__ import annotations

from datetime import date, datetime, UTC

from sqlalchemy.orm import Session

from libs.adapters.sec_adapter import SECAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.financial_period import FinancialPeriod
from libs.db.models.financial_fact_std import FinancialFactStd
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)

# Key metrics to extract from SEC companyfacts
KEY_METRICS = {
    "income": [
        "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
        "CostOfGoodsAndServicesSold", "CostOfRevenue",
        "GrossProfit", "OperatingIncomeLoss", "NetIncomeLoss",
        "EarningsPerShareBasic", "EarningsPerShareDiluted",
    ],
    "balance": [
        "Assets", "Liabilities", "StockholdersEquity",
        "CashAndCashEquivalentsAtCarryingValue",
        "LongTermDebt", "LongTermDebtNoncurrent",
        "CommonStockSharesOutstanding",
    ],
    "cashflow": [
        "NetCashProvidedByUsedInOperatingActivities",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsOfDividends", "PaymentsForRepurchaseOfCommonStock",
    ],
}


async def sync_fundamentals_sec(
    session: Session, cik: str, instrument_id: str,
) -> dict:
    """Sync fundamentals from SEC companyfacts."""
    run = SourceRun(
        run_id=new_id(), source="sec", job_name="sync_fundamentals_sec",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"periods_created": 0, "facts_created": 0, "errors": 0}

    try:
        sec = SECAdapter()
        company_facts = await sec.get_company_facts(cik)
        us_gaap = company_facts.get("facts", {}).get("us-gaap", {})

        # Phase 1: collect latest entry per (fy, fp, form, metric) then bulk insert
        # SEC companyfacts has multiple entries per metric (amendments, restates)
        # We take the latest filing for each (fy, fp, metric)
        period_map: dict[tuple, FinancialPeriod] = {}
        # (period_key, stmt_type, metric_name) -> (value, unit, filed_date)
        fact_latest: dict[tuple, tuple] = {}

        for stmt_type, metric_names in KEY_METRICS.items():
            for metric_name in metric_names:
                concept = us_gaap.get(metric_name, {})
                for unit_type, entries in concept.get("units", {}).items():
                    if unit_type not in ("USD", "shares"):
                        continue
                    for entry in entries:
                        try:
                            fy = entry.get("fy")
                            fp = entry.get("fp", "")
                            form = entry.get("form", "")
                            filed = entry.get("filed", "")
                            end_str = entry.get("end", "")

                            if not fy or not end_str or not filed:
                                continue
                            if form not in ("10-K", "10-Q"):
                                continue
                            # Only take annual (FY) and quarterly (Q1-Q4)
                            if fp not in ("FY", "Q1", "Q2", "Q3", "Q4"):
                                continue

                            period_key = (fy, fp)
                            fact_key = (period_key, stmt_type, metric_name)

                            # Keep latest filing
                            if fact_key in fact_latest:
                                existing_filed = fact_latest[fact_key][2]
                                if filed <= existing_filed:
                                    continue

                            period_end = date.fromisoformat(end_str)
                            reported_at = datetime.combine(
                                date.fromisoformat(filed), datetime.min.time()
                            ).replace(tzinfo=UTC)

                            fact_latest[fact_key] = (float(entry["val"]), unit_type, filed, period_end, reported_at, entry.get("accn"))

                        except Exception as e:
                            counters["errors"] += 1

        # Now create periods first, flush, then insert facts
        # Pass 1: collect unique periods
        for (period_key, stmt_type, metric_name), (val, unit, filed, period_end, reported_at, accn) in fact_latest.items():
            fy, fp = period_key
            if period_key not in period_map:
                scope = "annual" if fp == "FY" else "quarterly"
                quarter = None
                if fp.startswith("Q"):
                    try:
                        quarter = int(fp[1:])
                    except ValueError:
                        pass
                fp_obj = FinancialPeriod(
                    financial_period_id=new_id(),
                    instrument_id=instrument_id,
                    statement_scope=scope,
                    fiscal_year=fy,
                    fiscal_quarter=quarter,
                    period_end=period_end,
                    reported_at=reported_at,
                    filing_accession_no=accn,
                    source="sec",
                )
                session.add(fp_obj)
                period_map[period_key] = fp_obj
                counters["periods_created"] += 1

        # Flush periods so FKs exist
        session.flush()

        # Pass 2: insert facts
        for (period_key, stmt_type, metric_name), (val, unit, filed, period_end, reported_at, accn) in fact_latest.items():
            fp_obj = period_map[period_key]
            session.add(FinancialFactStd(
                financial_period_id=fp_obj.financial_period_id,
                statement_type=stmt_type,
                metric_code=metric_name,
                source="sec",
                metric_value=val,
                unit=unit,
            ))
            counters["facts_created"] += 1

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()
        logger.info("sync_fundamentals_sec.complete", cik=cik, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
