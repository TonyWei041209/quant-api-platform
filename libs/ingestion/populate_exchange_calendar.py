"""Populate exchange_calendar with NYSE/NASDAQ trading days."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.exchange_calendar import ExchangeCalendar
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)

# Known US market holidays (NYSE/NASDAQ closed) — 2020-2026
# Source: NYSE holiday schedule
US_HOLIDAYS = {
    # 2020
    date(2020, 1, 1), date(2020, 1, 20), date(2020, 2, 17), date(2020, 4, 10),
    date(2020, 5, 25), date(2020, 7, 3), date(2020, 9, 7), date(2020, 11, 26),
    date(2020, 12, 25),
    # 2021
    date(2021, 1, 1), date(2021, 1, 18), date(2021, 2, 15), date(2021, 4, 2),
    date(2021, 5, 31), date(2021, 7, 5), date(2021, 9, 6), date(2021, 11, 25),
    date(2021, 12, 24),
    # 2022
    date(2022, 1, 17), date(2022, 2, 21), date(2022, 4, 15), date(2022, 5, 30),
    date(2022, 6, 20), date(2022, 7, 4), date(2022, 9, 5), date(2022, 11, 24),
    date(2022, 12, 26),
    # 2023
    date(2023, 1, 2), date(2023, 1, 16), date(2023, 2, 20), date(2023, 4, 7),
    date(2023, 5, 29), date(2023, 6, 19), date(2023, 7, 4), date(2023, 9, 4),
    date(2023, 11, 23), date(2023, 12, 25),
    # 2024
    date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 3, 29),
    date(2024, 5, 27), date(2024, 6, 19), date(2024, 7, 4), date(2024, 9, 2),
    date(2024, 11, 28), date(2024, 12, 25),
    # 2025
    date(2025, 1, 1), date(2025, 1, 9), date(2025, 1, 20), date(2025, 2, 17),
    date(2025, 4, 18), date(2025, 5, 26), date(2025, 6, 19), date(2025, 7, 4),
    date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25),
    # 2026
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
    date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
    date(2026, 11, 26), date(2026, 12, 25),
}


def populate_exchange_calendar(
    session: Session,
    exchanges: list[str] | None = None,
    start_year: int = 2020,
    end_year: int = 2026,
) -> dict:
    """Populate exchange_calendar with trading days for NYSE/NASDAQ."""
    if exchanges is None:
        exchanges = ["NYSE", "NASDAQ"]

    run = SourceRun(
        run_id=new_id(), source="internal", job_name="populate_exchange_calendar",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"days_inserted": 0, "holidays_marked": 0}

    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    current = start_date

    while current <= end_date:
        is_weekday = current.weekday() < 5
        is_holiday = current in US_HOLIDAYS

        for exchange in exchanges:
            if is_weekday:
                is_open = not is_holiday
                stmt = pg_insert(ExchangeCalendar).values(
                    exchange=exchange,
                    trade_date=current,
                    is_open=is_open,
                    source="internal_calendar",
                ).on_conflict_do_nothing(
                    index_elements=["exchange", "trade_date"],
                )
                session.execute(stmt)
                counters["days_inserted"] += 1
                if not is_open:
                    counters["holidays_marked"] += 1

        current += timedelta(days=1)

    session.commit()
    run.status = "success"
    run.finished_at = utc_now()
    run.counters = counters
    session.commit()

    logger.info("exchange_calendar.populated", **counters)
    return counters
