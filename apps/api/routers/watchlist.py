"""Watchlist API — manage daily focus universe."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.db.models.watchlist import WatchlistGroup, WatchlistItem

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None
    is_default: bool = False


class ItemAdd(BaseModel):
    instrument_id: str
    notes: Optional[str] = None
    tags: Optional[dict] = None


@router.get("/groups")
def list_groups(db: Session = Depends(get_sync_db)):
    groups = db.query(WatchlistGroup).order_by(WatchlistGroup.created_at.desc()).all()
    result = []
    for g in groups:
        count = db.query(WatchlistItem).filter(WatchlistItem.group_id == g.group_id).count()
        result.append({
            "group_id": str(g.group_id),
            "name": g.name,
            "description": g.description,
            "is_default": g.is_default,
            "item_count": count,
            "created_at": g.created_at.isoformat() if g.created_at else None,
        })
    return {"groups": result}


@router.post("/groups")
def create_group(body: GroupCreate, db: Session = Depends(get_sync_db)):
    g = WatchlistGroup(name=body.name, description=body.description, is_default=body.is_default)
    db.add(g)
    db.commit()
    db.refresh(g)
    return {"group_id": str(g.group_id), "name": g.name}


@router.delete("/groups/{group_id}")
def delete_group(group_id: str, db: Session = Depends(get_sync_db)):
    gid = uuid.UUID(group_id)
    db.query(WatchlistItem).filter(WatchlistItem.group_id == gid).delete()
    db.query(WatchlistGroup).filter(WatchlistGroup.group_id == gid).delete()
    db.commit()
    return {"deleted": True}


@router.get("/groups/{group_id}/items")
def list_items(group_id: str, db: Session = Depends(get_sync_db)):
    from libs.db.models.instrument import Instrument
    from libs.db.models.ticker_history import TickerHistory

    gid = uuid.UUID(group_id)
    items = (
        db.query(WatchlistItem, Instrument)
        .join(Instrument, WatchlistItem.instrument_id == Instrument.instrument_id)
        .filter(WatchlistItem.group_id == gid)
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )

    # Build ticker lookup
    inst_ids = [wi.instrument_id for wi, _ in items]
    ticker_map = {}
    if inst_ids:
        ticker_rows = (
            db.query(TickerHistory.instrument_id, TickerHistory.ticker)
            .filter(TickerHistory.instrument_id.in_(inst_ids), TickerHistory.effective_to.is_(None))
            .all()
        )
        ticker_map = {row[0]: row[1] for row in ticker_rows}

    result = []
    for wi, inst in items:
        result.append({
            "item_id": str(wi.item_id),
            "instrument_id": str(wi.instrument_id),
            "ticker": ticker_map.get(wi.instrument_id),
            "issuer_name": inst.issuer_name_current,
            "asset_type": inst.asset_type,
            "is_active": inst.is_active,
            "notes": wi.notes,
            "tags": wi.tags,
            "added_at": wi.added_at.isoformat() if wi.added_at else None,
        })
    return {"items": result, "total": len(result)}


@router.post("/groups/{group_id}/items")
def add_item(group_id: str, body: ItemAdd, db: Session = Depends(get_sync_db)):
    gid = uuid.UUID(group_id)
    iid = uuid.UUID(body.instrument_id)
    existing = db.query(WatchlistItem).filter(
        WatchlistItem.group_id == gid, WatchlistItem.instrument_id == iid
    ).first()
    if existing:
        return {"item_id": str(existing.item_id), "already_exists": True}
    item = WatchlistItem(group_id=gid, instrument_id=iid, notes=body.notes, tags=body.tags)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"item_id": str(item.item_id), "added": True}


@router.delete("/groups/{group_id}/items/{instrument_id}")
def remove_item(group_id: str, instrument_id: str, db: Session = Depends(get_sync_db)):
    gid = uuid.UUID(group_id)
    iid = uuid.UUID(instrument_id)
    db.query(WatchlistItem).filter(
        WatchlistItem.group_id == gid, WatchlistItem.instrument_id == iid
    ).delete()
    db.commit()
    return {"removed": True}


# ---------------------------------------------------------------------------
# Watchlist Quant Snapshot — lightweight price + research freshness
# ---------------------------------------------------------------------------

def _compute_price_snapshots(db: Session, instrument_ids: list[str]) -> dict:
    """Batch-compute 1D/5D/1M price change + 52-week range for given instruments.

    Returns {instrument_id_str: {change_1d_pct, change_5d_pct, change_1m_pct,
    latest_close, latest_trade_date, week52_high, week52_low, week52_pct}}
    with None for insufficient data.
    """
    if not instrument_ids:
        return {}

    from collections import defaultdict

    placeholders = ", ".join(f"'{uid}'::uuid" for uid in instrument_ids)

    # Fetch last 30 trading days per instrument (for 1D/5D/1M)
    rows = db.execute(text(f"""
        WITH ranked AS (
            SELECT instrument_id, trade_date, close,
                   ROW_NUMBER() OVER (PARTITION BY instrument_id ORDER BY trade_date DESC) AS rn
            FROM price_bar_raw
            WHERE instrument_id IN ({placeholders})
        )
        SELECT instrument_id::text, trade_date, close::float, rn
        FROM ranked
        WHERE rn <= 30
        ORDER BY instrument_id, rn
    """)).fetchall()

    by_inst: dict[str, list] = defaultdict(list)
    for row in rows:
        by_inst[row[0]].append({"trade_date": row[1], "close": row[2], "rn": row[3]})

    # Fetch 52-week high/low per instrument (separate query, efficient aggregate)
    w52_rows = db.execute(text(f"""
        SELECT instrument_id::text,
               MIN(close)::float AS low_52w,
               MAX(close)::float AS high_52w
        FROM price_bar_raw
        WHERE instrument_id IN ({placeholders})
          AND trade_date >= CURRENT_DATE - INTERVAL '365 days'
        GROUP BY instrument_id
    """)).fetchall()

    w52_map: dict[str, dict] = {}
    for row in w52_rows:
        w52_map[row[0]] = {"low": row[1], "high": row[2]}

    result = {}
    for iid in instrument_ids:
        bars = by_inst.get(iid, [])
        w52 = w52_map.get(iid, {})
        snap: dict = {
            "change_1d_pct": None,
            "change_5d_pct": None,
            "change_1m_pct": None,
            "latest_close": None,
            "latest_trade_date": None,
            "week52_high": w52.get("high"),
            "week52_low": w52.get("low"),
            "week52_pct": None,
        }
        if len(bars) >= 1:
            snap["latest_close"] = bars[0]["close"]
            snap["latest_trade_date"] = str(bars[0]["trade_date"])
            # 52-week range position: 0% = at low, 100% = at high
            high = w52.get("high")
            low = w52.get("low")
            if high is not None and low is not None and high > low:
                snap["week52_pct"] = round(
                    (bars[0]["close"] - low) / (high - low) * 100, 1
                )
        if len(bars) >= 2:
            snap["change_1d_pct"] = round(
                (bars[0]["close"] - bars[1]["close"]) / bars[1]["close"] * 100, 2
            )
        if len(bars) >= 6:
            snap["change_5d_pct"] = round(
                (bars[0]["close"] - bars[5]["close"]) / bars[5]["close"] * 100, 2
            )
        if len(bars) >= 22:
            snap["change_1m_pct"] = round(
                (bars[0]["close"] - bars[21]["close"]) / bars[21]["close"] * 100, 2
            )
        result[iid] = snap

    return result


@router.get("/snapshots")
def watchlist_snapshots(
    instrument_ids: str = Query(..., description="Comma-separated instrument UUIDs"),
    db: Session = Depends(get_sync_db),
):
    """Batch snapshot: 1D/5D/1M price change + research freshness.

    Layer 1 — Research-open: read-only data query, no execution impact.
    """
    from libs.db.models.ticker_history import TickerHistory
    from libs.portfolio.portfolio_service import get_research_status_batch

    # Parse & validate instrument IDs
    raw_ids = [s.strip() for s in instrument_ids.split(",") if s.strip()]
    valid_ids = []
    for iid in raw_ids:
        try:
            valid_ids.append(str(uuid.UUID(iid)))
        except (ValueError, AttributeError):
            pass
    if not valid_ids:
        return {"items": []}

    # Batch price snapshots
    price_snaps = _compute_price_snapshots(db, valid_ids)

    # Batch research status (reuse existing logic)
    research_status = get_research_status_batch(db, valid_ids)

    # Ticker lookup
    ticker_map = {}
    if valid_ids:
        uuid_objs = [uuid.UUID(v) for v in valid_ids]
        ticker_rows = (
            db.query(TickerHistory.instrument_id, TickerHistory.ticker)
            .filter(TickerHistory.instrument_id.in_(uuid_objs), TickerHistory.effective_to.is_(None))
            .all()
        )
        ticker_map = {str(row[0]): row[1] for row in ticker_rows}

    today = date.today()
    items = []
    for iid in valid_ids:
        ps = price_snaps.get(iid, {})
        rs = research_status.get(iid, {})
        last_note_at = rs.get("last_note_at")

        freshness_days = None
        if last_note_at:
            try:
                last_dt = datetime.fromisoformat(last_note_at)
                freshness_days = (today - last_dt.date()).days
            except (ValueError, TypeError):
                pass

        items.append({
            "instrument_id": iid,
            "ticker": ticker_map.get(iid),
            "change_1d_pct": ps.get("change_1d_pct"),
            "change_5d_pct": ps.get("change_5d_pct"),
            "change_1m_pct": ps.get("change_1m_pct"),
            "latest_close": ps.get("latest_close"),
            "latest_trade_date": ps.get("latest_trade_date"),
            "week52_high": ps.get("week52_high"),
            "week52_low": ps.get("week52_low"),
            "week52_pct": ps.get("week52_pct"),
            "research_freshness_days": freshness_days,
            "last_research_at": last_note_at,
        })

    return {"items": items}
