"""Event study: post-earnings return analysis.

Minimum viable: compute 1/3/5/10-day returns after earnings announcements.
All data must be PIT-safe.
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
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """Compute post-earnings returns for an instrument.

    Returns DataFrame with columns:
        event_id, report_date, eps_actual, eps_estimate, surprise,
        ret_1d, ret_3d, ret_5d, ret_10d
    """
    if windows is None:
        windows = WINDOWS

    # Get earnings events
    events_sql = text("""
        SELECT event_id::text, report_date, eps_actual, eps_estimate,
               revenue_actual, revenue_estimate
        FROM earnings_event
        WHERE instrument_id = :iid
        ORDER BY report_date
    """)
    events = pd.read_sql(events_sql, session.bind, params={"iid": instrument_id})
    if events.empty:
        return events

    # Get price data
    prices_sql = text("""
        SELECT trade_date, close
        FROM price_bar_raw
        WHERE instrument_id = :iid
        ORDER BY trade_date
    """)
    prices = pd.read_sql(prices_sql, session.bind, params={"iid": instrument_id})
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
            post_prices = prices[(prices.index > report_date) & (prices.index <= target_date)]
            if post_prices.empty:
                row[f"ret_{w}d"] = None
            else:
                end_price = float(post_prices.iloc[-1]["close"])
                row[f"ret_{w}d"] = (end_price - base_price) / base_price

        results.append(row)

    return pd.DataFrame(results)
