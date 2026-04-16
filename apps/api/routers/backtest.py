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


class RealisticCostConfig(BaseModel):
    """Realistic cost settings for Strategy Honesty Report.

    Defaults model a T212 GBP account buying US stocks — a typical retail
    European broker scenario.
    """
    slippage_bps: float = 5.0
    spread_bps: float = 10.0          # typical US large cap spread
    fx_fee_bps: float = 15.0          # T212 FX conversion fee
    base_currency: str = "GBP"
    commission_per_share: float = 0.0
    volume_impact_bps: float = 0.0
    volume_impact_threshold: float = 0.01


class HonestyReportRequest(BaseModel):
    """Runs two backtests (legacy vs realistic cost) and compares them.

    Neither run is persisted — this is a diagnostic report, not a saved run.
    """
    tickers: list[str] = ["AAPL", "MSFT", "NVDA", "SPY"]
    start_date: str = "2023-01-01"
    end_date: str = "2024-12-31"
    max_positions: int = 20
    rebalance_freq: str = "monthly"
    # Legacy "textbook" cost: single slippage bps, nothing else
    legacy_slippage_bps: float = 5.0
    # Realistic cost: full component breakdown
    realistic: RealisticCostConfig = RealisticCostConfig()


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


def _verdict_from_retention(retention_pct: float, realistic_return: float) -> tuple[str, str]:
    """Translate return retention into an honesty verdict.

    retention_pct: realistic_return / legacy_return * 100 (for positive returns)
    realistic_return: needed to catch the "positive legacy, negative realistic" case
    """
    if realistic_return <= 0:
        return (
            "illusion",
            "Realistic cost turns this strategy unprofitable — legacy backtest "
            "return is a pure accounting illusion.",
        )
    if retention_pct >= 85:
        return (
            "honest",
            "Strategy retains most of its textbook return after realistic "
            "execution costs. Edge appears durable.",
        )
    if retention_pct >= 50:
        return (
            "degraded",
            "Realistic costs eat a significant share of the textbook return. "
            "Strategy is on the edge — small alpha erosion could flip it.",
        )
    return (
        "illusion",
        "Most of the textbook return is consumed by realistic execution friction. "
        "Likely a curve-fit or low-alpha strategy masquerading as edge.",
    )


@router.post("/honesty-report")
def honesty_report(req: HonestyReportRequest, db: Session = Depends(get_sync_db)) -> dict:
    """Generate a Strategy Honesty Report.

    Runs the SAME backtest twice with two different cost models, then reports
    the gap between textbook P&L (legacy slippage-only) and realistic P&L
    (spread + FX + volume impact). Neither run is persisted.

    Layer 1 — Research-open: read-only analysis, no execution impact, no
    persistence beyond the transient response.
    """
    from datetime import date as dt_date
    from libs.backtest.engine import run_backtest, CostModel, PortfolioConfig

    instrument_map = _resolve_tickers(db, req.tickers)
    if not instrument_map:
        raise HTTPException(status_code=404, detail="No instruments found for the given tickers")

    instrument_ids = list(instrument_map.values())
    start = dt_date.fromisoformat(req.start_date)
    end = dt_date.fromisoformat(req.end_date)
    portfolio_cfg = PortfolioConfig(
        max_positions=req.max_positions,
        rebalance_frequency=req.rebalance_freq,
    )

    # Legacy: textbook 5-bps slippage only
    legacy_cm = CostModel(slippage_bps=req.legacy_slippage_bps)
    legacy_result = run_backtest(
        session=db,
        instrument_ids=instrument_ids,
        start_date=start,
        end_date=end,
        config=portfolio_cfg,
        cost_model=legacy_cm,
    )

    # Realistic: full friction chain
    r = req.realistic
    realistic_cm = CostModel(
        slippage_bps=r.slippage_bps,
        spread_bps=r.spread_bps,
        fx_fee_bps=r.fx_fee_bps,
        base_currency=r.base_currency,
        commission_per_share=r.commission_per_share,
        volume_impact_bps=r.volume_impact_bps,
        volume_impact_threshold=r.volume_impact_threshold,
    )
    realistic_result = run_backtest(
        session=db,
        instrument_ids=instrument_ids,
        start_date=start,
        end_date=end,
        config=portfolio_cfg,
        cost_model=realistic_cm,
    )

    # Guard against missing data
    legacy_m = legacy_result.metrics or {}
    realistic_m = realistic_result.metrics or {}
    if "total_return" not in legacy_m or "total_return" not in realistic_m:
        raise HTTPException(
            status_code=422,
            detail="Insufficient price data to run comparable backtests.",
        )

    legacy_ret = legacy_m["total_return"]
    realistic_ret = realistic_m["total_return"]
    legacy_cost = legacy_m.get("total_costs") or 0.0
    realistic_cost = realistic_m.get("total_costs") or 0.0

    # Return retention: realistic / legacy (only meaningful if legacy is positive)
    if legacy_ret > 0:
        retention_pct = (realistic_ret / legacy_ret) * 100
    elif legacy_ret == 0:
        retention_pct = 100.0 if realistic_ret >= 0 else 0.0
    else:
        # Legacy already negative — the "degraded" framing doesn't apply
        retention_pct = 100.0 if realistic_ret >= legacy_ret else 0.0

    cost_multiplier = (realistic_cost / legacy_cost) if legacy_cost > 0 else None

    # Annualized cost drag in bps of avg NAV
    years = max(legacy_m.get("trading_days", 1) / 252, 1e-9)
    initial_capital = legacy_m.get("initial_capital") or 100_000.0
    annual_cost_drag_bps = (
        (realistic_cost - legacy_cost) / initial_capital / years * 10000
    )

    verdict, reason = _verdict_from_retention(retention_pct, realistic_ret)

    return {
        "legacy": {
            "total_return": legacy_ret,
            "annualized_return": legacy_m.get("annualized_return"),
            "sharpe_ratio": legacy_m.get("sharpe_ratio"),
            "max_drawdown": legacy_m.get("max_drawdown"),
            "total_costs": legacy_cost,
            "total_trades": legacy_m.get("total_trades"),
            "final_nav": legacy_m.get("final_nav"),
            "cost_breakdown": legacy_m.get("cost_breakdown"),
        },
        "realistic": {
            "total_return": realistic_ret,
            "annualized_return": realistic_m.get("annualized_return"),
            "sharpe_ratio": realistic_m.get("sharpe_ratio"),
            "max_drawdown": realistic_m.get("max_drawdown"),
            "total_costs": realistic_cost,
            "total_trades": realistic_m.get("total_trades"),
            "final_nav": realistic_m.get("final_nav"),
            "cost_breakdown": realistic_m.get("cost_breakdown"),
        },
        "gap": {
            "return_pp": (realistic_ret - legacy_ret) * 100,
            "return_retention_pct": round(retention_pct, 2),
            "sharpe_delta": (realistic_m.get("sharpe_ratio") or 0)
                            - (legacy_m.get("sharpe_ratio") or 0),
            "cost_multiplier": round(cost_multiplier, 2) if cost_multiplier else None,
            "cost_delta_usd": realistic_cost - legacy_cost,
            "annual_cost_drag_bps": round(annual_cost_drag_bps, 1),
        },
        "verdict": verdict,
        "verdict_reason": reason,
        "config": {
            "tickers": req.tickers,
            "start_date": req.start_date,
            "end_date": req.end_date,
            "max_positions": req.max_positions,
            "rebalance_freq": req.rebalance_freq,
            "legacy_cost": {"slippage_bps": req.legacy_slippage_bps},
            "realistic_cost": r.model_dump(),
        },
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
