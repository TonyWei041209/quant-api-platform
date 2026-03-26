"""Broker readonly API router — Trading 212 account/positions/orders."""
from __future__ import annotations

import asyncio
from fastapi import APIRouter, Query

from libs.adapters.trading212_adapter import Trading212Adapter
from libs.core.config import get_settings

router = APIRouter()


def _get_adapter() -> Trading212Adapter:
    settings = get_settings()
    use_demo = bool(settings.t212_demo_base_url and not settings.t212_live_base_url)
    return Trading212Adapter(use_demo=use_demo)


def _is_configured() -> bool:
    settings = get_settings()
    return bool(settings.t212_api_key and settings.t212_api_secret)


@router.get("/t212/account")
async def get_t212_account():
    """Get Trading 212 account summary (readonly)."""
    if not _is_configured():
        return {"error": "T212 not configured", "connected": False}
    adapter = _get_adapter()
    data = await adapter.get_account_summary()
    return {**data, "connected": True}


@router.get("/t212/positions")
async def get_t212_positions():
    """Get Trading 212 open positions (readonly)."""
    if not _is_configured():
        return []
    adapter = _get_adapter()
    raw = await adapter.get_positions()
    return [adapter.normalize_position(p) for p in raw]


@router.get("/t212/orders")
async def get_t212_orders(limit: int = Query(10, le=50)):
    """Get Trading 212 historical orders (readonly)."""
    if not _is_configured():
        return {"items": []}
    adapter = _get_adapter()
    raw = await adapter.get_orders(limit=limit)
    return {"items": [adapter.normalize_order(o) for o in raw]}
