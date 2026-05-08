"""Broker readonly API router — Trading 212 account/positions/orders.

Two surfaces:

  - Direct live readonly: /t212/account, /t212/positions, /t212/orders
    (legacy; calls T212 directly per request, no cache, no rate-limit gate)

  - Live read-through with cache + rate-limit awareness:
    /t212/live/positions, /t212/live/summary, /t212/live/status
    (the new near-real-time path used by the Dashboard, see
    `docs/t212-near-real-time-broker-truth-plan.md`)

This router NEVER calls a T212 write endpoint, NEVER places/cancels orders,
and NEVER touches order_intent / order_draft / submit objects.
FEATURE_T212_LIVE_SUBMIT remains false; this router does not check or
mutate it. Order placement still lives behind the controlled-execution
flow, which is unaffected by this file.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from libs.adapters.trading212_adapter import Trading212Adapter
from libs.core.config import get_settings
from libs.core.exceptions import RateLimitExceeded
from libs.core.logging import get_logger
from libs.portfolio.broker_live_cache import (
    LiveFetchResult,
    get_default_cache,
)

logger = get_logger(__name__)

router = APIRouter()

LIVE_SOURCE = "trading212_live_readonly"


def _get_adapter() -> Trading212Adapter:
    settings = get_settings()
    use_demo = bool(settings.t212_demo_base_url and not settings.t212_live_base_url)
    return Trading212Adapter(use_demo=use_demo)


def _is_configured() -> bool:
    settings = get_settings()
    return bool(settings.t212_api_key and settings.t212_api_secret)


def _extract_rate_limit(headers) -> dict[str, str] | None:
    """Pluck any x-ratelimit-* headers from a httpx response, lowercased."""
    if not headers:
        return None
    out: dict[str, str] = {}
    for name in (
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
    ):
        val = headers.get(name)
        if val is not None:
            out[name] = str(val)
    return out or None


# ---- Legacy direct endpoints (kept for the existing Execution page) ----

@router.get("/t212/account")
async def get_t212_account():
    """Get Trading 212 account summary (readonly, no cache)."""
    if not _is_configured():
        return {"error": "T212 not configured", "connected": False}
    adapter = _get_adapter()
    data = await adapter.get_account_summary()
    return {**data, "connected": True}


@router.get("/t212/positions")
async def get_t212_positions():
    """Get Trading 212 open positions (readonly, no cache)."""
    if not _is_configured():
        return []
    adapter = _get_adapter()
    raw = await adapter.get_positions()
    return [adapter.normalize_position(p) for p in raw]


@router.get("/t212/orders")
async def get_t212_orders(limit: int = Query(10, le=50)):
    """Get Trading 212 historical orders (readonly, no cache)."""
    if not _is_configured():
        return {"items": []}
    adapter = _get_adapter()
    raw = await adapter.get_orders(limit=limit)
    return {"items": [adapter.normalize_order(o) for o in raw]}


# ---- Live read-through endpoints (cached + rate-limit aware) ----


def _result_envelope(
    *,
    payload: Any,
    result: LiveFetchResult,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the JSON envelope returned to the frontend."""
    body: dict[str, Any] = {
        "source": LIVE_SOURCE,
        "live_fetched_at": result.fetched_at,
        "served_at": result.served_at,
        "provider_latency_ms": result.provider_latency_ms,
        "cache_status": result.cache_status,
        "stale_reason": result.stale_reason,
        "rate_limit": result.rate_limit,
    }
    if extra:
        body.update(extra)
    body["payload"] = payload
    return body


