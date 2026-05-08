"""Portfolio Context Service — aggregates broker snapshots into unified portfolio view.

This is the canonical contract for Portfolio Context in v1.7.0.

Three layers:
  1. FACT layer    — broker_*_snapshot tables (readonly truth from broker)
  2. DERIVED layer — portfolio summary, holding relationships, cross-references
  3. SESSION layer — WorkspaceContext activeInstrument + portfolio awareness

This service produces DERIVED layer objects from FACT layer data.
It never writes to broker tables. It never triggers broker API calls.
It only reads the most recent snapshots from the database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


def _latest_sync_session_id(db: Session, broker: str) -> UUID | None:
    """Return the most recent non-null sync_session_id for the broker, else None.

    Used by all position-reading helpers so closed-out tickers (which never
    receive a qty=0 marker because T212 only returns currently-held positions)
    drop out of the dashboard view as soon as the next sync runs.
    """
    row = db.execute(text("""
        SELECT sync_session_id
        FROM broker_position_snapshot
        WHERE broker = :broker AND sync_session_id IS NOT NULL
        ORDER BY snapshot_at DESC
        LIMIT 1
    """), {"broker": broker}).fetchone()
    return row[0] if row and row[0] is not None else None


def get_portfolio_summary(db: Session, broker: str = "trading212") -> dict:
    """
    Aggregate the latest account snapshot, positions, and recent orders
    into a single portfolio summary dict.

    Returns:
        {
            "connected": bool,
            "account": { ... } | None,
            "positions": [ { instrument_id, broker_ticker, quantity, ... } ],
            "position_count": int,
            "total_market_value": float,
            "total_pnl": float,
            "recent_orders": [ { ... } ],
            "held_instrument_ids": [str],
            "as_of": str | None,
            "source": str,
        }
    """
    result = {
        "connected": False,
        "account": None,
        "positions": [],
        "position_count": 0,
        "total_market_value": 0.0,
        "total_pnl": 0.0,
        "recent_orders": [],
        "held_instrument_ids": [],
        "as_of": None,
        "source": broker,
    }

    # 1. Latest account snapshot
    acct_row = db.execute(text("""
        SELECT snapshot_id, broker, account_id, cash_free, cash_total,
               portfolio_value, currency, snapshot_at
        FROM broker_account_snapshot
        WHERE broker = :broker
        ORDER BY snapshot_at DESC LIMIT 1
    """), {"broker": broker}).fetchone()

    if acct_row:
        result["connected"] = True
        result["account"] = {
            "account_id": str(acct_row[2]) if acct_row[2] else None,
            "cash_free": float(acct_row[3]) if acct_row[3] else 0.0,
            "cash_total": float(acct_row[4]) if acct_row[4] else 0.0,
            "portfolio_value": float(acct_row[5]) if acct_row[5] else 0.0,
            "currency": acct_row[6] or "USD",
            "snapshot_at": acct_row[7].isoformat() if acct_row[7] else None,
        }
        result["as_of"] = acct_row[7].isoformat() if acct_row[7] else None

    # 2. Latest position snapshots — snapshot-set semantics with legacy fallback.
    #
    # Primary path: if the broker has any rows with sync_session_id set, return
    # only positions from the most recent sync_session_id. This eliminates
    # ghost positions because a closed-out ticker simply isn't present in the
    # newest sync run (T212 only returns currently-held positions, and the
    # sync writes one row per held position per run, all sharing one UUID).
    #
    # Legacy fallback: when no non-null sync_session_id exists yet (pre-
    # migration data, or production has not yet run a single post-deploy
    # sync), preserve the prior DISTINCT ON (broker_ticker) WHERE quantity>0
    # behavior so the dashboard does not go blank during the rollout window.
    latest_sid = _latest_sync_session_id(db, broker)
    if latest_sid is not None:
        pos_rows = db.execute(text("""
            SELECT snapshot_id, broker, instrument_id, broker_ticker,
                   quantity, avg_cost, current_price, market_value, pnl,
                   currency, snapshot_at
            FROM broker_position_snapshot
            WHERE broker = :broker
              AND sync_session_id = :sid
              AND quantity > 0
            ORDER BY snapshot_at DESC, broker_ticker
        """), {"broker": broker, "sid": latest_sid}).fetchall()
    else:
        pos_rows = db.execute(text("""
            SELECT DISTINCT ON (broker_ticker)
                   snapshot_id, broker, instrument_id, broker_ticker,
                   quantity, avg_cost, current_price, market_value, pnl,
                   currency, snapshot_at
            FROM broker_position_snapshot
            WHERE broker = :broker AND quantity > 0
            ORDER BY broker_ticker, snapshot_at DESC
        """), {"broker": broker}).fetchall()

    positions = []
    held_ids = []
    total_mv = 0.0
    total_pnl = 0.0

    for row in pos_rows:
        inst_id = str(row[2]) if row[2] else None
        mv = float(row[7]) if row[7] else 0.0
        pnl = float(row[8]) if row[8] else 0.0
        total_mv += mv
        total_pnl += pnl
        if inst_id:
            held_ids.append(inst_id)
        positions.append({
            "instrument_id": inst_id,
            "broker_ticker": row[3],
            "quantity": float(row[4]) if row[4] else 0,
            "avg_cost": float(row[5]) if row[5] else 0,
            "current_price": float(row[6]) if row[6] else 0,
            "market_value": mv,
            "pnl": pnl,
            "pnl_percent": (pnl / (mv - pnl) * 100) if mv != pnl and (mv - pnl) != 0 else 0,
            "currency": row[9] or "USD",
            "snapshot_at": row[10].isoformat() if row[10] else None,
        })

    result["positions"] = positions
    result["position_count"] = len(positions)
    result["total_market_value"] = total_mv
    result["total_pnl"] = total_pnl
    result["held_instrument_ids"] = held_ids

    # 3. Recent orders (last 10)
    ord_rows = db.execute(text("""
        SELECT snapshot_id, broker, broker_order_id, instrument_id, broker_ticker,
               side, order_type, qty, filled_qty, avg_fill_price, status,
               created_at_broker, filled_at, snapshot_at
        FROM broker_order_snapshot
        WHERE broker = :broker
        ORDER BY snapshot_at DESC LIMIT 10
    """), {"broker": broker}).fetchall()

    orders = []
    for row in ord_rows:
        orders.append({
            "broker_order_id": row[2],
            "instrument_id": str(row[3]) if row[3] else None,
            "broker_ticker": row[4],
            "side": row[5],
            "order_type": row[6],
            "qty": float(row[7]) if row[7] else 0,
            "filled_qty": float(row[8]) if row[8] else 0,
            "avg_fill_price": float(row[9]) if row[9] else 0,
            "status": row[10],
            "created_at": row[11].isoformat() if row[11] else None,
            "filled_at": row[12].isoformat() if row[12] else None,
        })

    result["recent_orders"] = orders

    return result


def is_instrument_held(db: Session, instrument_id: str, broker: str = "trading212") -> dict:
    """
    Check if a specific instrument is currently held in the portfolio.

    Returns:
        {
            "held": bool,
            "quantity": float,
            "avg_cost": float,
            "current_price": float,
            "market_value": float,
            "pnl": float,
            "broker_ticker": str | None,
            "snapshot_at": str | None,
        }
    """
    latest_sid = _latest_sync_session_id(db, broker)
    if latest_sid is not None:
        row = db.execute(text("""
            SELECT broker_ticker, quantity, avg_cost, current_price, market_value, pnl, snapshot_at
            FROM broker_position_snapshot
            WHERE broker = :broker
              AND sync_session_id = :sid
              AND instrument_id = :iid
              AND quantity > 0
            ORDER BY snapshot_at DESC LIMIT 1
        """), {"broker": broker, "sid": latest_sid, "iid": instrument_id}).fetchone()
    else:
        row = db.execute(text("""
            SELECT broker_ticker, quantity, avg_cost, current_price, market_value, pnl, snapshot_at
            FROM broker_position_snapshot
            WHERE broker = :broker AND instrument_id = :iid AND quantity > 0
            ORDER BY snapshot_at DESC LIMIT 1
        """), {"broker": broker, "iid": instrument_id}).fetchone()

    if row and row[1] and float(row[1]) > 0:
        return {
            "held": True,
            "broker_ticker": row[0],
            "quantity": float(row[1]),
            "avg_cost": float(row[2]) if row[2] else 0,
            "current_price": float(row[3]) if row[3] else 0,
            "market_value": float(row[4]) if row[4] else 0,
            "pnl": float(row[5]) if row[5] else 0,
            "snapshot_at": row[6].isoformat() if row[6] else None,
        }

    return {"held": False, "quantity": 0, "broker_ticker": None}


def get_watchlist_holdings_overlay(db: Session, group_id: str, broker: str = "trading212") -> dict:
    """
    For a given watchlist group, return which items are currently held.

    Returns:
        {
            "group_id": str,
            "total_items": int,
            "held_items": [ { instrument_id, broker_ticker, quantity } ],
            "held_count": int,
            "unheld_count": int,
        }
    """
    # Get watchlist items
    items = db.execute(text("""
        SELECT wi.instrument_id
        FROM watchlist_item wi
        WHERE wi.group_id = :gid
    """), {"gid": group_id}).fetchall()

    item_ids = [str(r[0]) for r in items]

    if not item_ids:
        return {
            "group_id": group_id,
            "total_items": 0,
            "held_items": [],
            "held_count": 0,
            "unheld_count": 0,
        }

    # Check which are held — snapshot-set semantics with legacy fallback.
    latest_sid = _latest_sync_session_id(db, broker)
    if latest_sid is not None:
        held_rows = db.execute(text("""
            SELECT instrument_id, broker_ticker, quantity
            FROM broker_position_snapshot
            WHERE broker = :broker
              AND sync_session_id = :sid
              AND instrument_id = ANY(:ids)
              AND quantity > 0
        """), {"broker": broker, "sid": latest_sid, "ids": item_ids}).fetchall()
    else:
        held_rows = db.execute(text("""
            SELECT DISTINCT ON (instrument_id)
                   instrument_id, broker_ticker, quantity
            FROM broker_position_snapshot
            WHERE broker = :broker
              AND instrument_id = ANY(:ids)
              AND quantity > 0
            ORDER BY instrument_id, snapshot_at DESC
        """), {"broker": broker, "ids": item_ids}).fetchall()

    held_items = [
        {
            "instrument_id": str(r[0]),
            "broker_ticker": r[1],
            "quantity": float(r[2]) if r[2] else 0,
        }
        for r in held_rows
    ]

    return {
        "group_id": group_id,
        "total_items": len(item_ids),
        "held_items": held_items,
        "held_count": len(held_items),
        "unheld_count": len(item_ids) - len(held_items),
    }


def get_research_status_batch(db: Session, instrument_ids: list[str]) -> dict:
    """
    For a list of instrument IDs, return aggregated research note status.

    Returns:
        {
            "instrument_id_str": {
                "has_thesis": bool,
                "has_risk": bool,
                "has_observation": bool,
                "note_count": int,
                "last_note_at": str | None,
            },
            ...
        }
    """
    if not instrument_ids:
        return {}

    # Filter to valid UUIDs only
    import uuid as _uuid
    valid_ids = []
    for iid in instrument_ids:
        try:
            valid_ids.append(str(_uuid.UUID(str(iid))))
        except (ValueError, AttributeError):
            pass
    if not valid_ids:
        return {}

    # Use IN clause with explicit UUID list (safe from injection since validated)
    placeholders = ", ".join(f"'{uid}'::uuid" for uid in valid_ids)
    rows = db.execute(text(f"""
        SELECT instrument_id::text, note_type, COUNT(*) as cnt, MAX(updated_at) as last_at
        FROM research_note
        WHERE instrument_id IN ({placeholders})
        GROUP BY instrument_id, note_type
    """)).fetchall()

    result = {}
    for row in rows:
        iid = str(row[0])
        note_type = row[1] or "general"
        cnt = int(row[2])
        last_at = row[3].isoformat() if row[3] else None

        if iid not in result:
            result[iid] = {
                "has_thesis": False,
                "has_risk": False,
                "has_observation": False,
                "note_count": 0,
                "last_note_at": None,
            }

        entry = result[iid]
        entry["note_count"] += cnt
        if last_at and (entry["last_note_at"] is None or last_at > entry["last_note_at"]):
            entry["last_note_at"] = last_at

        if note_type == "thesis":
            entry["has_thesis"] = True
        elif note_type == "risk":
            entry["has_risk"] = True
        elif note_type == "observation":
            entry["has_observation"] = True

    return result
