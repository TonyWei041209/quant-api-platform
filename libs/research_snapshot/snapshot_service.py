"""Research snapshot persistence — service layer.

Append-only writes to the four research snapshot tables. Every public
function:

  * obeys the ``FEATURE_RESEARCH_SNAPSHOT_WRITE`` env flag
  * never raises — failures are caught, logged, and reported as a
    structured ``PersistenceResult`` the caller can attach to its
    response if it wants
  * never writes to broker_*, order_*, instrument_*, watchlist_*,
    saved_preset, research_note, or any other pre-existing table
  * never invokes any Trading 212 endpoint
  * never reads or mutates ``FEATURE_T212_LIVE_SUBMIT``

The service is intentionally thin: it accepts the dict that the
scanner or brief already produces and stores it (plus a couple of
denormalized index columns) without any transformation that could
silently drop fields.
"""
from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from sqlalchemy.orm import Session

from libs.core.time import utc_now
from libs.db.models.research_snapshot import (
    MarketBriefCandidateSnapshot,
    MarketBriefRun,
    ScannerCandidateSnapshot,
    ScannerRun,
)


logger = logging.getLogger(__name__)


# Schema version surfaced to the snapshot JSON payloads. Bump only when
# the JSON shape changes in a way downstream consumers should detect.
SCHEMA_VERSION = "1.0"

# Env flag — set to "false" to disable all snapshot writes without a
# code deploy.
_FEATURE_FLAG_NAME = "FEATURE_RESEARCH_SNAPSHOT_WRITE"


def is_snapshot_write_enabled() -> bool:
    """True unless the env flag is explicitly set to a falsy value.

    Default is enabled — the persistence is best-effort and isolated,
    so the safe default is to record history.
    """
    raw = os.environ.get(_FEATURE_FLAG_NAME, "true").strip().lower()
    return raw not in ("false", "0", "no", "off", "")


@dataclass
class PersistenceResult:
    """Structured outcome the caller can attach to its response.

    ``ok`` is True when the snapshot was written successfully OR when
    persistence was skipped via the feature flag (this is a
    deliberate behaviour: a disabled flag is not a failure).
    """

    ok: bool
    skipped: bool = False
    run_id: uuid.UUID | None = None
    rows_written: int = 0
    error: str | None = None
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "ok": self.ok,
            "skipped": self.skipped,
            "rows_written": self.rows_written,
        }
        if self.run_id is not None:
            d["run_id"] = str(self.run_id)
        if self.error is not None:
            d["error"] = self.error
        if self.note is not None:
            d["note"] = self.note
        return d


# ---------------------------------------------------------------------------
# Scanner snapshot
# ---------------------------------------------------------------------------


