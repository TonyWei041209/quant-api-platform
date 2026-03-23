"""Backtest trade persistence model."""
from __future__ import annotations
import uuid
from datetime import date, datetime
from sqlalchemy import Text, Date, DateTime, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from libs.db.base import Base
from libs.core.time import utc_now

class BacktestTrade(Base):
    __tablename__ = "backtest_trade"

    trade_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("backtest_run.run_id"), nullable=False, index=True)
    instrument_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("instrument.instrument_id"), nullable=False)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[str] = mapped_column(Text, nullable=False)  # BUY or SELL
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    slippage_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    notional: Mapped[float] = mapped_column(Float, nullable=False)
