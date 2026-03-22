"""MacroSeries — macroeconomic series metadata."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class MacroSeries(Base):
    __tablename__ = "macro_series"

    series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    series_name: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    frequency: Mapped[str | None] = mapped_column(String(20))
    unit: Mapped[str | None] = mapped_column(String(50))
    metadata_payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
