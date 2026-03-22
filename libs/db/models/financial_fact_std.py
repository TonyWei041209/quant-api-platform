"""FinancialFactStd — standardized financial facts (long table)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class FinancialFactStd(Base):
    __tablename__ = "financial_fact_std"

    financial_period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("financial_period.financial_period_id"), primary_key=True,
    )
    statement_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    metric_code: Mapped[str] = mapped_column(String(80), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    metric_value: Mapped[float] = mapped_column(Numeric(24, 6), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20))
    scale: Mapped[str | None] = mapped_column(String(20))
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
