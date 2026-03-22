"""DQ rules for filings."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_duplicate_accession(session: Session) -> list[dict]:
    """DQ-3: No duplicate accession numbers in filing table."""
    sql = text("""
        SELECT accession_no, COUNT(*) as cnt
        FROM filing
        GROUP BY accession_no
        HAVING COUNT(*) > 1
        LIMIT 100
    """)
    rows = session.execute(sql).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "error",
            "table_name": "filing",
            "record_key": row[0],
            "details": {"count": row[1], "reason": "Duplicate accession number"},
        })
    return issues
