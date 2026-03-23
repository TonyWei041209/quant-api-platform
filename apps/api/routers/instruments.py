"""Instrument endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.db.models.instrument import Instrument
from libs.db.models.identifier import InstrumentIdentifier
from libs.db.models.ticker_history import TickerHistory

router = APIRouter()


@router.get("")
def list_instruments(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_sync_db),
) -> dict:
    instruments = db.query(Instrument).offset(skip).limit(limit).all()
    total = db.query(Instrument).count()
    return {
        "total": total,
        "items": [
            {
                "instrument_id": str(i.instrument_id),
                "asset_type": i.asset_type,
                "issuer_name_current": i.issuer_name_current,
                "exchange_primary": i.exchange_primary,
                "currency": i.currency,
                "is_active": i.is_active,
            }
            for i in instruments
        ],
    }


@router.get("/{instrument_id}")
def get_instrument(instrument_id: str, db: Session = Depends(get_sync_db)) -> dict:
    try:
        iid = uuid.UUID(instrument_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")

    inst = db.get(Instrument, iid)
    if not inst:
        raise HTTPException(status_code=404, detail="Instrument not found")

    identifiers = db.query(InstrumentIdentifier).filter_by(instrument_id=iid).all()
    ticker_hist = db.query(TickerHistory).filter_by(instrument_id=iid).all()

    return {
        "instrument_id": str(inst.instrument_id),
        "asset_type": inst.asset_type,
        "issuer_name_current": inst.issuer_name_current,
        "exchange_primary": inst.exchange_primary,
        "currency": inst.currency,
        "is_active": inst.is_active,
        "identifiers": [
            {"id_type": x.id_type, "id_value": x.id_value, "source": x.source,
             "valid_from": str(x.valid_from), "valid_to": str(x.valid_to) if x.valid_to else None}
            for x in identifiers
        ],
        "ticker_history": [
            {"ticker": x.ticker, "issuer_name": x.issuer_name, "exchange": x.exchange,
             "effective_from": str(x.effective_from), "effective_to": str(x.effective_to) if x.effective_to else None}
            for x in ticker_hist
        ],
    }
