"""Research endpoints."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.db.models.instrument import Instrument
from libs.research.adjusted_prices import get_split_adjusted_prices
from libs.research.pit_views import get_latest_financials_pit
from libs.research.event_study import earnings_event_study

router = APIRouter()


@router.get("/instrument/{instrument_id}/summary")
def instrument_summary(instrument_id: str, db: Session = Depends(get_sync_db)) -> dict:
    """Summary: latest prices, PIT financials, recent corporate actions."""
    try:
        iid = uuid.UUID(instrument_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    inst = db.query(Instrument).get(iid)
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found")

    # Latest PIT financials
    financials_df = get_latest_financials_pit(db, instrument_id)
    financials = financials_df.to_dict("records") if not financials_df.empty else []

    # Recent prices
    prices_df = get_split_adjusted_prices(db, instrument_id)
    recent_prices = prices_df.tail(5).to_dict("records") if not prices_df.empty else []

    return {
        "instrument_id": instrument_id,
        "issuer_name": inst.issuer_name_current,
        "recent_prices": recent_prices,
        "latest_financials": financials[:20],
    }


@router.get("/instrument/{instrument_id}/prices")
def instrument_prices(
    instrument_id: str,
    start: str = Query(None),
    end: str = Query(None),
    db: Session = Depends(get_sync_db),
) -> dict:
    """Get split-adjusted prices."""
    from datetime import date as dt_date
    start_date = dt_date.fromisoformat(start) if start else None
    end_date = dt_date.fromisoformat(end) if end else None
    prices_df = get_split_adjusted_prices(db, instrument_id, start_date, end_date)
    return {"instrument_id": instrument_id, "prices": prices_df.to_dict("records") if not prices_df.empty else []}


class EventStudyRequest(BaseModel):
    instrument_id: str
    windows: list[int] | None = None


@router.post("/event-study/earnings")
def run_earnings_event_study(
    req: EventStudyRequest,
    db: Session = Depends(get_sync_db),
) -> dict:
    """Run post-earnings event study."""
    df = earnings_event_study(db, req.instrument_id, req.windows)
    return {"instrument_id": req.instrument_id, "results": df.to_dict("records") if not df.empty else []}


@router.get("/instrument/{instrument_id}/performance")
def instrument_performance(
    instrument_id: str,
    start: str = Query(None),
    end: str = Query(None),
    db: Session = Depends(get_sync_db),
) -> dict:
    """Performance statistics for an instrument."""
    from datetime import date as dt_date
    from libs.research.factors import performance_summary
    start_date = dt_date.fromisoformat(start) if start else None
    end_date = dt_date.fromisoformat(end) if end else None
    stats = performance_summary(db, instrument_id, start_date, end_date)
    return {"instrument_id": instrument_id, "performance": stats}


@router.get("/instrument/{instrument_id}/valuation")
def instrument_valuation(
    instrument_id: str,
    db: Session = Depends(get_sync_db),
) -> dict:
    """Simple valuation snapshot based on PIT financials + latest price."""
    from libs.research.factors import valuation_snapshot
    snap = valuation_snapshot(db, instrument_id)
    return {"instrument_id": instrument_id, "valuation": snap}


@router.get("/instrument/{instrument_id}/drawdown")
def instrument_drawdown(
    instrument_id: str,
    start: str = Query(None),
    end: str = Query(None),
    db: Session = Depends(get_sync_db),
) -> dict:
    """Drawdown series for an instrument."""
    from datetime import date as dt_date
    from libs.research.factors import drawdown
    start_date = dt_date.fromisoformat(start) if start else None
    end_date = dt_date.fromisoformat(end) if end else None
    df = drawdown(db, instrument_id, start_date, end_date)
    if df.empty:
        return {"instrument_id": instrument_id, "drawdown": []}
    return {
        "instrument_id": instrument_id,
        "max_drawdown": float(df["max_drawdown"].min()) if not df.empty else None,
        "current_drawdown": float(df["drawdown"].iloc[-1]) if not df.empty else None,
        "data_points": len(df),
    }


@router.get("/screener/liquidity")
def screener_liquidity(
    min_avg_volume: float = Query(1_000_000),
    lookback_days: int = Query(20),
    db: Session = Depends(get_sync_db),
) -> dict:
    """Screen instruments by average daily volume."""
    from libs.research.screeners import screen_by_liquidity
    df = screen_by_liquidity(db, min_avg_volume=min_avg_volume, lookback_days=lookback_days)
    return {"results": df.to_dict("records") if not df.empty else []}


@router.get("/screener/returns")
def screener_returns(
    lookback_days: int = Query(63),
    min_return: float = Query(None),
    max_return: float = Query(None),
    db: Session = Depends(get_sync_db),
) -> dict:
    """Screen instruments by N-day return."""
    from libs.research.screeners import screen_by_returns
    df = screen_by_returns(db, lookback_days=lookback_days, min_return=min_return, max_return=max_return)
    return {"results": df.to_dict("records") if not df.empty else []}


@router.get("/screener/fundamentals")
def screener_fundamentals(
    max_pe: float = Query(None),
    min_revenue: float = Query(None),
    db: Session = Depends(get_sync_db),
) -> dict:
    """Screen instruments by fundamental metrics (PIT-safe)."""
    from libs.research.screeners import screen_by_fundamentals
    df = screen_by_fundamentals(db, max_pe=max_pe, min_revenue=min_revenue)
    return {"results": df.to_dict("records") if not df.empty else []}


@router.get("/screener/rank")
def screener_rank(db: Session = Depends(get_sync_db)) -> dict:
    """Rank universe by composite factor score."""
    from libs.research.screeners import rank_universe
    df = rank_universe(db)
    return {"results": df.to_dict("records") if not df.empty else []}


class EventStudySummaryRequest(BaseModel):
    instrument_ids: list[str] | None = None
    min_date: str | None = None
    max_date: str | None = None
    windows: list[int] | None = None


@router.post("/event-study/earnings/summary")
def earnings_event_study_summary_endpoint(
    req: EventStudySummaryRequest,
    db: Session = Depends(get_sync_db),
) -> dict:
    """Grouped earnings event study summary across instruments."""
    from datetime import date as dt_date
    from libs.research.event_study import earnings_event_study_summary
    min_date = dt_date.fromisoformat(req.min_date) if req.min_date else None
    max_date = dt_date.fromisoformat(req.max_date) if req.max_date else None
    return earnings_event_study_summary(
        db, instrument_ids=req.instrument_ids,
        min_date=min_date, max_date=max_date, windows=req.windows,
    )
