"""Taxonomy scanner read-only API.

Routes:

  GET  /api/scanner/taxonomy/categories        — broad + subcategory list
  GET  /api/scanner/taxonomy/universe-preview  — sampled tickers per category
  GET  /api/scanner/provider-capabilities      — provider feature gate flags
  GET  /api/scanner/all-market/preview         — light read-only preview;
                                                 full all-market scan is
                                                 ``job_required=true``

All routes are read-only. No production write. No T212 write. No
broker write. No order/execution objects. Research-only language.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.scanner import market_taxonomy as tax


router = APIRouter()

ALL_MARKET_PREVIEW_DEFAULT = 100
ALL_MARKET_PREVIEW_CEILING = 1000


@router.get("/taxonomy/categories")
def get_categories():
    return {
        "broad_categories": list(tax.BROAD_CATEGORIES),
        "subcategories": list(tax.SUBCATEGORIES),
        "language_policy": (
            "Research candidate scanner. Outputs are research candidates "
            "only and require independent validation. No trading "
            "instruction is implied."
        ),
    }


@router.get("/taxonomy/universe-preview")
def universe_preview(
    broad: Optional[str] = Query(None),
    sub: Optional[str] = Query(None),
    db: Session = Depends(get_sync_db),
):
    """Preview tickers from the static theme map matching the filter.

    Read-only: walks the in-memory static theme map only — does NOT
    issue any provider call and does NOT touch broker_*_snapshot or
    instrument tables. The `db` dependency is included so future work
    can mix in the user's Trading 212 Mirror without API change; it is
    not used in this preview.
    """
    items: list[dict] = []
    for ticker, entry in tax._STATIC_THEMES.items():
        item_broad = entry.get("broad")
        item_subs = tuple(entry.get("subs") or ())
        items.append({
            "display_ticker": ticker,
            "taxonomy_tags": {"broad": item_broad, "subs": list(item_subs)},
        })
    filtered = tax.filter_universe_by_categories(
        items,
        broad_categories=[broad] if broad else None,
        subcategories=[sub] if sub else None,
    )
    return {
        "broad": broad,
        "subcategory": sub,
        "count": len(filtered),
        "items": filtered,
        "source": "static_theme_map",
        "note": (
            "Static theme map only — full provider classification is "
            "applied during the all-market scan. No provider HTTP call."
        ),
    }


@router.get("/provider-capabilities")
def provider_capabilities():
    """Report which provider features are configured.

    Used by the frontend to decide whether to gate the all-market scan
    button vs. show a "set up provider key" hint. Read-only check on
    the `Settings` object only — no provider HTTP call.
    """
    from libs.core.config import get_settings
    s = get_settings()
    fmp_configured = bool(getattr(s, "fmp_api_key", None))
    massive_configured = bool(getattr(s, "massive_api_key", None))
    return {
        "fmp": {
            "configured": fmp_configured,
            "supports_earnings_calendar": fmp_configured,
            "supports_news": fmp_configured,  # actual access varies by plan
            "supports_profile": fmp_configured,
        },
        "massive_polygon": {
            "configured": massive_configured,
            "supports_eod_bars": massive_configured,
            "supports_news": False,
            "supports_earnings": False,
        },
        "all_market_scan_ready": fmp_configured,
    }


@router.get("/all-market/preview")
def all_market_preview(
    limit: int = Query(ALL_MARKET_PREVIEW_DEFAULT, ge=10, le=ALL_MARKET_PREVIEW_CEILING),
    broad: Optional[str] = Query(None),
    sub: Optional[str] = Query(None),
):
    """Light all-market preview from the static theme map.

    The full all-market scan requires a one-shot Cloud Run Job and is
    NOT executed by this endpoint. Returns ``job_required=true`` and
    a clear explanation when limit > ALL_MARKET_PREVIEW_CEILING is
    requested or when the result would otherwise be unbounded.
    """
    items: list[dict] = []
    for ticker, entry in tax._STATIC_THEMES.items():
        items.append({
            "display_ticker": ticker,
            "taxonomy_tags": {
                "broad": entry.get("broad"),
                "subs": list(entry.get("subs") or ()),
            },
        })
    filtered = tax.filter_universe_by_categories(
        items,
        broad_categories=[broad] if broad else None,
        subcategories=[sub] if sub else None,
    )
    truncated = filtered[:limit]
    # Bounded planning estimates so the UI / operator can decide
    # whether a one-shot Cloud Run Job is worth scheduling.
    # `estimated_symbol_count` is the full count after filter (no cap).
    # `provider_call_estimate` is a conservative upper bound: one
    # /profile call per ticker (cached at the provider layer in
    # production; this is the worst-case fresh-fetch scenario).
    estimated_symbol_count = len(filtered)
    provider_call_estimate = estimated_symbol_count  # 1 :: 1 profile fetch
    return {
        "broad": broad,
        "subcategory": sub,
        "limit": limit,
        "max_symbols": ALL_MARKET_PREVIEW_CEILING,
        "preview_count": len(truncated),
        "total_known_in_taxonomy": estimated_symbol_count,
        "estimated_symbol_count": estimated_symbol_count,
        "provider_call_estimate": provider_call_estimate,
        "requires_overnight_job": True,
        "items": truncated,
        "job_required": True,  # legacy alias
        "language_policy": (
            "Research candidates only. Full-market scanning would use "
            "provider bulk/grouped data and runs best overnight. "
            "Results are research candidates, not trading instructions."
        ),
        "source": "static_theme_map_preview",
    }
