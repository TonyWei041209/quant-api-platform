"""Instrument — the security entity master table."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.db.base import Base, TimestampMixin


class Instrument(Base, TimestampMixin):
    __tablename__ = "instrument"

    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    issuer_name_current: Mapped[str] = mapped_column(Text, nullable=False)
    exchange_primary: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str | None] = mapped_column(String(10))
    country_code: Mapped[str | None] = mapped_column(String(5))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    identifiers = relationship("InstrumentIdentifier", back_populates="instrument", lazy="selectin")
    ticker_histories = relationship("TickerHistory", back_populates="instrument", lazy="selectin")
