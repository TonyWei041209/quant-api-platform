"""DEV-ONLY: Load real EOD prices via yfinance for development/validation.

WARNING: This is NOT a production data source. yfinance is an unofficial wrapper.
Production must use Massive/Polygon or FMP with proper API keys.
Data loaded here is tagged with source='yfinance_dev' for traceability.

This loader exists solely so the pipeline can be validated end-to-end
with real market data before production API keys are configured.
"""
from __future__ import annotations

from datetime import date, datetime, UTC

import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.price_bar_raw import PriceBarRaw
from libs.db.models.corporate_action import CorporateAction
from libs.db.models.earnings_event import EarningsEvent
from libs.db.models.instrument import Instrument
from libs.db.models.identifier import InstrumentIdentifier
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)

SOURCE = "yfinance_dev"


def _resolve_instrument_id(session: Session, ticker: str) -> str | None:
    """Resolve ticker to instrument_id."""
    result = session.execute(
        select(InstrumentIdentifier.instrument_id).where(
            InstrumentIdentifier.id_type == "ticker",
            InstrumentIdentifier.id_value == ticker.upper(),
        )
    ).first()
    return str(result[0]) if result else None


def load_eod_prices(
    session: Session,
    ticker: str,
    start: str = "2020-01-01",
    end: str | None = None,
) -> dict:
    """Load raw unadjusted EOD bars from yfinance.

    yfinance returns adjusted close by default. We request auto_adjust=False
    to get raw (unadjusted) OHLC + separate adjusted close.
    We store ONLY the raw unadjusted OHLC in price_bar_raw.
    """
    instrument_id = _resolve_instrument_id(session, ticker)
    if not instrument_id:
        raise ValueError(f"Ticker {ticker} not found in instrument_identifier")

    run = SourceRun(
        run_id=new_id(), source=SOURCE, job_name="dev_load_eod_prices",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"inserted": 0, "skipped": 0, "errors": 0}

    try:
        stock = yf.Ticker(ticker)
        df = stock.history(start=start, end=end, auto_adjust=False)

        if df.empty:
            logger.warning("dev_load.no_data", ticker=ticker)
            run.status = "success"
            run.finished_at = utc_now()
            run.counters = counters
            session.commit()
            return counters

        for trade_date, row in df.iterrows():
            try:
                td = trade_date.date() if hasattr(trade_date, 'date') else trade_date

                stmt = pg_insert(PriceBarRaw).values(
                    instrument_id=instrument_id,
                    trade_date=td,
                    source=SOURCE,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    volume=int(row["Volume"]),
                    raw_payload={
                        "adj_close": float(row["Adj Close"]) if "Adj Close" in row.index else None,
                        "dividends": float(row["Dividends"]) if "Dividends" in row.index else 0,
                        "stock_splits": float(row["Stock Splits"]) if "Stock Splits" in row.index else 0,
                    },
                    ingested_at=utc_now(),
                ).on_conflict_do_nothing(
                    index_elements=["instrument_id", "trade_date", "source"],
                )
                result = session.execute(stmt)
                if result.rowcount > 0:
                    counters["inserted"] += 1
                else:
                    counters["skipped"] += 1

            except Exception as e:
                counters["errors"] += 1
                logger.error("dev_load.bar_error", error=str(e))

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()
        logger.info("dev_load.prices_complete", ticker=ticker, **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters


def load_corporate_actions(session: Session, ticker: str) -> dict:
    """Load splits and dividends from yfinance."""
    instrument_id = _resolve_instrument_id(session, ticker)
    if not instrument_id:
        raise ValueError(f"Ticker {ticker} not found")

    counters = {"splits": 0, "dividends": 0, "errors": 0}

    try:
        stock = yf.Ticker(ticker)

        # Splits
        splits = stock.splits
        if splits is not None and not splits.empty:
            for split_date, ratio in splits.items():
                if ratio == 0:
                    continue
                td = split_date.date() if hasattr(split_date, 'date') else split_date
                # yfinance ratio: e.g., 4.0 means 4-for-1 split
                session.add(CorporateAction(
                    action_id=new_id(),
                    instrument_id=instrument_id,
                    action_type="split",
                    ex_date=td,
                    split_from=1,
                    split_to=float(ratio),
                    source=SOURCE,
                    raw_payload={"ratio": float(ratio)},
                ))
                counters["splits"] += 1

        # Dividends
        dividends = stock.dividends
        if dividends is not None and not dividends.empty:
            for div_date, amount in dividends.items():
                if amount <= 0:
                    continue
                td = div_date.date() if hasattr(div_date, 'date') else div_date
                session.add(CorporateAction(
                    action_id=new_id(),
                    instrument_id=instrument_id,
                    action_type="cash_dividend",
                    ex_date=td,
                    cash_amount=float(amount),
                    currency="USD",
                    source=SOURCE,
                    raw_payload={"amount": float(amount)},
                ))
                counters["dividends"] += 1

        session.commit()
        logger.info("dev_load.corp_actions_complete", ticker=ticker, **counters)

    except Exception as e:
        logger.error("dev_load.corp_actions_error", ticker=ticker, error=str(e))
        raise

    return counters


def load_earnings_events(session: Session, ticker: str) -> dict:
    """Load earnings events from yfinance."""
    instrument_id = _resolve_instrument_id(session, ticker)
    if not instrument_id:
        raise ValueError(f"Ticker {ticker} not found")

    counters = {"inserted": 0, "errors": 0}

    try:
        stock = yf.Ticker(ticker)

        # Earnings dates
        try:
            earnings_dates = stock.earnings_dates
        except Exception:
            earnings_dates = None

        if earnings_dates is not None and not earnings_dates.empty:
            for report_dt, row in earnings_dates.iterrows():
                try:
                    rd = report_dt.date() if hasattr(report_dt, 'date') else report_dt

                    eps_estimate = None
                    eps_actual = None
                    if "EPS Estimate" in row.index:
                        try:
                            eps_estimate = float(row["EPS Estimate"])
                        except (ValueError, TypeError):
                            pass
                    if "Reported EPS" in row.index:
                        try:
                            eps_actual = float(row["Reported EPS"])
                        except (ValueError, TypeError):
                            pass

                    session.add(EarningsEvent(
                        event_id=new_id(),
                        instrument_id=instrument_id,
                        fiscal_year=rd.year,
                        report_date=rd,
                        event_time_code="UNKNOWN",
                        eps_estimate=eps_estimate,
                        eps_actual=eps_actual,
                        source=SOURCE,
                        raw_payload={
                            k: (float(v) if isinstance(v, (int, float)) and str(v) != 'nan' else str(v))
                            for k, v in row.items()
                        },
                    ))
                    counters["inserted"] += 1

                except Exception as e:
                    counters["errors"] += 1
                    logger.error("dev_load.earnings_error", error=str(e))

        session.commit()
        logger.info("dev_load.earnings_complete", ticker=ticker, **counters)

    except Exception as e:
        logger.error("dev_load.earnings_error", ticker=ticker, error=str(e))
        raise

    return counters
