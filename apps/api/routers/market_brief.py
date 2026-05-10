"""Overnight Market Brief — read-only composed view.

Single endpoint: ``GET /api/market-brief/overnight-preview``.

This route NEVER writes the database, NEVER calls a Trading 212 write
endpoint, NEVER touches order_intent / order_draft / submit objects,
NEVER alters FEATURE_T212_LIVE_SUBMIT, and intentionally has NO
companion Cloud Scheduler — the brief is generated on demand.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.market_brief.overnight_brief_service import (
    DEFAULT_DAYS,
    DEFAULT_NEWS_LIMIT_PER_TICKER,
    DEFAULT_NEWS_TOP_N,
    DEFAULT_SCANNER_LIMIT,
    build_overnight_brief,
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
    return await build_overnight_brief(
        db,
        days=days,
        scanner_limit=scanner_limit,
        news_top_n=news_top_n,
        news_limit_per_ticker=news_limit_per_ticker,
        manual_tickers=manual_tickers,
    )
