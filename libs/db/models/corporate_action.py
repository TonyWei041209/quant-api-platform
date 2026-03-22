"""CorporateAction — splits, dividends, ticker changes, etc."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class CorporateAction(Base):
    __tablename__ = "corporate_action"

    action_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=False)
    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    ex_date: Mapped[date] = mapped_column(Date, nullable=False)
    record_date: Mapped[date | None] = mapped_column(Date)
    pay_date: Mapped[date | None] = mapped_column(Date)
    split_from: Mapped[float | None] = mapped_column(Numeric(18, 6))
    split_to: Mapped[float | None] = mapped_column(Numeric(18, 6))
    cash_amount: Mapped[float | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str | None] = mapped_column(String(10))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
