"""Compute split-adjusted and total-return-adjusted price series.

Rules:
- Based on price_bar_raw + corporate_action
- Never overwrites raw table
- Uses ex_date for corporate action effective date
- Split adjustment: multiply by cumulative split factor (reverse from latest)
- Total return: also adjust for dividends
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from libs.core.logging import get_logger

logger = get_logger(__name__)


def get_split_adjusted_prices(
    session: Session,
    instrument_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Compute split-adjusted price series for an instrument.

    Returns DataFrame with columns: trade_date, open, high, low, close, volume, adj_factor
    """
    # Get raw prices
    price_sql = text("""
        SELECT trade_date, open, high, low, close, volume
        FROM price_bar_raw
        WHERE instrument_id = :iid
          AND (:start IS NULL OR trade_date >= :start)
          AND (:end IS NULL OR trade_date <= :end)
        ORDER BY trade_date
    """)
    prices = pd.read_sql(
        price_sql, session.bind,
        params={"iid": instrument_id, "start": start_date, "end": end_date},
    )
    if prices.empty:
        return prices

    # Get splits
    split_sql = text("""
        SELECT ex_date, split_from, split_to
        FROM corporate_action
        WHERE instrument_id = :iid AND action_type = 'split'
          AND split_from > 0 AND split_to > 0
        ORDER BY ex_date
    """)
    splits = pd.read_sql(split_sql, session.bind, params={"iid": instrument_id})

    # Compute cumulative split factor (reverse chronological)
    prices["adj_factor"] = 1.0
    for _, split in splits.iterrows():
        ratio = float(split["split_to"]) / float(split["split_from"])
        mask = prices["trade_date"] < split["ex_date"]
        prices.loc[mask, "adj_factor"] *= ratio

    # Apply adjustment
    for col in ["open", "high", "low", "close"]:
        prices[col] = prices[col].astype(float) * prices["adj_factor"]
    prices["volume"] = (prices["volume"].astype(float) / prices["adj_factor"]).astype(int)

    return prices


def get_total_return_adjusted_prices(
    session: Session,
    instrument_id: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Compute total-return-adjusted series (split + dividend adjusted).

    Dividend adjustment: f *= (P_prev - D) / P_prev
    """
    prices = get_split_adjusted_prices(session, instrument_id, start_date, end_date)
    if prices.empty:
        return prices

    # Get dividends
    div_sql = text("""
        SELECT ex_date, cash_amount
        FROM corporate_action
        WHERE instrument_id = :iid AND action_type = 'cash_dividend'
          AND cash_amount > 0
        ORDER BY ex_date
    """)
    dividends = pd.read_sql(div_sql, session.bind, params={"iid": instrument_id})

    prices["tr_factor"] = 1.0
    for _, div in dividends.iterrows():
        ex = div["ex_date"]
        cash = float(div["cash_amount"])
        # Find previous day close
        prev_prices = prices[prices["trade_date"] < ex]
        if prev_prices.empty:
            continue
        prev_close = float(prev_prices.iloc[-1]["close"])
        if prev_close <= 0:
            continue
        ratio = (prev_close - cash) / prev_close
        mask = prices["trade_date"] < ex
        prices.loc[mask, "tr_factor"] *= ratio

    for col in ["open", "high", "low", "close"]:
        prices[col] = prices[col].astype(float) * prices["tr_factor"]

    return prices
