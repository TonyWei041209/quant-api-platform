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


def check_cross_source_price_divergence(session: Session, tolerance: float = 0.05) -> list[dict]:
    """Check if prices from different sources diverge more than tolerance for same date."""
    sql = text("""
        SELECT a.instrument_id::text, a.trade_date::text,
               a.source as src_a, b.source as src_b,
               a.close as close_a, b.close as close_b,
               ABS(a.close - b.close) / NULLIF(a.close, 0) as pct_diff
        FROM price_bar_raw a
        JOIN price_bar_raw b
            ON a.instrument_id = b.instrument_id
            AND a.trade_date = b.trade_date
            AND a.source < b.source
        WHERE ABS(a.close - b.close) / NULLIF(a.close, 0) > :tolerance
        LIMIT 100
    """)
    rows = session.execute(sql, {"tolerance": tolerance}).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "warning",
            "table_name": "price_bar_raw",
            "record_key": f"{row[0]}|{row[1]}",
            "details": {
                "source_a": row[2], "source_b": row[3],
                "close_a": float(row[4]), "close_b": float(row[5]),
                "pct_diff": float(row[6]),
                "reason": "Cross-source price divergence exceeds tolerance",
            },
        })
    return issues


def check_raw_adjusted_contamination(session: Session) -> list[dict]:
    """DQ-11: Verify price_bar_raw contains no rows where source indicates adjusted data."""
    sql = text("""
        SELECT instrument_id::text, trade_date::text, source
        FROM price_bar_raw
        WHERE LOWER(source) LIKE '%adjusted%'
           OR LOWER(source) LIKE '%adj%close%'
           OR LOWER(source) LIKE '%split%adjusted%'
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
                "source": row[2],
                "reason": "Raw price table contaminated with adjusted data source",
            },
        })
    return issues


def check_stale_prices(session: Session, max_gap_days: int = 5) -> list[dict]:
    """Check for instruments with gaps in price data exceeding max_gap_days."""
    sql = text("""
        WITH gaps AS (
            SELECT instrument_id, trade_date,
                   trade_date - LAG(trade_date) OVER (PARTITION BY instrument_id ORDER BY trade_date) as gap_days
            FROM price_bar_raw
        )
        SELECT instrument_id::text, trade_date::text, gap_days
        FROM gaps
        WHERE gap_days > :max_gap
        LIMIT 100
    """)
    rows = session.execute(sql, {"max_gap": max_gap_days}).fetchall()
    issues = []
    for row in rows:
        issues.append({
            "severity": "warning",
            "table_name": "price_bar_raw",
            "record_key": f"{row[0]}|{row[1]}",
            "details": {"gap_days": int(row[2]), "reason": f"Price gap of {row[2]} days"},
        })
    return issues
