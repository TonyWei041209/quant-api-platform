"""Backtest API endpoints."""
from __future__ import annotations

import uuid
from datetime import date as dt_date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class BacktestRequest(BaseModel):
    strategy: str = "momentum"
    tickers: list[str] = ["AAPL", "MSFT", "NVDA", "SPY"]
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    commission_bps: float = 5.0
    slippage_bps: float = 5.0
    max_positions: int = 20
    rebalance_freq: str = "monthly"
    # Realistic cost model (all optional, default 0 preserves legacy behavior)
    spread_bps: float = 0.0
    fx_fee_bps: float = 0.0
    base_currency: str = "USD"
    volume_impact_bps: float = 0.0
    volume_impact_threshold: float = 0.01
    commission_per_share: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_tickers(db: Session, tickers: list[str]) -> dict[str, str]:
    """Return {ticker: instrument_id_str} for the given ticker symbols."""
    rows = db.execute(
        text(
            "SELECT ii.id_value, i.instrument_id::text "
            "FROM instrument_identifier ii "
            "JOIN instrument i ON i.instrument_id = ii.instrument_id "
            "WHERE ii.id_type = 'ticker' AND ii.id_value = ANY(:tickers)"
        ),
        {"tickers": [t.strip().upper() for t in tickers]},
    ).fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/run")
def run_backtest_endpoint(req: BacktestRequest, db: Session = Depends(get_sync_db)) -> dict:
    """Run a new backtest and persist results."""
    instrument_map = _resolve_tickers(db, req.tickers)
    if not instrument_map:
        raise HTTPException(status_code=404, detail="No instruments found for the given tickers")

    from libs.backtest.engine import run_and_persist_backtest, CostModel, PortfolioConfig

    cost = CostModel(
        slippage_bps=req.slippage_bps,
        commission_per_share=req.commission_per_share,
        spread_bps=req.spread_bps,
        fx_fee_bps=req.fx_fee_bps,
        base_currency=req.base_currency,
        volume_impact_bps=req.volume_impact_bps,
        volume_impact_threshold=req.volume_impact_threshold,
    )
    config = PortfolioConfig(
        max_positions=req.max_positions,
        rebalance_frequency=req.rebalance_freq,
    )

    result, run_id = run_and_persist_backtest(
        session=db,
        instrument_ids=list(instrument_map.values()),
        start_date=dt_date.fromisoformat(req.start_date),
        end_date=dt_date.fromisoformat(req.end_date),
        strategy_name=req.strategy,
        config=config,
        cost_model=cost,
    )
    db.commit()

    return {
        "run_id": str(run_id),
        "strategy": req.strategy,
        "tickers": req.tickers,
        "start_date": req.start_date,
        "end_date": req.end_date,
        "metrics": result.metrics,
    }


@router.get("/runs")
def list_runs(
    strategy: str = Query(None, description="Filter by strategy name"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_sync_db),
) -> dict:
    """List past backtest runs."""
    from libs.backtest.persistence import list_backtest_runs

    runs = list_backtest_runs(db, strategy_name=strategy)
    items = []
    for r in runs[:limit]:
        items.append({
            "run_id": str(r.run_id),
            "strategy_name": r.strategy_name,
            "start_date": str(r.start_date) if r.start_date else None,
            "end_date": str(r.end_date) if r.end_date else None,
            "total_return": r.total_return,
            "sharpe_ratio": r.sharpe_ratio,
            "max_drawdown": r.max_drawdown,
            "total_trades": r.total_trades,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return {"runs": items, "count": len(items)}


@router.get("/runs/{run_id}")
def get_run(run_id: str, db: Session = Depends(get_sync_db)) -> dict:
    """Get a specific backtest run with all metrics."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")

    from libs.backtest.persistence import load_backtest_run

    run = load_backtest_run(db, rid)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    return {
        "run_id": str(run.run_id),
        "strategy_name": run.strategy_name,
        "start_date": str(run.start_date) if run.start_date else None,
        "end_date": str(run.end_date) if run.end_date else None,
        "config": run.config,
        "total_return": run.total_return,
        "annualized_return": run.annualized_return,
        "volatility": run.volatility,
        "sharpe_ratio": run.sharpe_ratio,
        "max_drawdown": run.max_drawdown,
        "total_trades": run.total_trades,
        "turnover": run.turnover,
        "total_costs": run.total_costs,
        "status": run.status,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.get("/runs/{run_id}/trades")
def get_run_trades(run_id: str, db: Session = Depends(get_sync_db)) -> dict:
    """Get trades for a backtest run."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")

    from libs.backtest.persistence import load_backtest_run, load_backtest_trades

    run = load_backtest_run(db, rid)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    trades = load_backtest_trades(db, rid)
    items = []
    for t in trades:
        items.append({
            "trade_id": str(t.trade_id),
            "instrument_id": str(t.instrument_id),
            "trade_date": str(t.trade_date),
            "side": t.side,
            "quantity": t.quantity,
            "price": t.price,
            "commission": t.commission,
            "slippage_cost": t.slippage_cost,
            "notional": t.notional,
        })
    return {"run_id": run_id, "trades": items, "count": len(items)}


@router.get("/runs/{run_id}/nav")
def get_run_nav(run_id: str, db: Session = Depends(get_sync_db)) -> dict:
    """Get NAV series for a backtest run."""
    try:
        rid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")

    from libs.backtest.persistence import load_backtest_run

    run = load_backtest_run(db, rid)
    if not run:
        raise HTTPException(status_code=404, detail="Backtest run not found")

    return {"run_id": run_id, "nav_series": run.nav_series or {}}
