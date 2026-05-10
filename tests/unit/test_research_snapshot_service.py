"""Research snapshot persistence — unit tests.

All tests are hermetic: they use an in-memory SQLite engine and the
schema-equivalent table DDL declared by the SQLAlchemy models. No
Postgres, no Cloud SQL, no real provider HTTP, no T212.

Coverage:
  * scanner snapshot inserts the run + per-candidate rows
  * brief snapshot inserts the run + per-candidate rows
  * payload_json keeps the original dict
  * `items` and per-candidate arrays are NOT duplicated in summary_json
  * schema_version is recorded
  * feature flag off → skip with ok=True, skipped=True
  * persistence failure (broken db) → ok=False, error set, no raise
  * source-grep guards on the service module
"""
from __future__ import annotations

import inspect
import io
import os
import tokenize
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from libs.db.base import Base
from libs.db.models import (
    MarketBriefCandidateSnapshot,
    MarketBriefRun,
    ScannerCandidateSnapshot,
    ScannerRun,
)
from libs.research_snapshot import snapshot_service as svc


# Teach SQLite (used only in unit tests) to render Postgres-only column
# types so we can spin up a hermetic in-memory schema. Production uses
# real Postgres.
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "VARCHAR(36)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def in_memory_db():
    """Build a fresh SQLite-backed Session per test.

    Creates ONLY the four research snapshot tables (not the full
    Base.metadata) so SQLite isn't asked to render Postgres-specific
    types from unrelated tables.
    """
    engine = create_engine("sqlite:///:memory:", future=True)
    snapshot_tables = [
        ScannerRun.__table__,
        ScannerCandidateSnapshot.__table__,
        MarketBriefRun.__table__,
        MarketBriefCandidateSnapshot.__table__,
    ]
    Base.metadata.create_all(engine, tables=snapshot_tables)
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _ensure_flag_default(monkeypatch):
    """Default the feature flag ON for tests; individual tests can flip
    it back off."""
    monkeypatch.setenv("FEATURE_RESEARCH_SNAPSHOT_WRITE", "true")


def _strip(src: str) -> str:
    out: list[str] = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    return "".join(out)


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_default_enabled(self, monkeypatch):
        monkeypatch.delenv("FEATURE_RESEARCH_SNAPSHOT_WRITE", raising=False)
        assert svc.is_snapshot_write_enabled() is True

    @pytest.mark.parametrize("val", ["false", "0", "no", "off", "FALSE", "Off"])
    def test_disabled_values(self, monkeypatch, val):
        monkeypatch.setenv("FEATURE_RESEARCH_SNAPSHOT_WRITE", val)
        assert svc.is_snapshot_write_enabled() is False

    @pytest.mark.parametrize("val", ["true", "1", "yes", "on", "anything-else"])
    def test_enabled_values(self, monkeypatch, val):
        monkeypatch.setenv("FEATURE_RESEARCH_SNAPSHOT_WRITE", val)
        assert svc.is_snapshot_write_enabled() is True

    def test_disabled_skips_scanner_write(self, monkeypatch, in_memory_db):
        monkeypatch.setenv("FEATURE_RESEARCH_SNAPSHOT_WRITE", "false")
        result = svc.persist_scanner_snapshot(
            in_memory_db,
            {"items": [{"ticker": "X", "instrument_id": str(uuid.uuid4())}],
             "scanned": 1, "matched": 1, "as_of": "2026-05-09"},
            universe="all", sort_by="signal_strength",
        )
        assert result.ok is True
        assert result.skipped is True
        assert in_memory_db.query(ScannerRun).count() == 0
        assert in_memory_db.query(ScannerCandidateSnapshot).count() == 0

    def test_disabled_skips_brief_write(self, monkeypatch, in_memory_db):
        monkeypatch.setenv("FEATURE_RESEARCH_SNAPSHOT_WRITE", "false")
        result = svc.persist_market_brief_snapshot(
            in_memory_db,
            {"ticker_count": 0, "candidates": []},
        )
        assert result.ok is True
        assert result.skipped is True
        assert in_memory_db.query(MarketBriefRun).count() == 0


# ---------------------------------------------------------------------------
# Scanner snapshot writes
# ---------------------------------------------------------------------------


