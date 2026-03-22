"""OrderDraft — pending human approval order draft."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class OrderDraft(Base):
    __tablename__ = "order_draft"

    draft_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("order_intent.intent_id"), nullable=False)
    broker: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[str | None] = mapped_column(String(50))
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    stop_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    tif: Mapped[str] = mapped_column(String(10), nullable=False, default="day")
    is_live_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=text("now()"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_approval")