@router.get("/t212/live/positions")
async def live_positions():
    """Live (cache-served) Trading 212 positions for the Dashboard.

    Server-side TTL of ~2s honours the per-account rate limit
    (1 req/sec) while serving many concurrent dashboard tabs from one
    upstream call.
    """
    if not _is_configured():
        return {
            "source": LIVE_SOURCE,
            "cache_status": "error",
            "stale_reason": "T212 not configured",
            "live_fetched_at": None,
            "provider_latency_ms": None,
            "rate_limit": None,
            "payload": {"connected": False, "positions": [], "position_count": 0},
        }

    adapter = _get_adapter()

    async def _fetch() -> tuple[Any, dict[str, str] | None]:
        resp = await adapter.fetch("GET", "/equity/positions")
        raw = resp.json() if resp.json() is not None else []
        if not isinstance(raw, list):
            raw = []
        return raw, _extract_rate_limit(resp.headers)

    cache = get_default_cache()
    result = await cache.get_or_fetch(
        broker="trading212",
        account_id="default",
        endpoint="positions",
        fetcher=_fetch,
    )

    raw_positions = result.payload if isinstance(result.payload, list) else []
    normalized = [adapter.normalize_position(p) for p in raw_positions]
    payload = {
        "connected": True,
        "positions": normalized,
        "position_count": len(normalized),
    }
    return _result_envelope(payload=payload, result=result)


@router.get("/t212/live/summary")
async def live_summary():
    """Live (cache-served) Trading 212 account summary for the Dashboard.

    Cache TTL ~10s; this endpoint is cheap to poll alongside positions.
    """
    if not _is_configured():
        return {
            "source": LIVE_SOURCE,
            "cache_status": "error",
            "stale_reason": "T212 not configured",
            "live_fetched_at": None,
            "provider_latency_ms": None,
            "rate_limit": None,
            "payload": {"connected": False},
        }

    adapter = _get_adapter()

    async def _fetch() -> tuple[Any, dict[str, str] | None]:
        resp = await adapter.fetch("GET", "/equity/account/summary")
        raw = resp.json() or {}
        if not isinstance(raw, dict):
            raw = {}
        return raw, _extract_rate_limit(resp.headers)

    cache = get_default_cache()
    result = await cache.get_or_fetch(
        broker="trading212",
        account_id="default",
        endpoint="summary",
        fetcher=_fetch,
    )

    raw = result.payload if isinstance(result.payload, dict) else {}
    cash = raw.get("cash") if isinstance(raw.get("cash"), dict) else {}
    payload = {
        "connected": True,
        "account_id": str(raw.get("id")) if raw.get("id") is not None else None,
        "currency": raw.get("currency") or raw.get("currencyCode"),
        "portfolio_value": raw.get("totalValue") or raw.get("portfolio_value"),
        "cash_free": cash.get("free") if isinstance(cash, dict) else raw.get("free"),
        "cash_total": cash.get("total") if isinstance(cash, dict) else raw.get("total"),
        "cash_available_to_trade": (
            cash.get("availableToTrade") if isinstance(cash, dict) else None
        ),
    }
    return _result_envelope(payload=payload, result=result)


@router.get("/t212/live/status")
async def live_status():
    """Combined live broker-truth status for the Dashboard banner.

    Returns connectivity + most recent live and cache state. Always 200.
    Never raises; on configuration / network problems returns
    cache_status=\"error\" with a stale_reason explaining the issue.

    This endpoint does NOT trigger an upstream T212 call by itself —
    it inspects the cache only — so it is safe to poll at sub-second
    rates from many tabs.
    """
    cache = get_default_cache()
    if not _is_configured():
        return {
            "source": LIVE_SOURCE,
            "configured": False,
            "cache_status": "error",
            "stale_reason": "T212 not configured",
            "rate_limit": None,
            "endpoints": {},
        }

    snapshot: dict[str, Any] = {}
    for endpoint in ("positions", "summary"):
        entry = cache._cache.get(("trading212", "default", endpoint))  # noqa: SLF001
        if entry is None:
            snapshot[endpoint] = {
                "have_cached": False,
                "fetched_at": None,
                "rate_limit": None,
            }
        else:
            snapshot[endpoint] = {
                "have_cached": True,
                "fetched_at": entry.fetched_at,
                "rate_limit": dict(entry.rate_limit) if entry.rate_limit else None,
            }
    return {
        "source": LIVE_SOURCE,
        "configured": True,
        "endpoints": snapshot,
    }
