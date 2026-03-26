"""Watchlist — user's daily focus universe."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base, TimestampMixin
from libs.core.time import utc_now


class WatchlistGroup(Base, TimestampMixin):
    __tablename__ = "watchlist_group"

    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class WatchlistItem(Base):
    __tablename__ = "watchlist_item"

    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("watchlist_group.group_id"), nullable=False)
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=text("now()"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
