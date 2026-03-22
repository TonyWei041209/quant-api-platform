"""Filing — regulatory filings (SEC EDGAR etc.)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class Filing(Base):
    __tablename__ = "filing"

    filing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=False)
    cik: Mapped[str] = mapped_column(String(20), nullable=False)
    accession_no: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    form_type: Mapped[str] = mapped_column(String(20), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    acceptance_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[date | None] = mapped_column(Date)
    primary_doc_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="sec")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
