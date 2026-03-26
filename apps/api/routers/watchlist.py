"""Watchlist API — manage daily focus universe."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
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

    gid = uuid.UUID(group_id)
    items = (
        db.query(WatchlistItem, Instrument)
        .join(Instrument, WatchlistItem.instrument_id == Instrument.instrument_id)
        .filter(WatchlistItem.group_id == gid)
        .order_by(WatchlistItem.added_at.desc())
        .all()
    )
    result = []
    for wi, inst in items:
        result.append({
            "item_id": str(wi.item_id),
            "instrument_id": str(wi.instrument_id),
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
