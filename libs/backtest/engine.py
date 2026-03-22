"""Minimal backtest engine.

Supports:
- Reading research signals / screener results
- Generating trades and positions
- Computing portfolio NAV path
- Outputting core metrics

Design: vectorized bar-by-bar simulation, not tick-level event-driven.
All data comes from the real database via session.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from libs.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CostModel:
    """Transaction cost model."""
    commission_per_share: float = 0.0
    commission_min: float = 0.0
    slippage_bps: float = 5.0  # basis points

    def compute_cost(self, qty: float, price: float) -> float:
        """Compute total transaction cost for a trade."""
        commission = max(abs(qty) * self.commission_per_share, self.commission_min)
        slippage = abs(qty) * price * (self.slippage_bps / 10000)
        return commission + slippage


@dataclass
class PortfolioConfig:
    """Portfolio construction config."""
    initial_capital: float = 100_000.0
    max_positions: int = 10
    weight_scheme: str = "equal"  # "equal" or "custom"
    rebalance_frequency: str = "monthly"  # "daily", "weekly", "monthly"
    max_weight_per_position: float = 0.25


@dataclass
class Trade:
    """A single trade record."""
    trade_date: date
    instrument_id: str
    ticker: str
    side: str  # "buy" or "sell"
    qty: float
    price: float
    cost: float
    notional: float


@dataclass
class BacktestResult:
    """Result of a backtest run."""
    nav_series: pd.DataFrame  # date, nav, daily_return
    trades: list[Trade]
    metrics: dict[str, float]
    positions_history: pd.DataFrame | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        lines = ["=== Backtest Summary ==="]
        for k, v in self.metrics.items():
            if isinstance(v, float):
                lines.append(f"  {k}: {v:.4f}")
            else:
                lines.append(f"  {k}: {v}")
        lines.append(f"  total_trades: {len(self.trades)}")
        return "\n".join(lines)


def _load_universe_prices(
    session: Session,
    instrument_ids: list[str],
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """Load close prices for multiple instruments, pivoted by date."""
    if not instrument_ids:
        return pd.DataFrame()

    placeholders = ", ".join(f"'{iid}'" for iid in instrument_ids)
    sql = text(f"""
        SELECT p.trade_date, p.instrument_id::text, p.close,
               ii.id_value as ticker
        FROM price_bar_raw p
        LEFT JOIN instrument_identifier ii
            ON p.instrument_id = ii.instrument_id
            AND ii.id_type = 'ticker' AND ii.source = 'sec'
        WHERE p.instrument_id::text IN ({placeholders})
          AND p.trade_date >= :start AND p.trade_date <= :end
        ORDER BY p.trade_date
    """)
    df = pd.read_sql(sql, session.bind, params={"start": start_date, "end": end_date})
    if df.empty:
        return df
    df["close"] = df["close"].astype(float)
    return df


def _get_rebalance_dates(dates: pd.Index, frequency: str) -> set[date]:
    """Determine which dates trigger a rebalance."""
    if frequency == "daily":
        return set(dates)

    rebal = set()
    if frequency == "weekly":
        for d in dates:
            if d.weekday() == 0:  # Monday
                rebal.add(d)
    elif frequency == "monthly":
        current_month = None
        for d in dates:
            if current_month != d.month:
                rebal.add(d)
                current_month = d.month

    # Always rebalance on first date
    if len(dates) > 0:
        rebal.add(dates[0])

    return rebal


def run_backtest(
    session: Session,
    instrument_ids: list[str],
    start_date: date,
    end_date: date,
    config: PortfolioConfig | None = None,
    cost_model: CostModel | None = None,
    signal_fn=None,
) -> BacktestResult:
    """Run a simple equal-weight or signal-based backtest.

    Args:
        session: DB session
        instrument_ids: Universe of instruments to trade
        start_date: Backtest start
        end_date: Backtest end
        config: Portfolio config (default: equal weight, monthly rebalance)
        cost_model: Transaction costs (default: 5bps slippage)
        signal_fn: Optional callable(date, prices_df) -> dict[instrument_id, weight]
                   If None, uses equal weight for all instruments.
    """
    if config is None:
        config = PortfolioConfig()
    if cost_model is None:
        cost_model = CostModel()

    # Load prices
    raw = _load_universe_prices(session, instrument_ids, start_date, end_date)
    if raw.empty:
        return BacktestResult(
            nav_series=pd.DataFrame(),
            trades=[],
            metrics={"error": "no price data"},
        )

    # Build ticker map
    ticker_map = {}
    for _, row in raw[["instrument_id", "ticker"]].drop_duplicates().iterrows():
        ticker_map[row["instrument_id"]] = row["ticker"] or row["instrument_id"][:8]

    # Pivot to wide format: date x instrument_id
    prices = raw.pivot_table(index="trade_date", columns="instrument_id", values="close")
    prices = prices.sort_index().ffill()

    dates = prices.index
    rebalance_dates = _get_rebalance_dates(dates, config.rebalance_frequency)

    # Simulation
    cash = config.initial_capital
    positions: dict[str, float] = {}  # instrument_id -> qty
    trades: list[Trade] = []
    nav_records = []

    n_positions = min(len(instrument_ids), config.max_positions)

    for d in dates:
        row = prices.loc[d]

        # Mark to market
        portfolio_value = cash
        for iid, qty in positions.items():
            if iid in row.index and not pd.isna(row[iid]):
                portfolio_value += qty * row[iid]

        # Rebalance?
        if d in rebalance_dates:
            # Determine target weights
            if signal_fn:
                target_weights = signal_fn(d, prices.loc[:d])
            else:
                # Equal weight across all available instruments
                available = [iid for iid in instrument_ids if iid in row.index and not pd.isna(row[iid]) and row[iid] > 0]
                n = min(len(available), n_positions)
                if n > 0:
                    w = min(1.0 / n, config.max_weight_per_position)
                    target_weights = {iid: w for iid in available[:n]}
                else:
                    target_weights = {}

            # Generate trades
            for iid, target_w in target_weights.items():
                if iid not in row.index or pd.isna(row[iid]) or row[iid] <= 0:
                    continue
                price = row[iid]
                target_value = portfolio_value * target_w
                target_qty = int(target_value / price)
                current_qty = positions.get(iid, 0)
                delta = target_qty - current_qty

                if abs(delta) < 1:
                    continue

                cost = cost_model.compute_cost(delta, price)
                side = "buy" if delta > 0 else "sell"

                trades.append(Trade(
                    trade_date=d,
                    instrument_id=iid,
                    ticker=ticker_map.get(iid, ""),
                    side=side,
                    qty=abs(delta),
                    price=price,
                    cost=cost,
                    notional=abs(delta) * price,
                ))

                cash -= delta * price + cost
                positions[iid] = target_qty

            # Close positions not in target
            for iid in list(positions.keys()):
                if iid not in target_weights and positions[iid] != 0:
                    price = row.get(iid, 0)
                    if price and not pd.isna(price) and price > 0:
                        qty = positions[iid]
                        cost = cost_model.compute_cost(qty, price)
                        trades.append(Trade(
                            trade_date=d,
                            instrument_id=iid,
                            ticker=ticker_map.get(iid, ""),
                            side="sell",
                            qty=abs(qty),
                            price=price,
                            cost=cost,
                            notional=abs(qty) * price,
                        ))
                        cash += qty * price - cost
                        del positions[iid]

        # Record NAV
        nav = cash
        for iid, qty in positions.items():
            if iid in row.index and not pd.isna(row[iid]):
                nav += qty * row[iid]

        nav_records.append({"trade_date": d, "nav": nav})

    # Build NAV series
    nav_df = pd.DataFrame(nav_records)
    if not nav_df.empty:
        nav_df["daily_return"] = nav_df["nav"].pct_change()

    # Compute metrics
    metrics = _compute_metrics(nav_df, trades, config)

    return BacktestResult(
        nav_series=nav_df,
        trades=trades,
        metrics=metrics,
        config={
            "initial_capital": config.initial_capital,
            "max_positions": config.max_positions,
            "weight_scheme": config.weight_scheme,
            "rebalance_frequency": config.rebalance_frequency,
            "cost_model": {
                "commission_per_share": cost_model.commission_per_share,
                "slippage_bps": cost_model.slippage_bps,
            },
            "start_date": str(start_date),
            "end_date": str(end_date),
            "universe_size": len(instrument_ids),
        },
    )


def _compute_metrics(nav_df: pd.DataFrame, trades: list[Trade], config: PortfolioConfig) -> dict:
    """Compute backtest performance metrics."""
    if nav_df.empty or len(nav_df) < 2:
        return {}

    returns = nav_df["daily_return"].dropna()
    if returns.empty:
        return {}

    total_return = (nav_df["nav"].iloc[-1] / nav_df["nav"].iloc[0]) - 1
    trading_days = len(returns)
    years = trading_days / 252
    ann_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
    ann_vol = returns.std() * np.sqrt(252) if len(returns) > 1 else 0
    sharpe = ann_return / ann_vol if ann_vol > 0 else 0

    # Max drawdown
    cum = (1 + returns).cumprod()
    peak = cum.cummax()
    dd = (cum - peak) / peak
    max_dd = dd.min() if not dd.empty else 0

    # Turnover
    total_traded = sum(t.notional for t in trades)
    avg_nav = nav_df["nav"].mean()
    turnover = total_traded / avg_nav if avg_nav > 0 else 0

    # Costs
    total_costs = sum(t.cost for t in trades)

    return {
        "total_return": float(total_return),
        "annualized_return": float(ann_return),
        "annualized_volatility": float(ann_vol),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd),
        "trading_days": int(trading_days),
        "total_trades": len(trades),
        "total_turnover": float(turnover),
        "total_costs": float(total_costs),
        "final_nav": float(nav_df["nav"].iloc[-1]),
        "initial_capital": float(config.initial_capital),
    }
