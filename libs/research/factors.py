"""Factor computation primitives.

All functions accept a SQLAlchemy session and instrument_id,
returning pandas DataFrames or Series. Time alignment is explicit.

Every function that touches market data requires an explicit asof_date
parameter to prevent look-ahead bias.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from libs.core.logging import get_logger

logger = get_logger(__name__)


def get_daily_returns(
    session: Session,
    instrument_id: str,
    start_date: date | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Compute daily simple returns from raw close prices.

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with columns: trade_date, close, daily_return
    """
    sql = text("""
        SELECT trade_date, close
        FROM price_bar_raw
        WHERE instrument_id = :iid
          AND (:start IS NULL OR trade_date >= :start)
          AND trade_date <= :end
        ORDER BY trade_date
    """)
    df = pd.read_sql(sql, session.bind, params={"iid": instrument_id, "start": start_date, "end": asof_date})
    if df.empty:
        return df
    df["close"] = df["close"].astype(float)
    df["daily_return"] = df["close"].pct_change()
    return df


def rolling_volatility(
    session: Session,
    instrument_id: str,
    window: int = 20,
    start_date: date | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
    annualize: bool = True,
) -> pd.DataFrame:
    """Compute rolling volatility of daily returns.

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with columns: trade_date, close, daily_return, volatility
    """
    df = get_daily_returns(session, instrument_id, start_date, asof_date)
    if df.empty:
        return df
    df["volatility"] = df["daily_return"].rolling(window=window).std()
    if annualize:
        df["volatility"] = df["volatility"] * np.sqrt(252)
    return df


