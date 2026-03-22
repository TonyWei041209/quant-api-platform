"""Order draft management — bridge between intent and broker submission."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from libs.core.ids import new_id
from libs.core.time import utc_now
from libs.db.models.order_draft import OrderDraft
from libs.db.models.order_intent import OrderIntent


def create_draft_from_intent(
    session: Session,
    intent_id: str | uuid.UUID,
    broker: str = "trading212",
    order_type: str = "limit",
    qty: float = 0,
    limit_price: float | None = None,
    stop_price: float | None = None,
    tif: str = "day",
) -> OrderDraft:
    """Create an order draft from an existing intent."""
    intent = session.query(OrderIntent).get(uuid.UUID(str(intent_id)))
    if intent is None:
        raise ValueError(f"Intent {intent_id} not found")

    draft = OrderDraft(
        draft_id=new_id(),
        intent_id=intent.intent_id,
        broker=broker,
        order_type=order_type,
        qty=qty or intent.target_qty or 0,
        limit_price=limit_price,
        stop_price=stop_price,
        tif=tif,
        is_live_enabled=False,
        status="pending_approval",
    )
    session.add(draft)

    intent.status = "drafted"
    session.flush()
    return draft


def approve_draft(session: Session, draft_id: str | uuid.UUID) -> OrderDraft:
    """Mark a draft as approved for submission."""
    draft = session.query(OrderDraft).get(uuid.UUID(str(draft_id)))
    if draft is None:
        raise ValueError(f"Draft {draft_id} not found")
    if draft.status != "pending_approval":
        raise ValueError(f"Draft {draft_id} is in status {draft.status}, cannot approve")

    draft.approved_at = utc_now()
    draft.status = "approved"
    session.flush()
    return draft


def list_drafts(session: Session, status: str | None = None) -> list[OrderDraft]:
    """List order drafts."""
    q = session.query(OrderDraft)
    if status:
        q = q.filter(OrderDraft.status == status)
    return q.order_by(OrderDraft.created_at.desc()).all()
