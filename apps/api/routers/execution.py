"""Execution endpoints — intents, drafts, approval."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.execution.intents import create_intent, list_intents
from libs.execution.drafts import create_draft_from_intent, approve_draft, list_drafts

router = APIRouter()


class CreateIntentRequest(BaseModel):
    strategy_name: str
    instrument_id: str
    side: str
    target_qty: float | None = None
    target_value: float | None = None
    target_weight: float | None = None
    reason: dict | None = None


class CreateDraftRequest(BaseModel):
    broker: str = "trading212"
    order_type: str = "limit"
    qty: float = 0
    limit_price: float | None = None
    stop_price: float | None = None
    tif: str = "day"


@router.get("/intents")
def get_intents(status: str | None = None, db: Session = Depends(get_sync_db)) -> dict:
    intents = list_intents(db, status)
    return {
        "items": [
            {
                "intent_id": str(i.intent_id),
                "strategy_name": i.strategy_name,
                "instrument_id": str(i.instrument_id),
                "side": i.side,
                "target_qty": float(i.target_qty) if i.target_qty else None,
                "status": i.status,
                "created_at": str(i.created_at),
            }
            for i in intents
        ]
    }


@router.post("/intents")
def create_new_intent(req: CreateIntentRequest, db: Session = Depends(get_sync_db)) -> dict:
    intent = create_intent(
        db,
        strategy_name=req.strategy_name,
        instrument_id=req.instrument_id,
        side=req.side,
        target_qty=req.target_qty,
        target_value=req.target_value,
        target_weight=req.target_weight,
        reason=req.reason,
    )
    db.commit()
    return {"intent_id": str(intent.intent_id), "status": intent.status}


@router.get("/drafts")
def get_drafts(status: str | None = None, db: Session = Depends(get_sync_db)) -> dict:
    drafts = list_drafts(db, status)
    return {
        "items": [
            {
                "draft_id": str(d.draft_id),
                "intent_id": str(d.intent_id),
                "broker": d.broker,
                "order_type": d.order_type,
                "qty": float(d.qty),
                "status": d.status,
                "is_live_enabled": d.is_live_enabled,
                "created_at": str(d.created_at),
            }
            for d in drafts
        ]
    }


@router.post("/drafts/from-intent/{intent_id}")
def create_draft(intent_id: str, req: CreateDraftRequest, db: Session = Depends(get_sync_db)) -> dict:
    try:
        draft = create_draft_from_intent(
            db,
            intent_id=intent_id,
            broker=req.broker,
            order_type=req.order_type,
            qty=req.qty,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
            tif=req.tif,
        )
        db.commit()
        return {"draft_id": str(draft.draft_id), "status": draft.status}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/drafts/{draft_id}/approve")
def approve_order_draft(draft_id: str, db: Session = Depends(get_sync_db)) -> dict:
    try:
        draft = approve_draft(db, draft_id)
        db.commit()
        return {"draft_id": str(draft.draft_id), "status": draft.status, "approved_at": str(draft.approved_at)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/drafts/{draft_id}/reject")
def reject_order_draft(draft_id: str, reason: str = "", db: Session = Depends(get_sync_db)) -> dict:
    try:
        from libs.execution.drafts import reject_draft
        draft = reject_draft(db, draft_id, reason)
        db.commit()
        return {"draft_id": str(draft.draft_id), "status": draft.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/drafts/{draft_id}/risk-check")
def run_risk_check(draft_id: str, db: Session = Depends(get_sync_db)) -> dict:
    """Run risk checks on a draft without submitting."""
    import uuid
    from libs.db.models.order_draft import OrderDraft
    from libs.execution.risk_checks import pre_submit_risk_check

    draft = db.get(OrderDraft, uuid.UUID(draft_id))
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    all_passed, results = pre_submit_risk_check(db, draft)
    return {
        "draft_id": draft_id,
        "all_passed": all_passed,
        "checks": [{"rule": r.rule, "passed": r.passed, "reason": r.reason} for r in results],
    }


@router.post("/drafts/expire-stale")
def expire_stale(max_age_hours: int = 48, db: Session = Depends(get_sync_db)) -> dict:
    """Expire stale pending drafts."""
    from libs.execution.drafts import expire_stale_drafts
    count = expire_stale_drafts(db, max_age_hours)
    db.commit()
    return {"expired_count": count}
