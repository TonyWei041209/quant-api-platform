"""Saved Presets API — reusable research configurations."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.db.models.saved_preset import SavedPreset

router = APIRouter()


class PresetCreate(BaseModel):
    name: str
    preset_type: str  # screener | event_study | backtest | research
    config: dict
    description: Optional[str] = None


class PresetUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    description: Optional[str] = None


@router.get("")
def list_presets(preset_type: Optional[str] = None, db: Session = Depends(get_sync_db)):
    q = db.query(SavedPreset)
    if preset_type:
        q = q.filter(SavedPreset.preset_type == preset_type)
    presets = q.order_by(SavedPreset.last_used_at.desc().nullslast(), SavedPreset.created_at.desc()).all()
    return {"items": [{
        "preset_id": str(p.preset_id),
        "name": p.name,
        "preset_type": p.preset_type,
        "config": p.config,
        "description": p.description,
        "use_count": p.use_count,
        "last_used_at": p.last_used_at.isoformat() if p.last_used_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
    } for p in presets], "total": len(presets)}


@router.post("")
def create_preset(body: PresetCreate, db: Session = Depends(get_sync_db)):
    p = SavedPreset(name=body.name, preset_type=body.preset_type, config=body.config, description=body.description)
    db.add(p)
    db.commit()
    db.refresh(p)
    return {"preset_id": str(p.preset_id), "name": p.name}


@router.put("/{preset_id}")
def update_preset(preset_id: str, body: PresetUpdate, db: Session = Depends(get_sync_db)):
    pid = uuid.UUID(preset_id)
    p = db.query(SavedPreset).filter(SavedPreset.preset_id == pid).first()
    if not p:
        raise HTTPException(404, "Preset not found")
    if body.name is not None:
        p.name = body.name
    if body.config is not None:
        p.config = body.config
    if body.description is not None:
        p.description = body.description
    db.commit()
    return {"updated": True}


@router.post("/{preset_id}/use")
def record_use(preset_id: str, db: Session = Depends(get_sync_db)):
    """Record that a preset was used (increments counter, updates last_used_at)."""
    pid = uuid.UUID(preset_id)
    p = db.query(SavedPreset).filter(SavedPreset.preset_id == pid).first()
    if not p:
        raise HTTPException(404, "Preset not found")
    p.use_count = (p.use_count or 0) + 1
    p.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return {"preset_id": str(p.preset_id), "use_count": p.use_count}


@router.delete("/{preset_id}")
def delete_preset(preset_id: str, db: Session = Depends(get_sync_db)):
    pid = uuid.UUID(preset_id)
    db.query(SavedPreset).filter(SavedPreset.preset_id == pid).delete()
    db.commit()
    return {"deleted": True}
