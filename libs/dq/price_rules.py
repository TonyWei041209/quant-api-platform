"""DQ rules for price data."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def check_ohlc_logic(session: Session) -> list[dict]:
    """DQ-1: high >= max(open,close,low) and low <= min(open,close,high)."""
    sql = text("""
        SELECT instrument_id::text, trade_date::text, source,
               open, high, low, close
        FROM price_bar_raw
        WHERE high < GREATEST(open, close, low)
           OR low > LEAST(open, close, high)
        LIMIT 1000
    """)
    rows = session.execute(sql).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "error",
            "table_name": "price_bar_raw",
            "record_key": f"{row[0]}|{row[1]}|{row[2]}",
            "details": {
                "open": float(row[3]),
                "high": float(row[4]),
                "low": float(row[5]),
                "close": float(row[6]),
                "reason": "OHLC logic violation: high < max(O,C,L) or low > min(O,C,H)",
            },
        })
    return issues


def check_non_negative_prices(session: Session) -> list[dict]:
    """DQ-2: price >= 0 and volume >= 0."""
    sql = text("""
        SELECT instrument_id::text, trade_date::text, source,
               open, high, low, close, volume
        FROM price_bar_raw
        WHERE open < 0 OR high < 0 OR low < 0 OR close < 0 OR volume < 0
        LIMIT 1000
    """)
    rows = session.execute(sql).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "error",
            "table_name": "price_bar_raw",
            "record_key": f"{row[0]}|{row[1]}|{row[2]}",
            "details": {"reason": "Negative price or volume detected"},
        })
    return issues
