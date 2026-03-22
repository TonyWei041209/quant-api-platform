"""Order intent management."""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from libs.core.ids import new_id
from libs.db.models.order_intent import OrderIntent


def create_intent(
    session: Session,
    strategy_name: str,
    instrument_id: str | uuid.UUID,
    side: str,
    target_qty: float | None = None,
    target_value: float | None = None,
    target_weight: float | None = None,
    reason: dict | None = None,
    risk_snapshot: dict | None = None,
) -> OrderIntent:
    """Create a new order intent."""
    intent = OrderIntent(
        intent_id=new_id(),
        strategy_name=strategy_name,
        instrument_id=uuid.UUID(str(instrument_id)),
        side=side,
        target_qty=target_qty,
        target_value=target_value,
        target_weight=target_weight,
        reason=reason,
        risk_snapshot=risk_snapshot,
        status="pending",
    )
    session.add(intent)
    session.flush()
    return intent


def list_intents(session: Session, status: str | None = None) -> list[OrderIntent]:
    """List order intents, optionally filtered by status."""
    q = session.query(OrderIntent)
    if status:
        q = q.filter(OrderIntent.status == status)
    return q.order_by(OrderIntent.created_at.desc()).all()
