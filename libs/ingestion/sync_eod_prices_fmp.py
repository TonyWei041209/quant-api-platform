"""Sync EOD prices from FMP (production primary path).

This is the production-recommended price ingestion path.
Uses FMP stable API endpoints with source='fmp'.

NOTE: FMP returns split-adjusted prices by default. We store them
as source='fmp' and document that FMP prices are adjusted.
For raw unadjusted prices, use Massive/Polygon adapter.
"""
from __future__ import annotations

import asyncio
import json
from datetime import date

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from libs.adapters.fmp_adapter import FMPAdapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.price_bar_raw import PriceBarRaw
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)

SOURCE = "fmp"


async def sync_eod_prices_fmp(
    session: Session,
    ticker: str,
    instrument_id: str,
    from_date: str = "",
    to_date: str = "",
) -> dict:
    """Sync EOD bars from FMP stable API.

    This is the production primary path for price data.
    """
    run = SourceRun(
        run_id=new_id(),
        source=SOURCE,
        job_name="sync_eod_prices_fmp",
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()

    counters = {"inserted": 0, "skipped": 0, "errors": 0}

    try:
        adapter = FMPAdapter()
        bars = await adapter.get_eod_prices(ticker, from_date=from_date, to_date=to_date)

        for bar in bars:
            try:
                norm = adapter.normalize_price(bar)
                trade_date_str = norm.get("trade_date")
                if not trade_date_str:
                    counters["errors"] += 1
                    continue

                trade_date = date.fromisoformat(str(trade_date_str))
                raw_json = json.dumps(bar, default=str)

                stmt = pg_insert(PriceBarRaw).values(
                    instrument_id=instrument_id,
                    trade_date=trade_date,
                    source=SOURCE,
                    open=norm["open"],
                    high=norm["high"],
                    low=norm["low"],
                    close=norm["close"],
                    volume=norm["volume"],
                    vwap=norm.get("vwap"),
                    ingested_at=utc_now(),
                    raw_payload=raw_json,
                ).on_conflict_do_nothing(
                    index_elements=["instrument_id", "trade_date", "source"],
                )
                session.execute(stmt)
                counters["inserted"] += 1

            except Exception as e:
                counters["errors"] += 1
                logger.error("sync_eod_fmp.bar_error", error=str(e))

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()

        logger.info("sync_eod_fmp.complete", ticker=ticker, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters


async def sync_fundamentals_fmp(
    session: Session,
    ticker: str,
    instrument_id: str,
    limit: int = 2,
) -> dict:
    """Sync financial statements from FMP stable API.

    This is the production primary path for financial data.
    """
    from libs.db.models.financial_period import FinancialPeriod
    from libs.db.models.financial_fact_std import FinancialFactStd

    run = SourceRun(
        run_id=new_id(),
        source=SOURCE,
        job_name="sync_fundamentals_fmp",
        started_at=utc_now(),
        status="running",
    )
    session.add(run)
    session.flush()

    counters = {"periods": 0, "facts": 0, "errors": 0}

    try:
        adapter = FMPAdapter()
        income = await adapter.get_income_statement(ticker, limit=limit)
        balance = await adapter.get_balance_sheet(ticker, limit=limit)
        cashflow = await adapter.get_cash_flow(ticker, limit=limit)

        fq_map = {"FY": 0, "Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}

        for stmt_list, stmt_type in [
            (income, "income"), (balance, "balance"), (cashflow, "cashflow")
        ]:
            for stmt in stmt_list:
                period_end = stmt.get("date")
                if not period_end:
                    continue

                fy = stmt.get("calendarYear", period_end[:4])
                fq_raw = stmt.get("period", "FY")
                scope = "annual" if fq_raw == "FY" else "quarterly"
                fq = fq_map.get(fq_raw, 0)
                reported_at = (
                    stmt.get("fillingDate")
                    or stmt.get("acceptedDate")
                    or period_end
                )

                # Check existing
                existing = session.query(FinancialPeriod).filter(
                    FinancialPeriod.instrument_id == instrument_id,
                    FinancialPeriod.period_end == period_end,
                    FinancialPeriod.source == SOURCE,
                    FinancialPeriod.statement_scope == scope,
                ).first()

                if existing:
                    fp_id = existing.financial_period_id
                else:
                    fp_id = new_id()
                    fp = FinancialPeriod(
                        financial_period_id=fp_id,
                        instrument_id=instrument_id,
                        statement_scope=scope,
                        fiscal_year=int(fy) if fy else 2024,
                        fiscal_quarter=fq,
                        period_end=period_end,
                        reported_at=reported_at,
                        source=SOURCE,
                        ingested_at=utc_now(),
                    )
                    session.add(fp)
                    counters["periods"] += 1

                # Insert facts
                facts = adapter.normalize_financial(stmt, stmt_type)
                for fact in facts:
                    stmt_insert = pg_insert(FinancialFactStd).values(
                        financial_period_id=fp_id,
                        statement_type=fact["statement_type"],
                        metric_code=fact["metric_code"],
                        metric_value=fact["metric_value"],
                        unit=fact["unit"],
                        source=SOURCE,
                        ingested_at=utc_now(),
                    ).on_conflict_do_nothing()
                    session.execute(stmt_insert)
                    counters["facts"] += 1

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()

        logger.info("sync_fundamentals_fmp.complete", ticker=ticker, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