def persist_scanner_snapshot(
    db: Session,
    scanner_response: dict[str, Any],
    *,
    universe: str,
    sort_by: str | None = None,
    source: str = "interactive",
) -> PersistenceResult:
    """Persist a single scanner result.

    Best-effort: if the write fails for any reason, the exception is
    swallowed, logged, and reported in the returned PersistenceResult.
    The caller is expected to ignore the failure (or surface it as a
    diagnostic flag in its response).
    """
    if not is_snapshot_write_enabled():
        return PersistenceResult(ok=True, skipped=True, note="feature flag off")

    try:
        items = list(scanner_response.get("items") or [])
        run_id = uuid.uuid4()
        run = ScannerRun(
            run_id=run_id,
            generated_at=_parse_iso(scanner_response.get("as_of")) or utc_now(),
            universe=str(universe)[:64],
            scanned=int(scanner_response.get("scanned") or 0),
            matched=int(scanner_response.get("matched") or len(items)),
            sort_by=(str(sort_by)[:32] if sort_by else None),
            data_as_of=(str(scanner_response.get("as_of"))[:16]
                        if scanner_response.get("as_of") else None),
            source=str(source)[:32],
            summary_json=_strip_items(scanner_response, schema_version=SCHEMA_VERSION),
        )
        db.add(run)

        rows = 0
        for rank, raw in enumerate(items, start=1):
            if not isinstance(raw, dict):
                continue
            ticker = str(raw.get("ticker") or "").upper()[:16]
            if not ticker:
                continue
            db.add(ScannerCandidateSnapshot(
                snapshot_id=uuid.uuid4(),
                run_id=run_id,
                rank=rank,
                ticker=ticker,
                instrument_id=_to_uuid_or_none(raw.get("instrument_id")),
                issuer_name=(str(raw.get("issuer_name"))[:256]
                             if raw.get("issuer_name") else None),
                signal_strength=(str(raw.get("signal_strength"))[:16]
                                 if raw.get("signal_strength") else None),
                payload_json=raw,
            ))
            rows += 1

        db.commit()
        return PersistenceResult(ok=True, run_id=run_id, rows_written=rows + 1)
    except Exception as exc:  # noqa: BLE001 — best-effort isolation
        logger.warning(
            "scanner snapshot persistence failed: %s",
            type(exc).__name__,
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return PersistenceResult(
            ok=False,
            error=f"{type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# Market brief snapshot
# ---------------------------------------------------------------------------


def persist_market_brief_snapshot(
    db: Session,
    brief_response: dict[str, Any],
    *,
    source: str = "interactive",
) -> PersistenceResult:
    """Persist a single overnight-brief result.

    Same isolation contract as ``persist_scanner_snapshot``.
    """
    if not is_snapshot_write_enabled():
        return PersistenceResult(ok=True, skipped=True, note="feature flag off")

    try:
        run_id = uuid.uuid4()
        scope = brief_response.get("universe_scope") or {}
        diag = brief_response.get("provider_diagnostics") or {}
        news = (diag.get("news") or {}) if isinstance(diag, dict) else {}

        run = MarketBriefRun(
            run_id=run_id,
            generated_at=_parse_iso(brief_response.get("generated_at"))
            or utc_now(),
            source=str(source)[:32],
            ticker_count=int(brief_response.get("ticker_count") or 0),
            effective_news_top_n=_int_or_none(scope.get("effective_news_top_n")),
            days_window=_int_or_none(scope.get("days_window")),
            news_section_state=(str(news.get("section_state"))[:32]
                                if news.get("section_state") else None),
            summary_json=_strip_lists(brief_response, schema_version=SCHEMA_VERSION),
        )
        db.add(run)

        rows = 0
        # Persist the FULL `candidates` list, not just the derived top-N
        # sections — derivation can be re-done at read time.
        candidates = list(brief_response.get("candidates") or [])
        for rank, c in enumerate(candidates, start=1):
            if not isinstance(c, dict):
                continue
            ticker = str(c.get("ticker") or "").upper()[:16]
            if not ticker:
                continue
            tags = c.get("source_tags") or []
            tags_str = ",".join(str(t) for t in tags if t)[:128]
            db.add(MarketBriefCandidateSnapshot(
                snapshot_id=uuid.uuid4(),
                run_id=run_id,
                rank=rank,
                ticker=ticker,
                company_name=(str(c.get("company_name"))[:256]
                              if c.get("company_name") else None),
                instrument_id=_to_uuid_or_none(c.get("instrument_id")),
                research_priority=_int_or_none(c.get("research_priority")),
                mapping_status=(str(c.get("mapping_status"))[:32]
                                if c.get("mapping_status") else None),
                source_tags=tags_str if tags_str else None,
                payload_json=c,
            ))
            rows += 1

        db.commit()
        return PersistenceResult(ok=True, run_id=run_id, rows_written=rows + 1)
    except Exception as exc:  # noqa: BLE001 — best-effort isolation
        logger.warning(
            "market brief snapshot persistence failed: %s",
            type(exc).__name__,
        )
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return PersistenceResult(
            ok=False,
            error=f"{type(exc).__name__}",
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _strip_items(d: dict[str, Any], *, schema_version: str) -> dict[str, Any]:
    """Drop the bulky `items` list; per-candidate detail goes to
    scanner_candidate_snapshot rows instead."""
    out = {k: v for k, v in d.items() if k != "items"}
    out["schema_version"] = schema_version
    return out


def _strip_lists(d: dict[str, Any], *, schema_version: str) -> dict[str, Any]:
    """Same idea for the brief: keep universe_scope, provider_diagnostics,
    side_effects, disclaimer, etc. but drop the per-candidate arrays
    that bloat the JSON column."""
    drop_keys = {
        "candidates",
        "top_price_anomaly_candidates",
        "top_news_linked_candidates",
        "earnings_nearby_candidates",
        "unmapped_candidates",
    }
    out = {k: v for k, v in d.items() if k not in drop_keys}
    out["schema_version"] = schema_version
    return out


def _to_uuid_or_none(value: Any) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _parse_iso(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value)
    # Strip trailing 'Z' which datetime.fromisoformat rejects on <3.11.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None
