"""EarningsEvent — earnings announcement events."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class EarningsEvent(Base):
    __tablename__ = "earnings_event"

    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    fiscal_quarter: Mapped[int | None] = mapped_column(Integer)
    period_end: Mapped[date | None] = mapped_column(Date)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_time_code: Mapped[str] = mapped_column(String(10), default="UNKNOWN")
    eps_estimate: Mapped[float | None] = mapped_column(Numeric(18, 6))
    eps_actual: Mapped[float | None] = mapped_column(Numeric(18, 6))
    revenue_estimate: Mapped[float | None] = mapped_column(Numeric(18, 6))
    revenue_actual: Mapped[float | None] = mapped_column(Numeric(18, 6))
    confirmed_flag: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
