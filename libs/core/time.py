"""Time utilities — all storage in UTC."""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta


def utc_now() -> datetime:
    return datetime.now(UTC)


def today_utc() -> date:
    return datetime.now(UTC).date()


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def trading_date_range(start: date, end: date) -> list[date]:
    """Generate date range (inclusive). Weekends excluded as heuristic."""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days
