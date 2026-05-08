"""Trading 212 Mirror Watchlist router.

Read-only endpoint that composes a "mirror" of the user's Trading 212 view
from data we already have access to (held positions + recent filled orders +
optional manually-supplied watched tickers via query string).

Trading 212's public API does NOT expose the user's in-app watchlist, so we
do not pretend to mirror it byte-for-byte. We never scrape, never automate
a browser, never call private endpoints, never call any T212 write endpoint.
Manual watched tickers are passed in via query string and persisted by the
frontend in localStorage; no schema migration was required for this phase.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.portfolio.mirror_watchlist_service import (
    DEFAULT_RECENT_LOOKBACK_DAYS,
    build_mirror_watchlist,
)


router = APIRouter()


@router.get("/trading212-mirror")
def get_trading212_mirror(
    manual: Optional[str] = Query(
        None,
        description=(
            "Comma-separated list of manually-watched tickers (e.g. RKLB,CRWV,HIMS). "
            "Persisted by the frontend in browser localStorage; this endpoint is "
            "stateless with respect to user-watched tickers."
        ),
    ),
    include_recent_orders: bool = Query(
        True,
        description="Include tickers traded within the last N days",
    ),
    lookback_days: int = Query(
        DEFAULT_RECENT_LOOKBACK_DAYS, ge=1, le=90,
        description="Recent-orders lookback window in days",
    ),
    db: Session = Depends(get_sync_db),
):
    """Return the composed Trading 212 Mirror watchlist.

    Read-only. Never writes the database, never calls a Trading 212 write
    endpoint, never creates execution objects, never alters live submit.
    """
    manual_tickers = (
        [t for t in (s.strip() for s in manual.split(",")) if t]
        if manual else None
    )
    return build_mirror_watchlist(
        db,
        manual_tickers=manual_tickers,
        include_recent_orders=include_recent_orders,
        recent_lookback_days=lookback_days,
    )
