"""Read-only query layer over the persisted overnight-brief snapshots.

These functions never write to the DB and never call providers — they
just hydrate `MarketBriefRun` / `MarketBriefCandidateSnapshot` rows
into JSON-friendly dicts for the API/UI.

The shape mirrors the live brief output where it makes sense (so the
UI can reuse the same renderer) but adds two top-level fields:

  * ``run_id``   — the snapshot UUID
  * ``persisted`` — `true` (so the UI can label "from history")

The candidate arrays (``top_news_linked_candidates`` etc.) are
reconstructed from `MarketBriefCandidateSnapshot.payload_json` at read
time, mirroring the derivation rules in
``libs/market_brief/overnight_brief_service.py``.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from libs.db.models.research_snapshot import (
    MarketBriefCandidateSnapshot,
    MarketBriefRun,
)


def list_brief_runs(
    db: Session,
    *,
    limit: int = 10,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """Return the most recent brief runs (lightweight summary only)."""
    limit = max(1, min(int(limit), 100))
    stmt = select(MarketBriefRun).order_by(desc(MarketBriefRun.generated_at))
    if source:
        stmt = stmt.where(MarketBriefRun.source == str(source)[:32])
    stmt = stmt.limit(limit)
    rows = db.execute(stmt).scalars().all()
    return [_summarize_run(r) for r in rows]


def get_latest_brief(
    db: Session,
    *,
    source: str | None = None,
) -> dict[str, Any] | None:
    """Return the single most recent persisted brief, fully hydrated.

    Returns None when no brief has ever been persisted.
    """
    stmt = select(MarketBriefRun).order_by(desc(MarketBriefRun.generated_at))
    if source:
        stmt = stmt.where(MarketBriefRun.source == str(source)[:32])
    stmt = stmt.limit(1)
    row = db.execute(stmt).scalar_one_or_none()
    if row is None:
        return None
    return _hydrate_run(db, row)


def get_brief_by_id(
    db: Session,
    run_id: str | uuid.UUID,
) -> dict[str, Any] | None:
    """Return a single persisted brief by run_id."""
    rid = _to_uuid(run_id)
    if rid is None:
        return None
    row = db.get(MarketBriefRun, rid)
    if row is None:
        return None
    return _hydrate_run(db, row)


# ---------------------------------------------------------------------------
# Internal hydration
# ---------------------------------------------------------------------------


def _summarize_run(row: MarketBriefRun) -> dict[str, Any]:
    return {
        "run_id": str(row.run_id),
        "generated_at": (row.generated_at.isoformat()
                         if row.generated_at else None),
        "source": row.source,
        "ticker_count": int(row.ticker_count or 0),
        "effective_news_top_n": row.effective_news_top_n,
        "days_window": row.days_window,
        "news_section_state": row.news_section_state,
    }


def _hydrate_run(db: Session, run: MarketBriefRun) -> dict[str, Any]:
    """Rebuild a brief-shaped payload from a persisted run + candidates."""
    cand_rows = db.execute(
        select(MarketBriefCandidateSnapshot)
        .where(MarketBriefCandidateSnapshot.run_id == run.run_id)
        .order_by(MarketBriefCandidateSnapshot.rank.asc())
    ).scalars().all()

    candidates: list[dict[str, Any]] = []
    for cr in cand_rows:
        # Prefer the full payload_json; fall back to a minimal record
        # if it's missing.
        if cr.payload_json:
            candidates.append(dict(cr.payload_json))
        else:
            candidates.append({
                "ticker": cr.ticker,
                "company_name": cr.company_name,
                "instrument_id": (str(cr.instrument_id)
                                  if cr.instrument_id else None),
                "research_priority": cr.research_priority,
                "mapping_status": cr.mapping_status,
                "source_tags": (cr.source_tags.split(",")
                                if cr.source_tags else []),
                "explanation": "",
            })

    # Derive the same top-N sections the live brief produces, using the
    # same sort keys defined in libs/market_brief/overnight_brief_service.py.
    top_price_anomaly = sorted(
        [c for c in candidates if "SCANNER" in (c.get("source_tags") or [])],
        key=lambda r: (
            -(r.get("research_priority") or 0),
            -(abs((r.get("price_move") or {}).get("change_1d_pct") or 0)),
            r.get("ticker") or "",
        ),
    )[:10]
    top_news_linked = sorted(
        [c for c in candidates if c.get("recent_news")],
        key=lambda r: (
            -(r.get("research_priority") or 0),
            -len(r.get("recent_news") or []),
            r.get("ticker") or "",
        ),
    )[:10]
    earnings_nearby = sorted(
        [c for c in candidates if c.get("upcoming_earnings")],
        key=lambda r: (
            -(r.get("research_priority") or 0),
            r.get("ticker") or "",
        ),
    )[:10]
    unmapped = sorted(
        [c for c in candidates
         if c.get("mapping_status") in ("unmapped", "unresolved", "newly_resolvable")],
        key=lambda r: (
            0 if r.get("mapping_status") == "newly_resolvable" else 1,
            r.get("ticker") or "",
        ),
    )[:20]

    # Categories summary — recompute from candidate taxonomy.
    cat_buckets: dict[str, dict[str, Any]] = {}
    for c in candidates:
        broad = (c.get("taxonomy") or {}).get("broad") or "Uncategorized"
        bucket = cat_buckets.setdefault(broad, {
            "broad": broad,
            "ticker_count": 0,
            "tickers": [],
            "subs": {},
        })
        bucket["ticker_count"] += 1
        if len(bucket["tickers"]) < 10:
            bucket["tickers"].append(c.get("ticker"))
        for sub in (c.get("taxonomy") or {}).get("subs", []):
            bucket["subs"][sub] = bucket["subs"].get(sub, 0) + 1
    categories_summary = sorted(
        cat_buckets.values(),
        key=lambda b: (-b["ticker_count"], b["broad"]),
    )

    summary = dict(run.summary_json or {})

    return {
        "run_id": str(run.run_id),
        "persisted": True,
        "generated_at": (run.generated_at.isoformat()
                         if run.generated_at else None),
        "source": run.source,
        "universe_scope": summary.get("universe_scope", {}),
        "ticker_count": int(run.ticker_count or 0),
        "candidates": candidates,
        "top_price_anomaly_candidates": top_price_anomaly,
        "top_news_linked_candidates": top_news_linked,
        "earnings_nearby_candidates": earnings_nearby,
        "unmapped_candidates": unmapped,
        "categories_summary": categories_summary,
        "provider_diagnostics": summary.get("provider_diagnostics", {}),
        "side_effects": summary.get("side_effects", {
            "db_writes": "NONE",
            "broker_writes": "NONE",
            "execution_objects": "NONE",
            "live_submit": "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)",
            "scheduler_changes": "NONE",
        }),
        "disclaimer": summary.get(
            "disclaimer",
            "Research events only. Independent validation required.",
        ),
        "schema_version": summary.get("schema_version"),
    }


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None
