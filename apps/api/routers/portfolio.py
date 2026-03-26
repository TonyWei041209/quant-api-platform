"""Portfolio Context API — aggregated portfolio views from broker snapshots.

All endpoints are readonly. No broker write operations.
Portfolio data is derived from the most recent broker snapshots in the database.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.portfolio.portfolio_service import (
    get_portfolio_summary,
    is_instrument_held,
    get_watchlist_holdings_overlay,
)

router = APIRouter()


@router.get("/summary")
def portfolio_summary(db: Session = Depends(get_sync_db)):
    """Get aggregated portfolio summary: account, positions, recent orders."""
    return get_portfolio_summary(db)


@router.get("/positions")
def portfolio_positions(db: Session = Depends(get_sync_db)):
    """Get current positions only."""
    summary = get_portfolio_summary(db)
    return {
        "positions": summary["positions"],
        "count": summary["position_count"],
        "total_market_value": summary["total_market_value"],
        "total_pnl": summary["total_pnl"],
        "as_of": summary["as_of"],
    }


@router.get("/instrument/{instrument_id}/holding")
def instrument_holding(instrument_id: str, db: Session = Depends(get_sync_db)):
    """Check if a specific instrument is currently held."""
    import uuid as _uuid
    try:
        _uuid.UUID(instrument_id)
    except ValueError:
        return {"held": False, "quantity": 0, "broker_ticker": None, "error": "invalid instrument_id format"}
    return is_instrument_held(db, instrument_id)


@router.get("/watchlist/{group_id}/holdings")
def watchlist_holdings(group_id: str, db: Session = Depends(get_sync_db)):
    """Get holdings overlay for a watchlist group."""
    return get_watchlist_holdings_overlay(db, group_id)
