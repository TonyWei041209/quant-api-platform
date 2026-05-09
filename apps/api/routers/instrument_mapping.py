"""Instrument-mapping read-only API.

`GET /api/instruments/mirror-mapping/plan` — returns a dry-run mapping
plan for the Trading 212 Mirror tickers (held + recently traded +
manually watched). The endpoint never writes the database, never calls
a Trading 212 write endpoint, never touches order_intent / order_draft
/ submit objects, and never alters live submit.

Production bootstrap (creating instrument + instrument_identifier +
ticker_history rows) is gated by the four-flag CLI handshake and is
NOT reachable through this HTTP route.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.instruments.mirror_instrument_mapper import build_mirror_mapping_plan


router = APIRouter()


@router.get("/mirror-mapping/plan")
async def mirror_mapping_plan(
    fetch_profiles: bool = Query(
        False,
        description=(
            "When True, fetch FMP profile for unmapped tickers (read-only). "
            "Default False to avoid provider quota usage."
        ),
    ),
    include_recent_orders: bool = Query(True),
    lookback_days: int = Query(7, ge=1, le=90),
    manual: Optional[str] = Query(
        None,
        description="Comma-separated manual watched tickers to merge in.",
    ),
    db: Session = Depends(get_sync_db),
):
    manual_list = (
        [t.strip() for t in manual.split(",") if t.strip()]
        if manual else None
    )

    fmp_fetcher = None
    if fetch_profiles:
        from libs.adapters.fmp_adapter import FMPAdapter
        adapter = FMPAdapter()

        async def _fetch(symbol: str):
            return await adapter.get_profile(symbol)
        fmp_fetcher = _fetch

    plan = await build_mirror_mapping_plan(
        db,
        fetch_profiles=fetch_profiles,
        include_recent_orders=include_recent_orders,
        recent_lookback_days=lookback_days,
        manual_tickers=manual_list,
        fmp_profile_fetcher=fmp_fetcher,
    )
    return plan.to_dict()
