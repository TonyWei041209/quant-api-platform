"""Saved presets — reusable research configurations."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base, TimestampMixin
from libs.core.time import utc_now


class SavedPreset(Base, TimestampMixin):
    __tablename__ = "saved_preset"

    preset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    preset_type: Mapped[str] = mapped_column(String(50), nullable=False)  # screener | event_study | backtest | research
    config: Mapped[dict] = mapped_column(JSONB, nullable=False)  # the saved parameters
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)
