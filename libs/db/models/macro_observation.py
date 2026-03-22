"""MacroObservation — macroeconomic data points with vintage support."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class MacroObservation(Base):
    __tablename__ = "macro_observation"

    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("macro_series.series_id"), primary_key=True,
    )
    observation_date: Mapped[date] = mapped_column(Date, primary_key=True)
    realtime_start: Mapped[date] = mapped_column(Date, primary_key=True, comment="Vintage start for PIT macro")
    realtime_end: Mapped[date] = mapped_column(Date, nullable=False, comment="Vintage end for PIT macro")
    value: Mapped[float | None] = mapped_column(Numeric(24, 6))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
