"""add research snapshot tables (scanner_run + market_brief_run + per-candidate)

Adds four append-only research-only tables:

  * scanner_run                       (one row per scanner snapshot)
  * scanner_candidate_snapshot        (one row per (run, candidate))
  * market_brief_run                  (one row per overnight brief snapshot)
  * market_brief_candidate_snapshot   (one row per (brief_run, candidate))

These tables are RESEARCH-ONLY:
  * No order_intent / order_draft / broker / submit foreign keys
  * No buy/sell/target_price/position_size columns
  * Schema_version lives inside the JSONB payload so future evolution
    is additive
  * All four tables are append-only — the persistence service NEVER
    issues UPDATE / DELETE against them.

The migration is purely additive (CREATE TABLE + CREATE INDEX). It
does not touch any pre-existing table, does not alter any constraint,
does not delete or rename any column, and does not modify any
broker_* / order_* / instrument_* table.

Revision ID: c1d4e7f8a902
Revises: b8a3f2d91e47
Create Date: 2026-05-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c1d4e7f8a902"
down_revision: Union[str, None] = "b8a3f2d91e47"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- scanner_run --------------------------------------------------
    op.create_table(
        "scanner_run",
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("universe", sa.String(64), nullable=False),
        sa.Column("scanned", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("matched", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("sort_by", sa.String(32), nullable=True),
        sa.Column("data_as_of", sa.String(16), nullable=True),
        sa.Column("source", sa.String(32), nullable=False,
                  server_default=sa.text("'interactive'")),
        sa.Column("summary_json", postgresql.JSONB, nullable=True),
    )
    op.create_index(
        "ix_scanner_run_generated_at",
        "scanner_run", ["generated_at"],
    )
    op.create_index(
        "ix_scanner_run_universe_generated_at",
        "scanner_run", ["universe", "generated_at"],
    )

    # --- scanner_candidate_snapshot -----------------------------------
    op.create_table(
        "scanner_candidate_snapshot",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True),
                  nullable=True),
        sa.Column("issuer_name", sa.String(256), nullable=True),
        sa.Column("signal_strength", sa.String(16), nullable=True),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
    )
    op.create_index(
        "ix_scanner_candidate_run",
        "scanner_candidate_snapshot", ["run_id", "rank"],
    )
    op.create_index(
        "ix_scanner_candidate_ticker",
        "scanner_candidate_snapshot", ["ticker"],
    )

    # --- market_brief_run --------------------------------------------
    op.create_table(
        "market_brief_run",
        sa.Column("run_id", postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True),
                  nullable=False, server_default=sa.text("now()")),
        sa.Column("source", sa.String(32), nullable=False,
                  server_default=sa.text("'interactive'")),
        sa.Column("ticker_count", sa.Integer, nullable=False,
                  server_default=sa.text("0")),
        sa.Column("effective_news_top_n", sa.Integer, nullable=True),
        sa.Column("days_window", sa.Integer, nullable=True),
        sa.Column("news_section_state", sa.String(32), nullable=True),
        sa.Column("summary_json", postgresql.JSONB, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_market_brief_run_generated_at",
        "market_brief_run", ["generated_at"],
    )
    op.create_index(
        "ix_market_brief_run_source_generated_at",
        "market_brief_run", ["source", "generated_at"],
    )

    # --- market_brief_candidate_snapshot ------------------------------
    op.create_table(
        "market_brief_candidate_snapshot",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True),
                  primary_key=True, nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("company_name", sa.String(256), nullable=True),
        sa.Column("instrument_id", postgresql.UUID(as_uuid=True),
                  nullable=True),
        sa.Column("research_priority", sa.Integer, nullable=True),
        sa.Column("mapping_status", sa.String(32), nullable=True),
        sa.Column("source_tags", sa.String(128), nullable=True),
        sa.Column("payload_json", postgresql.JSONB, nullable=True),
    )
    op.create_index(
        "ix_market_brief_candidate_run",
        "market_brief_candidate_snapshot", ["run_id", "rank"],
    )
    op.create_index(
        "ix_market_brief_candidate_ticker",
        "market_brief_candidate_snapshot", ["ticker"],
    )


def downgrade() -> None:
    # Drop in reverse dependency order (none of these tables have FKs,
    # but match the create order in reverse for tidiness).
    op.drop_index(
        "ix_market_brief_candidate_ticker",
        table_name="market_brief_candidate_snapshot",
    )
    op.drop_index(
        "ix_market_brief_candidate_run",
        table_name="market_brief_candidate_snapshot",
    )
    op.drop_table("market_brief_candidate_snapshot")

    op.drop_index(
        "ix_market_brief_run_source_generated_at",
        table_name="market_brief_run",
    )
    op.drop_index(
        "ix_market_brief_run_generated_at",
        table_name="market_brief_run",
    )
    op.drop_table("market_brief_run")

    op.drop_index(
        "ix_scanner_candidate_ticker",
        table_name="scanner_candidate_snapshot",
    )
    op.drop_index(
        "ix_scanner_candidate_run",
        table_name="scanner_candidate_snapshot",
    )
    op.drop_table("scanner_candidate_snapshot")

    op.drop_index(
        "ix_scanner_run_universe_generated_at", table_name="scanner_run",
    )
    op.drop_index(
        "ix_scanner_run_generated_at", table_name="scanner_run",
    )
    op.drop_table("scanner_run")
