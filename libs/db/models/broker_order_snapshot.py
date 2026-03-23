"""BrokerOrderSnapshot — broker order history snapshots."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class BrokerOrderSnapshot(Base):
    __tablename__ = "broker_order_snapshot"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    broker_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"))
    broker_ticker: Mapped[str | None] = mapped_column(String(30))
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    filled_qty: Mapped[float | None] = mapped_column(Numeric(18, 6))
    limit_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    stop_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    avg_fill_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at_broker: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text, nullable=False, default="trading212")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
