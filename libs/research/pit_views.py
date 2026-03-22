"""Point-in-time safe views for financial data.

Core rule: NEVER return data where reported_at > asof_time.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from libs.core.logging import get_logger
from libs.core.time import utc_now

logger = get_logger(__name__)


def get_latest_financials_pit(
    session: Session,
    instrument_id: str,
    asof_time: datetime | None = None,
) -> pd.DataFrame:
    """Get the latest available financial facts as of a given time.

    This is PIT-safe: only returns data that was publicly known at asof_time.
    """
    if asof_time is None:
        asof_time = utc_now()

    sql = text("""
        WITH ranked AS (
            SELECT
                fp.financial_period_id,
                fp.fiscal_year,
                fp.fiscal_quarter,
                fp.period_end,
                fp.reported_at,
                fp.statement_scope,
                ff.statement_type,
                ff.metric_code,
                ff.metric_value,
                ff.unit,
                ROW_NUMBER() OVER (
                    PARTITION BY ff.statement_type, ff.metric_code
                    ORDER BY fp.period_end DESC, fp.reported_at DESC
                ) as rn
            FROM financial_period fp
            JOIN financial_fact_std ff ON fp.financial_period_id = ff.financial_period_id
            WHERE fp.instrument_id = :iid
              AND fp.reported_at <= :asof
        )
        SELECT fiscal_year, fiscal_quarter, period_end, reported_at,
               statement_scope, statement_type, metric_code, metric_value, unit
        FROM ranked
        WHERE rn = 1
        ORDER BY statement_type, metric_code
    """)
    return pd.read_sql(sql, session.bind, params={"iid": instrument_id, "asof": asof_time})


def get_financial_history_pit(
    session: Session,
    instrument_id: str,
    metric_code: str,
    asof_time: datetime | None = None,
) -> pd.DataFrame:
    """Get historical values for a specific metric, PIT-safe."""
    if asof_time is None:
        asof_time = utc_now()

    sql = text("""
        SELECT
            fp.fiscal_year,
            fp.fiscal_quarter,
            fp.period_end,
            fp.reported_at,
            ff.metric_value,
            ff.unit
        FROM financial_period fp
        JOIN financial_fact_std ff ON fp.financial_period_id = ff.financial_period_id
        WHERE fp.instrument_id = :iid
          AND ff.metric_code = :metric
          AND fp.reported_at <= :asof
        ORDER BY fp.period_end
    """)
    return pd.read_sql(
        sql, session.bind,
        params={"iid": instrument_id, "metric": metric_code, "asof": asof_time},
    )