def cumulative_return(
    session: Session,
    instrument_id: str,
    start_date: date | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Compute cumulative return series.

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with columns: trade_date, close, daily_return, cum_return
    """
    df = get_daily_returns(session, instrument_id, start_date, asof_date)
    if df.empty:
        return df
    df["cum_return"] = (1 + df["daily_return"].fillna(0)).cumprod() - 1
    return df


def drawdown(
    session: Session,
    instrument_id: str,
    start_date: date | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Compute drawdown series from peak.

    asof_date is required to prevent look-ahead bias.

    Returns DataFrame with columns: trade_date, close, peak, drawdown, max_drawdown
    """
    sql = text("""
        SELECT trade_date, close
        FROM price_bar_raw
        WHERE instrument_id = :iid
          AND (:start IS NULL OR trade_date >= :start)
          AND trade_date <= :end
        ORDER BY trade_date
    """)
    df = pd.read_sql(sql, session.bind, params={"iid": instrument_id, "start": start_date, "end": asof_date})
    if df.empty:
        return df
    df["close"] = df["close"].astype(float)
    df["peak"] = df["close"].cummax()
    df["drawdown"] = (df["close"] - df["peak"]) / df["peak"]
    df["max_drawdown"] = df["drawdown"].cummin()
    return df


def relative_strength(
    session: Session,
    instrument_id: str,
    benchmark_id: str,
    start_date: date | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
) -> pd.DataFrame:
    """Compute relative strength vs a benchmark.

    asof_date is required to prevent look-ahead bias.

    RS = cumulative_return(stock) / cumulative_return(benchmark)
    """
    stock = get_daily_returns(session, instrument_id, start_date, asof_date)
    bench = get_daily_returns(session, benchmark_id, start_date, asof_date)
    if stock.empty or bench.empty:
        return pd.DataFrame()

    stock = stock.set_index("trade_date")
    bench = bench.set_index("trade_date")

    merged = stock[["close"]].join(bench[["close"]], rsuffix="_bench", how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged["stock_cum"] = merged["close"].pct_change().fillna(0).add(1).cumprod()
    merged["bench_cum"] = merged["close_bench"].pct_change().fillna(0).add(1).cumprod()
    merged["relative_strength"] = merged["stock_cum"] / merged["bench_cum"]

    return merged.reset_index()


def momentum(
    session: Session,
    instrument_id: str,
    lookback_days: int = 252,
    skip_recent: int = 21,
    asof_date: date = ...,  # type: ignore[assignment]
) -> float | None:
    """Compute momentum factor: return over lookback period, skipping recent days.

    asof_date is required to prevent look-ahead bias.
    Lookback and skip windows are computed relative to asof_date.

    Classic 12-1 month momentum: lookback_days=252, skip_recent=21
    """
    # Use 2x multiplier to ensure enough trading days within calendar days
    start = asof_date - timedelta(days=int((lookback_days + skip_recent) * 2))

    sql = text("""
        SELECT trade_date, close
        FROM price_bar_raw
        WHERE instrument_id = :iid
          AND trade_date >= :start AND trade_date <= :end
        ORDER BY trade_date
    """)
    df = pd.read_sql(sql, session.bind, params={"iid": instrument_id, "start": start, "end": asof_date})
    if len(df) < lookback_days + skip_recent:
        return None

    df["close"] = df["close"].astype(float)

    end_idx = len(df) - skip_recent - 1
    start_idx = end_idx - lookback_days

    if start_idx < 0 or end_idx < 0:
        return None

    return (df.iloc[end_idx]["close"] / df.iloc[start_idx]["close"]) - 1


def valuation_snapshot(
    session: Session,
    instrument_id: str,
    asof_date: date = ...,  # type: ignore[assignment]
) -> dict:
    """Compute simple valuation metrics from latest PIT financials + price.

    asof_date is required to prevent look-ahead bias.
    Price lookup uses only prices <= asof_date.

    Returns dict with: latest_price, revenue, net_income, total_assets, equity,
    market_cap_proxy, pe_ratio, pb_ratio (where computable).
    """
    from datetime import datetime, UTC

    asof_time = datetime.combine(asof_date, datetime.max.time()).replace(tzinfo=UTC)

    # Latest price — only use prices <= asof_date
    price_sql = text("""
        SELECT close FROM price_bar_raw
        WHERE instrument_id = :iid AND trade_date <= :asof
        ORDER BY trade_date DESC LIMIT 1
    """)
    price_row = session.execute(price_sql, {"iid": instrument_id, "asof": asof_date}).fetchone()
    latest_price = float(price_row[0]) if price_row else None

    # Latest PIT financials
    fin_sql = text("""
        WITH latest_period AS (
            SELECT financial_period_id, fiscal_year, period_end
            FROM financial_period
            WHERE instrument_id = :iid
              AND statement_scope = 'annual'
              AND reported_at <= :asof_time
            ORDER BY period_end DESC LIMIT 1
        )
        SELECT ff.metric_code, ff.metric_value
        FROM financial_fact_std ff
        JOIN latest_period lp ON ff.financial_period_id = lp.financial_period_id
    """)
    facts = session.execute(fin_sql, {"iid": instrument_id, "asof_time": asof_time}).fetchall()
    metrics = {row[0]: float(row[1]) for row in facts}

    revenue = metrics.get("Revenues") or metrics.get("RevenueFromContractWithCustomerExcludingAssessedTax")
    net_income = metrics.get("NetIncomeLoss")
    total_assets = metrics.get("Assets")
    equity = metrics.get("StockholdersEquity")
    shares = metrics.get("CommonStockSharesOutstanding")

    result = {
        "latest_price": latest_price,
        "revenue": revenue,
        "net_income": net_income,
        "total_assets": total_assets,
        "equity": equity,
        "shares_outstanding": shares,
    }

    # Derived ratios
    if latest_price and shares and shares > 0:
        market_cap = latest_price * shares
        result["market_cap_proxy"] = market_cap
        if net_income and net_income > 0:
            result["pe_ratio"] = market_cap / net_income
        if equity and equity > 0:
            result["pb_ratio"] = market_cap / equity

    if net_income and revenue and revenue > 0:
        result["net_margin"] = net_income / revenue

    return result


def performance_summary(
    session: Session,
    instrument_id: str,
    start_date: date | None = None,
    asof_date: date = ...,  # type: ignore[assignment]
) -> dict:
    """Compute a summary of performance statistics.

    asof_date is required to prevent look-ahead bias.

    Returns dict with: total_return, annualized_return, volatility,
    max_drawdown, sharpe_ratio (rf=0), trading_days.
    """
    df = get_daily_returns(session, instrument_id, start_date, asof_date)
    if df.empty or len(df) < 2:
        return {}

    returns = df["daily_return"].dropna()
    if returns.empty:
        return {}

    total_ret = (1 + returns).prod() - 1
    trading_days = len(returns)
    years = trading_days / 252
    ann_ret = (1 + total_ret) ** (1 / years) - 1 if years > 0 else 0
    ann_vol = returns.std() * np.sqrt(252)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0

    # Max drawdown
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    max_dd = dd.min()

    return {
        "total_return": float(total_ret),
        "annualized_return": float(ann_ret),
        "annualized_volatility": float(ann_vol),
        "max_drawdown": float(max_dd),
        "sharpe_ratio": float(sharpe),
        "trading_days": int(trading_days),
    }
