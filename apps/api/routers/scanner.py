"""Stock Scanner API — research candidate discovery.

Layer 1 (Research-open). Read-only. No execution objects, no broker write.

Pydantic models use ``model_config = ConfigDict(extra="forbid")`` so that any
attempt to add buy/sell/target_price/position_size fields to responses fails
fast at serialization time.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.research_snapshot import persist_scanner_snapshot
from libs.scanner.stock_scanner_service import scan_stocks


router = APIRouter()


# ---------------------------------------------------------------------------
# Response models — STRICT (extra="forbid")
# ---------------------------------------------------------------------------

class ScanItem(BaseModel):
    """A single scanner result. Whitelisted fields only."""
    model_config = ConfigDict(extra="forbid")

    instrument_id: str
    ticker: Optional[str]
    issuer_name: Optional[str]
    universe_source: str
    scan_types: list[str]
    signal_strength: Literal["low", "medium", "high"]
    change_1d_pct: Optional[float]
    change_5d_pct: Optional[float]
    change_1m_pct: Optional[float]
    week52_position_pct: Optional[float]
    volume_ratio: Optional[float]
    risk_flags: list[str]
    explanation: str
    recommended_next_step: Literal[
        "research", "validate", "add_to_watchlist", "run_backtest", "monitor"
    ]
    data_mode: Literal["daily_eod"]
    as_of: Optional[str]


class ScanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ScanItem]
    as_of: Optional[str]
    data_mode: Literal["daily_eod"]
    universe: Literal["all", "watchlist"]
    limit: int
    scanned: int
    matched: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.get("/stock", response_model=ScanResponse)
def stock_scanner(
    universe: Literal["all", "watchlist", "holdings"] = Query("all"),
    watchlist_group_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    sort_by: Literal[
        "signal_strength", "change_1d", "change_5d", "change_1m", "week52"
    ] = Query("signal_strength"),
    min_change_1d: Optional[float] = Query(None),
    min_change_5d: Optional[float] = Query(None),
    include_needs_research: bool = Query(False),
    db: Session = Depends(get_sync_db),
) -> ScanResponse:
    """Scan instruments for research candidates.

    Layer 1 — Research-open: read-only, no execution impact.

    Returns descriptive research candidates with deterministic rule-based
    classification. NEVER produces buy/sell/target/position language.

    `holdings` universe is not yet supported because broker_position_snapshot
    instrument_id mapping is not stable across environments. Pass `all` or
    `watchlist` instead.
    """
    if universe == "holdings":
        # 501 Not Implemented — deliberate, scoped out of v1
        raise HTTPException(
            status_code=501,
            detail=(
                "holdings scanner pending stable instrument mapping. "
                "Use universe=all or universe=watchlist for now."
            ),
        )

    if universe == "watchlist" and not watchlist_group_id:
        raise HTTPException(
            status_code=400,
            detail="watchlist_group_id is required when universe=watchlist",
        )

    result = scan_stocks(
        db,
        universe=universe,
        watchlist_group_id=watchlist_group_id,
        limit=limit,
        sort_by=sort_by,
        min_change_1d=min_change_1d,
        min_change_5d=min_change_5d,
        include_needs_research=include_needs_research,
    )

    # Best-effort research-only snapshot. Returns a structured outcome
    # but we deliberately do NOT attach it to the response (strict
    # Pydantic model). Failures are isolated inside the service and
    # never break the API.
    persist_scanner_snapshot(
        db,
        result,
        universe=str(universe),
        sort_by=str(sort_by),
        source="interactive",
    )

    return ScanResponse(**result)
