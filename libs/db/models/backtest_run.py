"""Backtest run persistence model."""
from __future__ import annotations
import uuid
from datetime import date, datetime
from sqlalchemy import Text, Date, DateTime, Float, Integer, Boolean
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from libs.db.base import Base
from libs.core.time import utc_now

class BacktestRun(Base):
    __tablename__ = "backtest_run"

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    strategy_name: Mapped[str] = mapped_column(Text, nullable=False)
    universe_description: Mapped[str] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Configuration
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Cost model params
    commission_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    slippage_bps: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Results metrics
    total_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    annualized_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    volatility: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turnover: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_costs: Mapped[float | None] = mapped_column(Float, nullable=True)
    # NAV series (daily)
    nav_series: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Status
    status: Mapped[str] = mapped_column(Text, nullable=False, default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
