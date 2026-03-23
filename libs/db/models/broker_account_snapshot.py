"""BrokerAccountSnapshot — broker account summary snapshots."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class BrokerAccountSnapshot(Base):
    __tablename__ = "broker_account_snapshot"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    cash_free: Mapped[float | None] = mapped_column(Numeric(18, 6))
    cash_total: Mapped[float | None] = mapped_column(Numeric(18, 6))
    portfolio_value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str | None] = mapped_column(String(10))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="trading212")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
