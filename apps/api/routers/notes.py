"""Research Notes API — lightweight thesis snapshots."""
from __future__ import annotations

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.db.models.research_note import ResearchNote
from libs.db.models.instrument import Instrument

router = APIRouter()


class NoteCreate(BaseModel):
    title: str
    content: str
    note_type: str = "general"
    instrument_id: Optional[str] = None
    tags: Optional[dict] = None
    context: Optional[dict] = None


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    note_type: Optional[str] = None
    tags: Optional[dict] = None


@router.get("")
def list_notes(
    instrument_id: Optional[str] = None,
    note_type: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_sync_db),
):
    q = db.query(ResearchNote)
    if instrument_id:
        q = q.filter(ResearchNote.instrument_id == uuid.UUID(instrument_id))
    if note_type:
        q = q.filter(ResearchNote.note_type == note_type)
    notes = q.order_by(ResearchNote.updated_at.desc()).limit(limit).all()
    # Resolve instrument names
    inst_ids = [n.instrument_id for n in notes if n.instrument_id]
    inst_map = {}
    if inst_ids:
        insts = db.query(Instrument).filter(Instrument.instrument_id.in_(inst_ids)).all()
        inst_map = {i.instrument_id: i.issuer_name_current for i in insts}
    return {"items": [{
        "note_id": str(n.note_id),
        "title": n.title,
        "content": n.content,
        "note_type": n.note_type,
        "instrument_id": str(n.instrument_id) if n.instrument_id else None,
        "instrument_name": inst_map.get(n.instrument_id) if n.instrument_id else None,
        "tags": n.tags,
        "context": n.context,
        "created_at": n.created_at.isoformat() if n.created_at else None,
        "updated_at": n.updated_at.isoformat() if n.updated_at else None,
    } for n in notes], "total": len(notes)}


@router.post("")
def create_note(body: NoteCreate, db: Session = Depends(get_sync_db)):
    n = ResearchNote(
        title=body.title,
        content=body.content,
        note_type=body.note_type,
        instrument_id=uuid.UUID(body.instrument_id) if body.instrument_id else None,
        tags=body.tags,
        context=body.context,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"note_id": str(n.note_id), "title": n.title}


@router.put("/{note_id}")
def update_note(note_id: str, body: NoteUpdate, db: Session = Depends(get_sync_db)):
    nid = uuid.UUID(note_id)
    n = db.query(ResearchNote).filter(ResearchNote.note_id == nid).first()
    if not n:
        raise HTTPException(404, "Note not found")
    if body.title is not None:
        n.title = body.title
    if body.content is not None:
        n.content = body.content
    if body.note_type is not None:
        n.note_type = body.note_type
    if body.tags is not None:
        n.tags = body.tags
    db.commit()
    return {"updated": True}


@router.delete("/{note_id}")
def delete_note(note_id: str, db: Session = Depends(get_sync_db)):
    nid = uuid.UUID(note_id)
    db.query(ResearchNote).filter(ResearchNote.note_id == nid).delete()
    db.commit()
    return {"deleted": True}
