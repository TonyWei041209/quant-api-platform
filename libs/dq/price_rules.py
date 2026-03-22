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


def check_trading_day_consistency(session: Session) -> list[dict]:
    """DQ-4: price_bar_raw.trade_date must be an open day in exchange_calendar."""
    sql = text("""
        SELECT p.instrument_id::text, p.trade_date::text, p.source
        FROM price_bar_raw p
        LEFT JOIN exchange_calendar ec
            ON ec.exchange IN ('NYSE', 'NASDAQ')
            AND ec.trade_date = p.trade_date
            AND ec.is_open = true
        WHERE ec.trade_date IS NULL
          AND EXISTS (SELECT 1 FROM exchange_calendar WHERE trade_date = p.trade_date)
        LIMIT 1000
    """)
    rows = session.execute(sql).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "warning",
            "table_name": "price_bar_raw",
            "record_key": f"{row[0]}|{row[1]}|{row[2]}",
            "details": {"reason": "Price bar on a non-trading day (market closed or holiday)"},
        })
    return issues
