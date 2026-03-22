"""DQ rules for identifier and ticker history consistency."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_ticker_history_overlap(session: Session) -> list[dict]:
    """Check for overlapping ticker history intervals for the same instrument."""
    sql = text("""
        SELECT a.instrument_id::text, a.ticker,
               a.effective_from::text as a_from, a.effective_to::text as a_to,
               b.effective_from::text as b_from, b.effective_to::text as b_to
        FROM ticker_history a
        JOIN ticker_history b
            ON a.instrument_id = b.instrument_id
            AND a.ticker = b.ticker
            AND a.effective_from < b.effective_from
            AND (a.effective_to IS NULL OR a.effective_to >= b.effective_from)
            AND a.effective_from != b.effective_from
        LIMIT 100
    """)
    rows = session.execute(sql).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "warning",
            "table_name": "ticker_history",
            "record_key": f"{row[0]}|{row[1]}",
            "details": {
                "ticker": row[1],
                "interval_a": f"{row[2]}..{row[3]}",
                "interval_b": f"{row[4]}..{row[5]}",
                "reason": "Overlapping ticker history intervals",
            },
        })
    return issues


def check_orphan_identifiers(session: Session) -> list[dict]:
    """Check for identifiers referencing non-existent instruments."""
    sql = text("""
        SELECT ii.instrument_id::text, ii.id_type, ii.id_value
        FROM instrument_identifier ii
        LEFT JOIN instrument i ON ii.instrument_id = i.instrument_id
        WHERE i.instrument_id IS NULL
        LIMIT 100
    """)
    rows = session.execute(sql).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "error",
            "table_name": "instrument_identifier",
            "record_key": f"{row[0]}|{row[1]}|{row[2]}",
            "details": {"reason": "Orphan identifier — no matching instrument"},
        })
    return issues
