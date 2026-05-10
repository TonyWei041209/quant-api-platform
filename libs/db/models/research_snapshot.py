"""Research snapshot tables — append-only history for scanner runs and
overnight market briefs.

These tables are RESEARCH-ONLY. They store the candidate sets and
metadata that the scanner / overnight brief surface to the user; they
never store order intents, order drafts, broker submissions, or any
executable trading instruction.

Side-effect attestations baked into the schema:
  * No `order_intent_id` / `order_draft_id` foreign keys
  * No `broker_*` foreign keys
  * No price/volume forecasts — only observed candidate metadata at
    capture time
  * No "buy / sell / target_price / position_size" columns
  * `schema_version` allows additive evolution of the JSON payload
    without destructive migrations later

The persistence is best-effort: the scanner / brief services always
return their full payload to the caller, and only attempt a snapshot
write inside an isolated try/except that swallows the error so a DB
hiccup never breaks the API. Persistence is also gated behind the
`FEATURE_RESEARCH_SNAPSHOT_WRITE` env flag so it can be turned off
fast if anything misbehaves.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from libs.db.base import Base
from libs.core.time import utc_now


# ---------------------------------------------------------------------------
# Scanner runs
# ---------------------------------------------------------------------------


class ScannerRun(Base):
    """One row per /scanner/stocks invocation that wrote a snapshot.

    Columns are deliberately conservative — anything that might evolve
    sits in `summary_json` so future schema changes are additive.
    """

    __tablename__ = "scanner_run"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # When the run was generated (server-clock UTC).
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=text("now()"),
        nullable=False,
    )
    # Universe scope keys: "scanner-research-36", "all-market", etc.
    universe: Mapped[str] = mapped_column(String(64), nullable=False)
    # How many instruments were considered.
    scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # How many rows ended up in the candidate snapshot.
    matched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Free-form sort key reported back to the caller.
    sort_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # The "as-of" data date the scanner used (string ISO date for simplicity).
    data_as_of: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Optional caller tag — "interactive", "overnight-job", "test", etc.
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="interactive",
    )
    # JSON payload (full provider_diagnostics + universe_scope).
    # `schema_version` lives inside the JSON so we can extend it later.
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
    )

    __table_args__ = (
        Index("ix_scanner_run_generated_at", "generated_at"),
        Index("ix_scanner_run_universe_generated_at",
              "universe", "generated_at"),
    )


class ScannerCandidateSnapshot(Base):
    """One row per (run, candidate). Append-only; never updated."""

    __tablename__ = "scanner_candidate_snapshot"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    # Logical foreign key to scanner_run.run_id (no DB-level FK to keep
    # the migration lean; an index covers the lookup pattern).
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    issuer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    signal_strength: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Candidate detail — scan_types, change_*, week52_position_pct,
    # volume_ratio, risk_flags, scanner explanation, etc. Anything new
    # the scanner adds in future versions slots in here without a
    # destructive migration.
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
    )

    __table_args__ = (
        Index("ix_scanner_candidate_run", "run_id", "rank"),
        Index("ix_scanner_candidate_ticker", "ticker"),
    )


# ---------------------------------------------------------------------------
# Market brief snapshots
# ---------------------------------------------------------------------------


class MarketBriefRun(Base):
    """One row per overnight brief invocation that wrote a snapshot.

    Stores the universe scope + provider diagnostics as JSON. The
    candidate detail lives in ``market_brief_candidate_snapshot``.
    """

    __tablename__ = "market_brief_run"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=text("now()"),
        nullable=False,
    )
    # "interactive" (user clicked refresh) or "overnight-job".
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="interactive",
    )
    # Total tickers in the merged universe.
    ticker_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    # News fan-out actually used (post-clamp).
    effective_news_top_n: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    # Days window argument.
    days_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Brief-level news section state — see overnight_brief_service.
    news_section_state: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
    )
    # Full universe_scope + provider_diagnostics + side_effects + disclaimer.
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
    )
    # Optional human notes from the operator (rarely populated; here for
    # forward-compat with rerun annotations).
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_market_brief_run_generated_at", "generated_at"),
        Index("ix_market_brief_run_source_generated_at",
              "source", "generated_at"),
    )


class MarketBriefCandidateSnapshot(Base):
    """One row per (brief_run, candidate). Append-only; never updated."""

    __tablename__ = "market_brief_candidate_snapshot"

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False,
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    company_name: Mapped[str | None] = mapped_column(
        String(256), nullable=True,
    )
    instrument_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    research_priority: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    mapping_status: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
    )
    # source_tags joined as a single comma-separated string for cheap
    # text indexing; the full tuple is also retained in payload_json.
    source_tags: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Full to_dict() output of the candidate row.
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True,
    )

    __table_args__ = (
        Index("ix_market_brief_candidate_run", "run_id", "rank"),
        Index("ix_market_brief_candidate_ticker", "ticker"),
    )
