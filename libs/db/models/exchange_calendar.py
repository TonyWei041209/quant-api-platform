"""ExchangeCalendar — trading day calendar."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, String, text
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base


class ExchangeCalendar(Base):
    __tablename__ = "exchange_calendar"

    exchange: Mapped[str] = mapped_column(String(20), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    session_open_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_close_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    has_extended_hours: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    source: Mapped[str] = mapped_column(String(50), nullable=False)
