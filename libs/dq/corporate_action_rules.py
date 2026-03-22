"""DQ rules for corporate actions."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_corporate_action_validity(session: Session) -> list[dict]:
    """DQ-5: split ratio > 0, dividend >= 0, ex_date not null."""
    issues = []

    # Check split ratios
    sql = text("""
        SELECT action_id::text, instrument_id::text, action_type, ex_date::text,
               split_from, split_to, cash_amount
        FROM corporate_action
        WHERE (action_type = 'split' AND (split_from <= 0 OR split_to <= 0 OR split_from IS NULL OR split_to IS NULL))
           OR (action_type = 'cash_dividend' AND (cash_amount < 0))
           OR ex_date IS NULL
        LIMIT 1000
    """)
    rows = session.execute(sql).fetchall()
    for row in rows:
        issues.append({
            "severity": "error",
            "table_name": "corporate_action",
            "record_key": str(row[0]),
            "details": {
                "action_type": row[2],
                "ex_date": row[3],
                "split_from": float(row[4]) if row[4] else None,
                "split_to": float(row[5]) if row[5] else None,
                "cash_amount": float(row[6]) if row[6] else None,
                "reason": "Invalid corporate action: bad ratio, negative dividend, or missing ex_date",
            },
        })
    return issues
