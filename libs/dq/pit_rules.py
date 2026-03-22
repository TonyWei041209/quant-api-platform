"""DQ rules for point-in-time (PIT) integrity."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_pit_reported_at(session: Session) -> list[dict]:
    """DQ-6: financial_period.reported_at must exist and be reasonable."""
    sql = text("""
        SELECT financial_period_id::text, instrument_id::text, period_end::text,
               reported_at, fiscal_year
        FROM financial_period
        WHERE reported_at IS NULL
           OR reported_at < '1990-01-01'::timestamptz
           OR reported_at > now() + interval '1 day'
        LIMIT 1000
    """)
    rows = session.execute(sql).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "error",
            "table_name": "financial_period",
            "record_key": str(row[0]),
            "details": {
                "instrument_id": str(row[1]),
                "period_end": row[2],
                "reported_at": str(row[3]) if row[3] else None,
                "reason": "Missing or unreasonable reported_at — breaks PIT guarantee",
            },
        })
    return issues
