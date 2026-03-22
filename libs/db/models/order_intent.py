"""OrderIntent — research-layer trading intent."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class OrderIntent(Base):
    __tablename__ = "order_intent"

    intent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    target_qty: Mapped[float | None] = mapped_column(Numeric(18, 6))
    target_value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    target_weight: Mapped[float | None] = mapped_column(Numeric(10, 6))
    reason: Mapped[dict | None] = mapped_column(JSONB)
    risk_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=text("now()"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
