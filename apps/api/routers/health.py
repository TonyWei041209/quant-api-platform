"""Health check endpoint."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "quant-api-platform", "version": "0.1.0"}
