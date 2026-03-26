"""Research notes — lightweight thesis snapshots and annotations."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base, TimestampMixin


class ResearchNote(Base, TimestampMixin):
    __tablename__ = "research_note"

    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=True)
    note_type: Mapped[str] = mapped_column(String(50), nullable=False, default="general")  # general | thesis | observation | risk | catalyst
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # e.g. {"tags": ["earnings", "momentum"]}
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)  # link to backtest_run_id, screener_config, etc
