"""InstrumentIdentifier — identifier mapping and history."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.db.base import Base


class InstrumentIdentifier(Base):
    __tablename__ = "instrument_identifier"
    __table_args__ = (
        {"comment": "Identifier mapping with temporal validity"},
    )

    instrument_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), primary_key=True,
    )
    id_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    id_value: Mapped[str] = mapped_column(String(50), primary_key=True)
    source: Mapped[str] = mapped_column(String(50), primary_key=True)
    valid_from: Mapped[date] = mapped_column(Date, primary_key=True)
    valid_to: Mapped[date | None] = mapped_column(Date)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    instrument = relationship("Instrument", back_populates="identifiers")
