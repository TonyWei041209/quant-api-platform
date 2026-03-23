"""Event study: post-earnings return analysis.

Minimum viable: compute 1/3/5/10-day returns after earnings announcements.
All data must be PIT-safe.

Every function requires an explicit asof_date parameter to prevent
look-ahead bias — only events with report_date <= asof_date are included.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from libs.core.logging import get_logger

logger = get_logger(__name__)

WINDOWS = [1, 3, 5, 10]


def earnings_event_study(
    session: Session,
    instrument_id: str,
    asof_date: date = ...,  # type: ignore[assignment]
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """Compute post-earnings returns for an instrument.

    asof_date is required to prevent look-ahead bias.
    Only earnings events with report_date <= asof_date are included.

    Returns DataFrame with columns:
        event_id, report_date, eps_actual, eps_estimate, surprise,
        ret_1d, ret_3d, ret_5d, ret_10d
    """
    if windows is None:
        windows = WINDOWS

    # Get earnings events — only those reported on or before asof_date
    events_sql = text("""
        SELECT event_id::text, report_date, eps_actual, eps_estimate,
               revenue_actual, revenue_estimate
        FROM earnings_event
        WHERE instrument_id = :iid
          AND report_date <= :asof_date
        ORDER BY report_date
    """)
    events = pd.read_sql(events_sql, session.bind, params={"iid": instrument_id, "asof_date": asof_date})
    if events.empty:
        return events

    # Get price data — only up to asof_date
    prices_sql = text("""
        SELECT trade_date, close
        FROM price_bar_raw
        WHERE instrument_id = :iid
          AND trade_date <= :asof_date
        ORDER BY trade_date
    """)
    prices = pd.read_sql(prices_sql, session.bind, params={"iid": instrument_id, "asof_date": asof_date})
    if prices.empty:
        return pd.DataFrame()

    prices = prices.set_index("trade_date").sort_index()

    results = []
    for _, event in events.iterrows():
        report_date = event["report_date"]
        row = {
            "event_id": event["event_id"],
            "report_date": report_date,
            "eps_actual": event["eps_actual"],
            "eps_estimate": event["eps_estimate"],
            "surprise": (
                float(event["eps_actual"]) - float(event["eps_estimate"])
                if event["eps_actual"] is not None and event["eps_estimate"] is not None
                else None
            ),
        }

        # Find the close price on or just before report date
        pre_prices = prices[prices.index <= report_date]
        if pre_prices.empty:
            for w in windows:
                row[f"ret_{w}d"] = None
            results.append(row)
            continue

        base_price = float(pre_prices.iloc[-1]["close"])
        if base_price <= 0:
            for w in windows:
                row[f"ret_{w}d"] = None
            results.append(row)
            continue

        for w in windows:
            target_date = report_date + timedelta(days=w)
            # Clamp target_date to asof_date so we never use future prices
            if target_date > asof_date:
                target_date = asof_date
            post_prices = prices[(prices.index > report_date) & (prices.index <= target_date)]
            if post_prices.empty:
                row[f"ret_{w}d"] = None
            else:
                end_price = float(post_prices.iloc[-1]["close"])
                row[f"ret_{w}d"] = (end_price - base_price) / base_price

        results.append(row)

    return pd.DataFrame(results)


def earnings_event_study_summary(
    session: Session,
    asof_date: date = ...,  # type: ignore[assignment]
    instrument_ids: list[str] | None = None,
    min_date: date | None = None,
    max_date: date | None = None,
    windows: list[int] | None = None,
) -> dict:
    """Compute grouped earnings event study summary across multiple instruments.

    asof_date is required to prevent look-ahead bias.
    Only earnings events with report_date <= asof_date are included.

    Returns dict with per-window statistics and per-ticker breakdowns.
    """
    if windows is None:
        windows = WINDOWS

    # Get all instruments if none specified
    if instrument_ids is None:
        from sqlalchemy import text as sql_text
        rows = session.execute(sql_text(
            "SELECT DISTINCT instrument_id::text FROM earnings_event WHERE report_date <= :asof_date"
        ), {"asof_date": asof_date}).fetchall()
        instrument_ids = [r[0] for r in rows]

    all_results = []
    ticker_map = {}

    for iid in instrument_ids:
        df = earnings_event_study(session, iid, asof_date=asof_date, windows=windows)
        if not df.empty:
            df["instrument_id"] = iid
            # Get ticker
            from sqlalchemy import text as sql_text
            ticker_row = session.execute(sql_text(
                "SELECT id_value FROM instrument_identifier WHERE instrument_id = :iid AND id_type = 'ticker' LIMIT 1"
            ), {"iid": iid}).fetchone()
            ticker = ticker_row[0] if ticker_row else iid[:8]
            df["ticker"] = ticker
            ticker_map[iid] = ticker

            if min_date:
                df = df[df["report_date"] >= min_date]
            if max_date:
                df = df[df["report_date"] <= max_date]

            all_results.append(df)

    if not all_results:
        return {"total_events": 0, "windows": {}, "by_ticker": {}}

    combined = pd.concat(all_results, ignore_index=True)

    result = {
        "total_events": len(combined),
        "date_range": {
            "min": str(combined["report_date"].min()),
            "max": str(combined["report_date"].max()),
        },
        "windows": {},
        "by_ticker": {},
    }

    for w in windows:
        col = f"ret_{w}d"
        vals = combined[col].dropna()
        if vals.empty:
            continue
        result["windows"][f"{w}d"] = {
            "mean": float(vals.mean()),
            "median": float(vals.median()),
            "std": float(vals.std()),
            "win_rate": float((vals > 0).sum() / len(vals)),
            "sample_count": int(len(vals)),
            "min": float(vals.min()),
            "max": float(vals.max()),
        }

    for ticker in combined["ticker"].unique():
        t_df = combined[combined["ticker"] == ticker]
        ticker_stats = {}
        for w in windows:
            col = f"ret_{w}d"
            vals = t_df[col].dropna()
            if vals.empty:
                continue
            ticker_stats[f"{w}d"] = {
                "mean": float(vals.mean()),
                "median": float(vals.median()),
                "win_rate": float((vals > 0).sum() / len(vals)),
                "sample_count": int(len(vals)),
            }
        result["by_ticker"][ticker] = ticker_stats

    return result