class TestScannerSnapshot:
    def test_basic_insert(self, in_memory_db):
        items = [
            {"ticker": "NVDA", "instrument_id": str(uuid.uuid4()),
             "issuer_name": "NVIDIA", "signal_strength": "high",
             "scan_types": ["strong_momentum"], "change_1d_pct": 2.1,
             "explanation": "x", "risk_flags": [],
             "data_mode": "daily_eod", "as_of": "2026-05-09"},
            {"ticker": "MU", "instrument_id": str(uuid.uuid4()),
             "issuer_name": "Micron", "signal_strength": "medium",
             "scan_types": ["range_break"], "change_1d_pct": 1.0,
             "explanation": "x", "risk_flags": [],
             "data_mode": "daily_eod", "as_of": "2026-05-09"},
        ]
        response = {
            "items": items, "as_of": "2026-05-09", "data_mode": "daily_eod",
            "universe": "all", "limit": 50, "scanned": 36, "matched": 2,
        }
        result = svc.persist_scanner_snapshot(
            in_memory_db, response,
            universe="all", sort_by="signal_strength",
        )
        assert result.ok is True
        assert result.skipped is False
        assert result.run_id is not None
        # 1 run + 2 candidates
        assert result.rows_written == 3
        runs = in_memory_db.query(ScannerRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.universe == "all"
        assert run.sort_by == "signal_strength"
        assert run.matched == 2
        assert run.scanned == 36
        assert run.source == "interactive"
        # summary_json carries schema_version and DOES NOT carry items
        assert run.summary_json is not None
        assert run.summary_json.get("schema_version") == svc.SCHEMA_VERSION
        assert "items" not in run.summary_json
        # Two candidate rows in rank order
        cands = in_memory_db.query(ScannerCandidateSnapshot).order_by(
            ScannerCandidateSnapshot.rank,
        ).all()
        assert len(cands) == 2
        assert cands[0].ticker == "NVDA"
        assert cands[0].rank == 1
        assert cands[0].signal_strength == "high"
        assert cands[1].ticker == "MU"
        assert cands[1].rank == 2
        # Full payload preserved
        assert cands[0].payload_json["scan_types"] == ["strong_momentum"]

    def test_empty_items(self, in_memory_db):
        result = svc.persist_scanner_snapshot(
            in_memory_db, {"items": [], "scanned": 36, "matched": 0,
                           "as_of": "2026-05-09"},
            universe="all",
        )
        assert result.ok is True
        # 1 run row, 0 candidates
        assert result.rows_written == 1
        assert in_memory_db.query(ScannerRun).count() == 1
        assert in_memory_db.query(ScannerCandidateSnapshot).count() == 0

    def test_failure_does_not_raise(self, monkeypatch, in_memory_db):
        # Force a failure by monkey-patching commit to raise. The
        # service must catch it and return ok=False without leaking
        # the exception to the caller.
        def _boom():
            raise RuntimeError("simulated DB outage")
        monkeypatch.setattr(in_memory_db, "commit", _boom)
        result = svc.persist_scanner_snapshot(
            in_memory_db,
            {"items": [{"ticker": "X", "instrument_id": str(uuid.uuid4())}],
             "scanned": 1, "matched": 1},
            universe="all",
        )
        assert result.ok is False
        assert result.error == "RuntimeError"


# ---------------------------------------------------------------------------
# Brief snapshot writes
# ---------------------------------------------------------------------------


class TestBriefSnapshot:
    def _sample_brief(self):
        return {
            "generated_at": "2026-05-10T02:00:00+00:00",
            "ticker_count": 2,
            "universe_scope": {
                "scanner_universe": "scanner-research-36",
                "scanner_matched": 1,
                "scanner_scanned": 36,
                "mirror_ticker_count": 5,
                "merged_ticker_count": 2,
                "news_fanout_top_n": 2,
                "effective_news_top_n": 5,
                "requested_news_top_n": 5,
                "days_window": 7,
            },
            "candidates": [
                {"ticker": "NVDA", "company_name": "NVIDIA",
                 "instrument_id": str(uuid.uuid4()),
                 "source_tags": ["HELD", "SCANNER"],
                 "research_priority": 5, "mapping_status": "mapped",
                 "explanation": "x"},
                {"ticker": "AAOI", "company_name": None,
                 "instrument_id": None,
                 "source_tags": ["WATCHED", "UNMAPPED"],
                 "research_priority": 1, "mapping_status": "unmapped",
                 "explanation": "x"},
            ],
            "top_price_anomaly_candidates": [],
            "top_news_linked_candidates": [],
            "earnings_nearby_candidates": [],
            "unmapped_candidates": [],
            "categories_summary": [],
            "provider_diagnostics": {
                "scanner": {"scanned": 36, "matched": 1, "as_of": "2026-05-09"},
                "news": {
                    "fmp": {"status": "ok", "raw_count": 1,
                            "parsed_count": 1, "skipped_count": 0,
                            "note": None, "error": None},
                    "polygon": {"status": "ok", "raw_count": 1,
                                "parsed_count": 1, "skipped_count": 0,
                                "note": None, "error": None},
                    "merged": {"status": "ok", "pre_dedup_count": 2,
                               "deduped_count": 2,
                               "dropped_duplicates": 0},
                    "section_state": "ok",
                    "requested_news_tickers": ["NVDA", "AAOI"],
                    "effective_news_top_n": 5,
                    "requested_news_top_n": 5,
                    "used_cached_news_count": 0,
                    "skipped_due_to_rate_limit": [],
                    "cached_news_age_seconds": None,
                },
                "earnings_status": "ok",
            },
            "side_effects": {
                "db_writes": "NONE", "broker_writes": "NONE",
                "execution_objects": "NONE",
                "live_submit": "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)",
                "scheduler_changes": "NONE",
            },
            "disclaimer": "research-only",
        }

    def test_basic_insert(self, in_memory_db):
        result = svc.persist_market_brief_snapshot(
            in_memory_db, self._sample_brief(), source="interactive",
        )
        assert result.ok is True
        assert result.run_id is not None
        # 1 run + 2 candidates
        assert result.rows_written == 3
        runs = in_memory_db.query(MarketBriefRun).all()
        assert len(runs) == 1
        run = runs[0]
        assert run.ticker_count == 2
        assert run.effective_news_top_n == 5
        assert run.days_window == 7
        assert run.news_section_state == "ok"
        # summary_json keeps the diagnostics + schema_version, drops candidates
        assert run.summary_json["schema_version"] == svc.SCHEMA_VERSION
        for dropped in (
            "candidates", "top_price_anomaly_candidates",
            "top_news_linked_candidates", "earnings_nearby_candidates",
            "unmapped_candidates",
        ):
            assert dropped not in run.summary_json
        assert run.summary_json["universe_scope"]["news_fanout_top_n"] == 2
        # Candidates rows
        cands = in_memory_db.query(MarketBriefCandidateSnapshot).order_by(
            MarketBriefCandidateSnapshot.rank,
        ).all()
        assert [c.ticker for c in cands] == ["NVDA", "AAOI"]
        assert cands[0].source_tags == "HELD,SCANNER"
        assert cands[0].research_priority == 5
        assert cands[1].mapping_status == "unmapped"

    def test_brief_failure_isolated(self, monkeypatch, in_memory_db):
        def _boom():
            raise RuntimeError("simulated DB outage")
        monkeypatch.setattr(in_memory_db, "commit", _boom)
        result = svc.persist_market_brief_snapshot(
            in_memory_db, self._sample_brief(),
        )
        assert result.ok is False
        assert result.error == "RuntimeError"


# ---------------------------------------------------------------------------
# Source-grep guards
# ---------------------------------------------------------------------------


class TestNoForbiddenSymbols:
    def test_service_is_research_only(self):
        src = _strip(inspect.getsource(svc))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "/equity/orders/limit", "/equity/orders/market",
            "broker_account_snapshot", "broker_position_snapshot",
            "broker_order_snapshot",
            "selenium", "playwright", "puppeteer", "webdriver",
            "beautifulsoup",
            "FEATURE_T212_LIVE_SUBMIT",
        ):
            assert needle.lower() not in src.lower(), (
                f"snapshot_service must not reference {needle!r}"
            )

    def test_models_are_research_only(self):
        from libs.db.models import research_snapshot as rs_models
        src = _strip(inspect.getsource(rs_models))
        for needle in (
            "submit_limit_order", "OrderIntent", "OrderDraft",
            "order_intent", "order_draft",
            "broker_account_snapshot", "broker_position_snapshot",
            "broker_order_snapshot",
            "target_price", "position_size",
            "FEATURE_T212_LIVE_SUBMIT",
        ):
            assert needle.lower() not in src.lower(), (
                f"research_snapshot models must not reference {needle!r}"
            )

    def test_migration_is_additive_only(self):
        from infra.migrations.versions import (
            c1d4e7f8a902_add_research_snapshot_tables as mig,
        )
        src = _strip(inspect.getsource(mig))
        # No drop / alter / rename of pre-existing tables
        for needle in (
            "alter_table", "drop_column",
            "drop_table('instrument'", "drop_table('order_",
            "drop_table('broker_", "drop_table('watchlist",
            "rename_table",
        ):
            assert needle.lower() not in src.lower()
        # No broker / order references
        for needle in (
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "broker_account_snapshot", "broker_position_snapshot",
            "broker_order_snapshot",
        ):
            assert needle.lower() not in src.lower()
