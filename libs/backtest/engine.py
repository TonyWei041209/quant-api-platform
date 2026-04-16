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

import uuid
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
    """Realistic transaction cost model.

    Models the full chain of retail-broker execution friction:
      commission + slippage + spread + fx_fee + volume_impact

    All components default to 0 (or flat 5 bps slippage) for backward
    compatibility. Legacy ``compute_cost()`` returns the aggregate. New
    callers should use ``compute_cost_breakdown()`` to audit each component.
    """
    # --- legacy (kept for backward compatibility) ---
    commission_per_share: float = 0.0
    commission_min: float = 0.0
    slippage_bps: float = 5.0  # flat slippage bps (applied regardless of size)

    # --- realistic additions (default 0 = no change from legacy) ---
    spread_bps: float = 0.0          # bid/ask half-spread per side (T212 ~5-20bps depending on stock)
    fx_fee_bps: float = 0.0          # applied only when instrument currency != base_currency
    base_currency: str = "USD"
    volume_impact_bps: float = 0.0   # multiplier when trade size breaches volume threshold
    volume_impact_threshold: float = 0.01  # 1% of daily volume triggers impact

    def compute_cost_breakdown(
        self,
        qty: float,
        price: float,
        *,
        currency: str | None = None,
        daily_volume: float | None = None,
    ) -> dict[str, float]:
        """Return each cost component separately.

        Args:
            qty: Trade quantity (signed ignored, absolute value used).
            price: Execution price.
            currency: Instrument currency. If != base_currency, fx_fee applies.
            daily_volume: Daily traded volume (shares) at the trade date.
                If provided and qty/daily_volume > threshold, volume_impact applies.

        Returns:
            {commission, slippage, spread, fx_fee, volume_impact, total}
        """
        notional = abs(qty) * price
        commission = max(abs(qty) * self.commission_per_share, self.commission_min)
        slippage = notional * (self.slippage_bps / 10000.0)
        spread = notional * (self.spread_bps / 10000.0)

        fx_fee = 0.0
        if currency and currency != self.base_currency and self.fx_fee_bps > 0:
            fx_fee = notional * (self.fx_fee_bps / 10000.0)

        volume_impact = 0.0
        if (
            daily_volume
            and daily_volume > 0
            and self.volume_impact_bps > 0
            and self.volume_impact_threshold > 0
        ):
            participation = abs(qty) / daily_volume
            if participation > self.volume_impact_threshold:
                # Linear impact: extra bps proportional to excess participation
                excess = participation - self.volume_impact_threshold
                impact_bps = self.volume_impact_bps * (excess / self.volume_impact_threshold)
                volume_impact = notional * (impact_bps / 10000.0)

        total = commission + slippage + spread + fx_fee + volume_impact
        return {
            "commission": commission,
            "slippage": slippage,
            "spread": spread,
            "fx_fee": fx_fee,
            "volume_impact": volume_impact,
            "total": total,
        }

    def compute_cost(
        self,
        qty: float,
        price: float,
        *,
        currency: str | None = None,
        daily_volume: float | None = None,
    ) -> float:
        """Aggregate cost (backward-compatible signature)."""
        return self.compute_cost_breakdown(
            qty, price, currency=currency, daily_volume=daily_volume
        )["total"]


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
    instrument_id: uuid.UUID
    ticker: str
    side: str  # "buy" or "sell"
    qty: float
    price: float
    cost: float  # aggregate cost (kept for backward compatibility)
    notional: float
    # Cost breakdown (all default 0 for backward compatibility)
    commission: float = 0.0
    slippage: float = 0.0
    spread: float = 0.0
    fx_fee: float = 0.0
    volume_impact: float = 0.0


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
    """Load close prices + volume for multiple instruments, pivoted by date.

    Returns long-format DataFrame with columns: trade_date, instrument_id,
    close, volume, ticker.
    """
    if not instrument_ids:
        return pd.DataFrame()

    placeholders = ", ".join(f"'{iid}'" for iid in instrument_ids)
    sql = text(f"""
        SELECT p.trade_date, p.instrument_id::text, p.close, p.volume,
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
    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce").fillna(0).astype(float)
    return df


def _load_instrument_currencies(
    session: Session,
    instrument_ids: list[str],
) -> dict[str, str]:
    """Load currency per instrument. Returns {instrument_id_str: currency}."""
    if not instrument_ids:
        return {}
    placeholders = ", ".join(f"'{iid}'" for iid in instrument_ids)
    rows = session.execute(text(f"""
        SELECT instrument_id::text, COALESCE(currency, 'USD')
        FROM instrument
        WHERE instrument_id::text IN ({placeholders})
    """)).fetchall()
    return {row[0]: row[1] for row in rows}


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

    # Load prices (+ volume)
    raw = _load_universe_prices(session, instrument_ids, start_date, end_date)
    if raw.empty:
        return BacktestResult(
            nav_series=pd.DataFrame(),
            trades=[],
            metrics={"error": "no price data"},
        )

    # Load currency per instrument (for FX fee calculation)
    currency_map = _load_instrument_currencies(session, instrument_ids)

    # Build ticker map
    ticker_map = {}
    for _, row in raw[["instrument_id", "ticker"]].drop_duplicates().iterrows():
        ticker_map[row["instrument_id"]] = row["ticker"] or row["instrument_id"][:8]

    # Pivot to wide format: date x instrument_id
    prices = raw.pivot_table(index="trade_date", columns="instrument_id", values="close")
    prices = prices.sort_index().ffill()

    # Pivot volume too (may be empty/NaN for some bars)
    volumes = raw.pivot_table(index="trade_date", columns="instrument_id", values="volume") if "volume" in raw.columns else pd.DataFrame()

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

            # Helper to compute cost breakdown with currency + volume context
            def _compute(qty_signed: float, price: float, iid: str) -> dict:
                vol = None
                if not volumes.empty and iid in volumes.columns:
                    v = volumes.loc[d, iid] if d in volumes.index else None
                    if v is not None and not pd.isna(v) and v > 0:
                        vol = float(v)
                return cost_model.compute_cost_breakdown(
                    qty_signed, price,
                    currency=currency_map.get(iid),
                    daily_volume=vol,
                )

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

                breakdown = _compute(delta, price, iid)
                side = "buy" if delta > 0 else "sell"

                trades.append(Trade(
                    trade_date=d,
                    instrument_id=uuid.UUID(iid),
                    ticker=ticker_map.get(iid, ""),
                    side=side,
                    qty=abs(delta),
                    price=price,
                    cost=breakdown["total"],
                    notional=abs(delta) * price,
                    commission=breakdown["commission"],
                    slippage=breakdown["slippage"],
                    spread=breakdown["spread"],
                    fx_fee=breakdown["fx_fee"],
                    volume_impact=breakdown["volume_impact"],
                ))

                cash -= delta * price + breakdown["total"]
                positions[iid] = target_qty

            # Close positions not in target
            for iid in list(positions.keys()):
                if iid not in target_weights and positions[iid] != 0:
                    price = row.get(iid, 0)
                    if price and not pd.isna(price) and price > 0:
                        qty = positions[iid]
                        breakdown = _compute(qty, price, iid)
                        trades.append(Trade(
                            trade_date=d,
                            instrument_id=uuid.UUID(iid),
                            ticker=ticker_map.get(iid, ""),
                            side="sell",
                            qty=abs(qty),
                            price=price,
                            cost=breakdown["total"],
                            notional=abs(qty) * price,
                            commission=breakdown["commission"],
                            slippage=breakdown["slippage"],
                            spread=breakdown["spread"],
                            fx_fee=breakdown["fx_fee"],
                            volume_impact=breakdown["volume_impact"],
                        ))
                        cash += qty * price - breakdown["total"]
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
                "commission_min": cost_model.commission_min,
                "slippage_bps": cost_model.slippage_bps,
                "spread_bps": cost_model.spread_bps,
                "fx_fee_bps": cost_model.fx_fee_bps,
                "base_currency": cost_model.base_currency,
                "volume_impact_bps": cost_model.volume_impact_bps,
                "volume_impact_threshold": cost_model.volume_impact_threshold,
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

    # Costs (aggregate + breakdown)
    total_costs = sum(t.cost for t in trades)
    total_commission = sum(t.commission for t in trades)
    total_slippage = sum(t.slippage for t in trades)
    total_spread = sum(t.spread for t in trades)
    total_fx_fee = sum(t.fx_fee for t in trades)
    total_volume_impact = sum(t.volume_impact for t in trades)

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
        "cost_breakdown": {
            "commission": float(total_commission),
            "slippage": float(total_slippage),
            "spread": float(total_spread),
            "fx_fee": float(total_fx_fee),
            "volume_impact": float(total_volume_impact),
        },
        "final_nav": float(nav_df["nav"].iloc[-1]),
        "initial_capital": float(config.initial_capital),
    }


def run_and_persist_backtest(
    session: Session,
    instrument_ids: list[str],
    start_date: date,
    end_date: date,
    strategy_name: str,
    config: PortfolioConfig | None = None,
    cost_model: CostModel | None = None,
    signal_fn=None,
) -> tuple[BacktestResult, uuid.UUID]:
    """Run a backtest and persist the results to the database.

    This is a convenience wrapper around ``run_backtest`` followed by
    ``persist_backtest_result``.  The original ``run_backtest`` remains a
    pure-computation function with no side effects.

    Args:
        session: SQLAlchemy session (caller manages commit/rollback).
        instrument_ids: Universe of instruments to trade.
        start_date: Backtest start date.
        end_date: Backtest end date.
        strategy_name: Human-readable strategy label stored with the run.
        config: Portfolio config (default: equal weight, monthly rebalance).
        cost_model: Transaction costs (default: 5 bps slippage).
        signal_fn: Optional signal function (see ``run_backtest``).

    Returns:
        A tuple of (BacktestResult, run_id).
    """
    from libs.backtest.persistence import persist_backtest_result

    result = run_backtest(
        session=session,
        instrument_ids=instrument_ids,
        start_date=start_date,
        end_date=end_date,
        config=config,
        cost_model=cost_model,
        signal_fn=signal_fn,
    )

    run_id = persist_backtest_result(
        session=session,
        result=result,
        strategy_name=strategy_name,
        instrument_ids=instrument_ids,
        config=result.config,
        trades=result.trades,
    )

    logger.info("backtest persisted", run_id=str(run_id), strategy=strategy_name)
    return result, run_id
