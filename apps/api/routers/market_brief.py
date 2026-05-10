"""Overnight Market Brief — read-only composed view.

Single endpoint: ``GET /api/market-brief/overnight-preview``.

This route NEVER writes the database, NEVER calls a Trading 212 write
endpoint, NEVER touches order_intent / order_draft / submit objects,
NEVER alters FEATURE_T212_LIVE_SUBMIT, and intentionally has NO
companion Cloud Scheduler — the brief is generated on demand.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.market_brief.overnight_brief_service import (
    DEFAULT_DAYS,
    DEFAULT_NEWS_LIMIT_PER_TICKER,
    DEFAULT_NEWS_TOP_N,
    DEFAULT_SCANNER_LIMIT,
    build_overnight_brief,
)
from libs.research_snapshot import (
    get_brief_by_id,
    get_latest_brief,
    list_brief_runs,
    persist_market_brief_snapshot,
)


router = APIRouter()


@router.get("/overnight-preview")
async def overnight_preview(
    days: int = Query(DEFAULT_DAYS, ge=1, le=30,
                      description="News + earnings window in days."),
    scanner_limit: int = Query(DEFAULT_SCANNER_LIMIT, ge=10, le=100,
                               description="Max scanner candidates."),
    news_top_n: int = Query(DEFAULT_NEWS_TOP_N, ge=1, le=25,
                            description=(
                                "News fan-out top-N tickers. Default kept "
                                "low (5) for the on-demand interactive "
                                "preview to stay below provider rate-limit "
                                "ceilings; up to 25 allowed per request."
                            )),
    news_limit_per_ticker: int = Query(
        DEFAULT_NEWS_LIMIT_PER_TICKER, ge=1, le=10,
        description="Per-ticker news cap.",
    ),
    manual: Optional[str] = Query(
        None,
        description="Comma-separated manually-watched tickers to merge in.",
    ),
    db: Session = Depends(get_sync_db),
):
    manual_tickers = (
        [t.strip() for t in manual.split(",") if t.strip()]
        if manual else None
    )
    brief = await build_overnight_brief(
        db,
        days=days,
        scanner_limit=scanner_limit,
        news_top_n=news_top_n,
        news_limit_per_ticker=news_limit_per_ticker,
        manual_tickers=manual_tickers,
    )

    # Best-effort research-only snapshot — failures isolated inside the
    # service. Gated by FEATURE_RESEARCH_SNAPSHOT_WRITE.
    persist_market_brief_snapshot(db, brief, source="interactive")

    return brief


# ---------------------------------------------------------------------------
# History endpoints (read-only over persisted snapshots)
# ---------------------------------------------------------------------------


@router.get("/latest")
def latest_brief(
    source: Optional[str] = Query(
        None,
        description=(
            "Optional source filter — e.g. 'interactive' or "
            "'overnight-job'. Default: latest of any source."
        ),
    ),
    db: Session = Depends(get_sync_db),
):
    """Return the most recent persisted overnight brief.

    Read-only. Never calls a provider, never writes the database, never
    mutates broker / order / live submit state.
    """
    brief = get_latest_brief(db, source=source)
    if brief is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "no persisted brief yet. Generate one via "
                "/market-brief/overnight-preview or wait for the "
                "scheduled overnight job."
            ),
        )
    return brief


@router.get("/history")
def brief_history(
    limit: int = Query(
        10, ge=1, le=100,
        description="Max number of runs to return.",
    ),
    source: Optional[str] = Query(
        None,
        description="Optional source filter (e.g. 'interactive').",
    ),
    db: Session = Depends(get_sync_db),
):
    """List recent persisted overnight briefs (lightweight summary)."""
    return {
        "items": list_brief_runs(db, limit=limit, source=source),
        "limit": limit,
    }


@router.get("/{run_id}")
def brief_by_id(
    run_id: str,
    db: Session = Depends(get_sync_db),
):
    """Fetch a single persisted brief by run_id."""
    brief = get_brief_by_id(db, run_id)
    if brief is None:
        raise HTTPException(
            status_code=404,
            detail=f"brief run_id {run_id!r} not found",
        )
    return brief
