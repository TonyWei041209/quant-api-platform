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
