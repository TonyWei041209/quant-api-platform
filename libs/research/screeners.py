"""Stock screener — filter and rank instruments by factor criteria.

All screens operate on real database data with explicit time boundaries.

Every screener function requires an explicit asof_date parameter
to prevent look-ahead bias.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from libs.core.logging import get_logger

logger = get_logger(__name__)


def screen_by_liquidity(
    session: Session,
    min_avg_volume: float = 1_000_000,
    lookback_days: int = 20,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Screen instruments by average daily volume.

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with: instrument_id, ticker, avg_volume, last_close
    """
    start = asof_date - timedelta(days=int(lookback_days * 1.5))

    sql = text("""
        WITH vol AS (
            SELECT p.instrument_id,
                   AVG(p.volume) as avg_volume,
                   (ARRAY_AGG(p.close ORDER BY p.trade_date DESC))[1] as last_close,
                   COUNT(*) as bar_count
            FROM price_bar_raw p
            WHERE p.trade_date >= :start AND p.trade_date <= :asof_date
            GROUP BY p.instrument_id
            HAVING AVG(p.volume) >= :min_vol
        )
        SELECT v.instrument_id::text, ii.id_value as ticker,
               v.avg_volume, v.last_close, v.bar_count
        FROM vol v
        LEFT JOIN instrument_identifier ii
            ON v.instrument_id = ii.instrument_id
            AND ii.id_type = 'ticker' AND ii.source = 'sec'
        ORDER BY v.avg_volume DESC
    """)
    return pd.read_sql(sql, session.bind, params={
        "start": start, "asof_date": asof_date, "min_vol": min_avg_volume,
    })


def screen_by_returns(
    session: Session,
    lookback_days: int = 63,
    min_return: float | None = None,
    max_return: float | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Screen instruments by N-day return.

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with: instrument_id, ticker, period_return, start_price, end_price
    """
    start = asof_date - timedelta(days=int(lookback_days * 1.5))

    sql = text("""
        WITH prices AS (
            SELECT instrument_id, trade_date, close,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date ASC) as rn_asc,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) as rn_desc
            FROM price_bar_raw
            WHERE trade_date >= :start AND trade_date <= :asof_date
        ),
        endpoints AS (
            SELECT instrument_id,
                   MAX(CASE WHEN rn_asc = 1 THEN close END) as start_price,
                   MAX(CASE WHEN rn_desc = 1 THEN close END) as end_price
            FROM prices
            GROUP BY instrument_id
            HAVING MAX(CASE WHEN rn_asc = 1 THEN close END) > 0
        )
        SELECT e.instrument_id::text, ii.id_value as ticker,
               (e.end_price / e.start_price - 1) as period_return,
               e.start_price, e.end_price
        FROM endpoints e
        LEFT JOIN instrument_identifier ii
            ON e.instrument_id = ii.instrument_id
            AND ii.id_type = 'ticker' AND ii.source = 'sec'
        WHERE (:min_ret IS NULL OR (e.end_price / e.start_price - 1) >= :min_ret)
          AND (:max_ret IS NULL OR (e.end_price / e.start_price - 1) <= :max_ret)
        ORDER BY (e.end_price / e.start_price - 1) DESC
    """)
    return pd.read_sql(sql, session.bind, params={
        "start": start, "asof_date": asof_date,
        "min_ret": min_return, "max_ret": max_return,
    })


def screen_by_fundamentals(
    session: Session,
    max_pe: float | None = None,
    min_revenue: float | None = None,
    min_net_income: float | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Screen instruments by fundamental metrics (PIT-safe).

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with: instrument_id, ticker, revenue, net_income, pe_proxy
    """
    from datetime import datetime, UTC

    asof_time = datetime.combine(asof_date, datetime.max.time()).replace(tzinfo=UTC)

    sql = text("""
        WITH latest_annual AS (
            SELECT DISTINCT ON (instrument_id)
                instrument_id, financial_period_id, fiscal_year, period_end
            FROM financial_period
            WHERE statement_scope = 'annual'
              AND reported_at <= :asof_time
            ORDER BY instrument_id, period_end DESC
        ),
        facts AS (
            SELECT la.instrument_id, la.fiscal_year,
                   MAX(CASE WHEN ff.metric_code IN ('Revenues', 'RevenueFromContractWithCustomerExcludingAssessedTax')
                       THEN ff.metric_value END) as revenue,
                   MAX(CASE WHEN ff.metric_code = 'NetIncomeLoss' THEN ff.metric_value END) as net_income,
                   MAX(CASE WHEN ff.metric_code = 'CommonStockSharesOutstanding' THEN ff.metric_value END) as shares
            FROM latest_annual la
            JOIN financial_fact_std ff ON la.financial_period_id = ff.financial_period_id
            GROUP BY la.instrument_id, la.fiscal_year
        ),
        with_price AS (
            SELECT f.*,
                   (SELECT close FROM price_bar_raw p
                    WHERE p.instrument_id = f.instrument_id AND p.trade_date <= :asof_date
                    ORDER BY p.trade_date DESC LIMIT 1) as last_close
            FROM facts f
        )
        SELECT wp.instrument_id::text, ii.id_value as ticker,
               wp.fiscal_year, wp.revenue, wp.net_income, wp.shares, wp.last_close,
               CASE WHEN wp.net_income > 0 AND wp.shares > 0 AND wp.last_close > 0
                    THEN (wp.last_close * wp.shares) / wp.net_income END as pe_proxy
        FROM with_price wp
        LEFT JOIN instrument_identifier ii
            ON wp.instrument_id = ii.instrument_id
            AND ii.id_type = 'ticker' AND ii.source = 'sec'
        WHERE (:min_rev IS NULL OR wp.revenue >= :min_rev)
          AND (:min_ni IS NULL OR wp.net_income >= :min_ni)
          AND (:max_pe IS NULL OR wp.net_income <= 0
               OR (wp.last_close * wp.shares) / wp.net_income <= :max_pe)
        ORDER BY wp.revenue DESC NULLS LAST
    """)
    return pd.read_sql(sql, session.bind, params={
        "asof_time": asof_time, "asof_date": asof_date,
        "min_rev": min_revenue, "min_ni": min_net_income, "max_pe": max_pe,
    })


def rank_universe(
    session: Session,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Rank all instruments by multiple factors.

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with: instrument_id, ticker, return_63d, avg_volume_20d,
    volatility_20d, and composite rank.
    """
    returns_df = screen_by_returns(session, lookback_days=63, asof_date=asof_date)
    liquidity_df = screen_by_liquidity(session, min_avg_volume=0, asof_date=asof_date)

    if returns_df.empty or liquidity_df.empty:
        return pd.DataFrame()

    merged = returns_df.merge(
        liquidity_df[["instrument_id", "avg_volume"]],
        on="instrument_id", how="inner",
    )

    if merged.empty:
        return merged

    # Rank each factor (higher is better for returns and volume)
    merged["return_rank"] = merged["period_return"].rank(ascending=False)
    merged["volume_rank"] = merged["avg_volume"].rank(ascending=False)
    merged["composite_rank"] = (merged["return_rank"] + merged["volume_rank"]) / 2
    merged = merged.sort_values("composite_rank")

    return merged
