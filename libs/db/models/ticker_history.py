"""TickerHistory — ticker/name/exchange historical intervals."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.db.base import Base


class TickerHistory(Base):
    __tablename__ = "ticker_history"

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), primary_key=True,
    )
    ticker: Mapped[str] = mapped_column(String(20), primary_key=True)
    effective_from: Mapped[date] = mapped_column(Date, primary_key=True)
    issuer_name: Mapped[str | None] = mapped_column(Text)
    exchange: Mapped[str | None] = mapped_column(String(20))
    effective_to: Mapped[date | None] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    instrument = relationship("Instrument", back_populates="ticker_histories")
