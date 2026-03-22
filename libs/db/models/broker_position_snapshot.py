"""BrokerPositionSnapshot — broker position snapshots."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


class BrokerPositionSnapshot(Base):
    __tablename__ = "broker_position_snapshot"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker: Mapped[str] = mapped_column(String(30), nullable=False)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"))
    broker_ticker: Mapped[str | None] = mapped_column(String(30))
    quantity: Mapped[float] = mapped_column(Numeric(18, 6), nullable=False)
    avg_cost: Mapped[float | None] = mapped_column(Numeric(18, 6))
    current_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    market_value: Mapped[float | None] = mapped_column(Numeric(18, 6))
    pnl: Mapped[float | None] = mapped_column(Numeric(18, 6))
    currency: Mapped[str | None] = mapped_column(String(10))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, server_default=text("now()"),
    )
