"""Persistence layer for backtest results.

Saves BacktestResult data into backtest_run / backtest_trade tables.
"""
from __future__ import annotations

import json
import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from libs.backtest.engine import BacktestResult, Trade
from libs.db.models.backtest_run import BacktestRun
from libs.db.models.backtest_trade import BacktestTrade


def persist_backtest_result(
    session: Session,
    result: BacktestResult,
    strategy_name: str,
    instrument_ids: list[str],
    config: dict[str, Any],
    trades: list[Trade],
) -> uuid.UUID:
    """Persist a BacktestResult to the database.

    Args:
        session: SQLAlchemy session (caller manages commit/rollback).
        result: The BacktestResult returned by run_backtest.
        strategy_name: Human-readable strategy name.
        instrument_ids: Universe of instrument UUIDs (as strings).
        config: Raw config dict (stored as JSONB).
        trades: List of Trade objects from the backtest.

    Returns:
        The generated run_id (UUID).
    """
    metrics = result.metrics

    # Build NAV series as JSON: {"YYYY-MM-DD": nav_value, ...}
    nav_json: dict[str, float] | None = None
    if result.nav_series is not None and not result.nav_series.empty:
        nav_json = {
            str(row["trade_date"]): float(row["nav"])
            for _, row in result.nav_series.iterrows()
        }

    # Extract cost-model params from config if available
    cost_cfg = config.get("cost_model", {})
    commission_bps = cost_cfg.get("commission_per_share", 0.0)
    slippage_bps = cost_cfg.get("slippage_bps", 0.0)

    # Parse date range from config
    start_date = _parse_date(config.get("start_date"))
    end_date = _parse_date(config.get("end_date"))

    run = BacktestRun(
        strategy_name=strategy_name,
        universe_description=f"{len(instrument_ids)} instruments",
        start_date=start_date,
        end_date=end_date,
        config=config,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
        total_return=metrics.get("total_return"),
        annualized_return=metrics.get("annualized_return"),
        volatility=metrics.get("annualized_volatility"),
        sharpe_ratio=metrics.get("sharpe_ratio"),
        max_drawdown=metrics.get("max_drawdown"),
        total_trades=metrics.get("total_trades"),
        turnover=metrics.get("total_turnover"),
        total_costs=metrics.get("total_costs"),
        nav_series=nav_json,
        status="completed",
    )
    session.add(run)
    session.flush()  # populate run.run_id

    # Persist individual trades (convert numpy types to native Python)
    for t in trades:
        bt = BacktestTrade(
            run_id=run.run_id,
            instrument_id=t.instrument_id,
            trade_date=t.trade_date,
            side=t.side.upper(),
            quantity=float(t.qty),
            price=float(t.price),
            commission=float(t.cost),
            slippage_cost=0.0,
            notional=float(t.notional),
        )
        session.add(bt)

    session.flush()
    return run.run_id


def load_backtest_run(session: Session, run_id: uuid.UUID) -> BacktestRun | None:
    """Load a single BacktestRun by its run_id.

    Returns None if not found.
    """
    return session.get(BacktestRun, run_id)


def list_backtest_runs(
    session: Session,
    strategy_name: str | None = None,
    start_after: date | None = None,
    start_before: date | None = None,
) -> list[BacktestRun]:
    """List BacktestRun records with optional filters.

    Args:
        session: SQLAlchemy session.
        strategy_name: Filter by exact strategy name.
        start_after: Only runs whose start_date >= this value.
        start_before: Only runs whose start_date <= this value.

    Returns:
        List of BacktestRun records ordered by created_at descending.
    """
    stmt = select(BacktestRun)

    if strategy_name is not None:
        stmt = stmt.where(BacktestRun.strategy_name == strategy_name)
    if start_after is not None:
        stmt = stmt.where(BacktestRun.start_date >= start_after)
    if start_before is not None:
        stmt = stmt.where(BacktestRun.start_date <= start_before)

    stmt = stmt.order_by(BacktestRun.created_at.desc())
    return list(session.scalars(stmt).all())


def load_backtest_trades(session: Session, run_id: uuid.UUID) -> list[BacktestTrade]:
    """Load all BacktestTrade records for a given run.

    Returns:
        List of BacktestTrade records ordered by trade_date.
    """
    stmt = (
        select(BacktestTrade)
        .where(BacktestTrade.run_id == run_id)
        .order_by(BacktestTrade.trade_date)
    )
    return list(session.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(val: Any) -> date | None:
    """Convert a string or date to a date object."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))
