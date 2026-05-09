"""Market Events & News API — read-only.

Routes:
  GET /api/market-events/feed         — composed earnings + news for a scope
  GET /api/market-events/earnings     — earnings only for a scope
  GET /api/market-events/news         — news only for a scope (per-ticker)
  GET /api/market-events/ticker/{ticker} — detail view for one ticker

All routes are read-only and behave as follows when upstream FMP is
unavailable: they return HTTP 200 with ``provider_status`` populated
("unavailable" / "error" / "partial") and empty/short data — never 500.

This router never writes the database, never calls a Trading 212 write
endpoint, never touches order_intent / order_draft / submit objects,
and never alters FEATURE_T212_LIVE_SUBMIT.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.market_events import market_events_service as svc


router = APIRouter()

ALLOWED_SCOPES = ("mirror", "scanner", "all_supported", "ticker")


@router.get("/feed")
async def feed(
    scope: str = Query("mirror"),
    days: int = Query(7, ge=1, le=60),
    limit: int = Query(100, ge=10, le=500),
    limit_per_ticker: int = Query(5, ge=1, le=25),
    ticker: Optional[str] = Query(None, description="Required when scope=ticker"),
    db: Session = Depends(get_sync_db),
):
    if scope not in ALLOWED_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scope '{scope}'. Allowed: {ALLOWED_SCOPES}",
        )
    if scope == "ticker" and not ticker:
        raise HTTPException(
            status_code=400,
            detail="scope='ticker' requires the 'ticker' query parameter",
        )
    return await svc.get_feed(
        db,
        scope=scope,
        days=days,
        limit=limit,
        limit_per_ticker=limit_per_ticker,
        ticker=ticker,
    )


@router.get("/earnings")
async def earnings_only(
    scope: str = Query("mirror"),
    days: int = Query(7, ge=1, le=60),
    limit: int = Query(100, ge=10, le=500),
    db: Session = Depends(get_sync_db),
):
    if scope not in ALLOWED_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scope '{scope}'. Allowed: {ALLOWED_SCOPES}",
        )
    feed = await svc.get_feed(
        db, scope=scope, days=days, limit=limit, limit_per_ticker=1,
    )
    return {
        "scope": scope,
        "generated_at": feed["generated_at"],
        "date_range": feed["date_range"],
        "provider_status": {"fmp_earnings": feed["provider_status"]["fmp_earnings"]},
        "counts": {"earnings": feed["counts"]["earnings"]},
        "earnings": feed["earnings"],
        "tickers_in_scope": feed["tickers_in_scope"],
        "disclaimer": feed["disclaimer"],
    }


@router.get("/news")
async def news_only(
    scope: str = Query("mirror"),
    days: int = Query(7, ge=1, le=60),
    limit_per_ticker: int = Query(5, ge=1, le=25),
    db: Session = Depends(get_sync_db),
):
    if scope not in ALLOWED_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scope '{scope}'. Allowed: {ALLOWED_SCOPES}",
        )
    if scope == "all_supported":
        # Intentional: do not issue an unbounded all-market news call.
        return {
            "scope": scope,
            "generated_at": "",
            "provider_status": {"fmp_news": "unavailable"},
            "provider_notes": {"fmp_news": "all_supported scope intentionally omits news"},
            "counts": {"news": 0},
            "news": [],
            "disclaimer": svc.DISCLAIMER,
        }
    feed = await svc.get_feed(
        db, scope=scope, days=days, limit=10, limit_per_ticker=limit_per_ticker,
    )
    return {
        "scope": scope,
        "generated_at": feed["generated_at"],
        "date_range": {"news_from": feed["date_range"]["news_from"], "news_to": feed["date_range"]["news_to"]},
        "provider_status": {"fmp_news": feed["provider_status"]["fmp_news"]},
        "counts": {"news": feed["counts"]["news"]},
        "news": feed["news"],
        "tickers_in_scope": feed["tickers_in_scope"],
        "disclaimer": feed["disclaimer"],
    }


@router.get("/ticker/{ticker}")
async def ticker_detail(
    ticker: str,
    days: int = Query(30, ge=1, le=120),
    db: Session = Depends(get_sync_db),
):
    if not ticker or len(ticker) > 20:
        raise HTTPException(status_code=400, detail="invalid ticker")
    return await svc.get_ticker_detail(db, ticker=ticker, days=days)
