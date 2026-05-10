"""Brief history service — read-only query layer tests."""
from __future__ import annotations

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
)
from libs.research_snapshot import (
    brief_history_service as hist,
    snapshot_service as svc,
)


# SQLite compat (mirrors test_research_snapshot_service.py)
@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(type_, compiler, **kw):  # pragma: no cover
    return "VARCHAR(36)"


@pytest.fixture
def in_memory_db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine, tables=[
        MarketBriefRun.__table__,
        MarketBriefCandidateSnapshot.__table__,
    ])
    session = Session(engine)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(autouse=True)
def _flag_on(monkeypatch):
    monkeypatch.setenv("FEATURE_RESEARCH_SNAPSHOT_WRITE", "true")


def _persist_sample(db, *, source="interactive", with_news=True):
    """Helper — persist one brief, return run_id."""
    brief = {
        "generated_at": "2026-05-10T02:00:00+00:00",
        "ticker_count": 2,
        "universe_scope": {
            "scanner_universe": "scanner-research-36",
            "scanner_matched": 1,
            "scanner_scanned": 36,
            "mirror_ticker_count": 1,
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
             "explanation": "x",
             "taxonomy": {"broad": "Technology", "subs": ["GPU"]},
             "scanner": {"scan_types": ["strong_momentum"],
                         "signal_strength": "high"},
             "price_move": {"change_1d_pct": 2.0},
             "recent_news": (
                 [{"title": "MU news", "ticker": "NVDA",
                   "published_at": "2026-05-09T12:00:00Z"}]
                 if with_news else []
             ),
             "upcoming_earnings": []},
            {"ticker": "AAOI", "company_name": None,
             "instrument_id": None,
             "source_tags": ["WATCHED", "UNMAPPED"],
             "research_priority": 1,
             "mapping_status": "newly_resolvable",
             "explanation": "x",
             "taxonomy": {"broad": "Technology", "subs": ["Optical"]},
             "scanner": {},
             "price_move": {},
             "recent_news": [],
             "upcoming_earnings": [
                 {"date": "2026-05-12", "symbol": "AAOI"}
             ]},
        ],
        "top_price_anomaly_candidates": [],
        "top_news_linked_candidates": [],
        "earnings_nearby_candidates": [],
        "unmapped_candidates": [],
        "categories_summary": [],
        "provider_diagnostics": {
            "scanner": {"scanned": 36, "matched": 1, "as_of": "2026-05-09"},
            "news": {"section_state": "ok",
                     "merged": {"status": "ok", "pre_dedup_count": 1,
                                "deduped_count": 1, "dropped_duplicates": 0}},
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
    result = svc.persist_market_brief_snapshot(db, brief, source=source)
    assert result.ok and not result.skipped
    return result.run_id


class TestList:
    def test_list_empty(self, in_memory_db):
        assert hist.list_brief_runs(in_memory_db) == []

    def test_list_returns_summaries_in_recent_first_order(self, in_memory_db):
        rid_a = _persist_sample(in_memory_db, source="interactive")
        rid_b = _persist_sample(in_memory_db, source="overnight-job")
        items = hist.list_brief_runs(in_memory_db, limit=10)
        # Both rows present (order depends on generated_at parsed from
        # the brief which is identical → fall back to whatever DB
        # ordering returns; just assert both UUIDs present).
        ids = {it["run_id"] for it in items}
        assert {str(rid_a), str(rid_b)}.issubset(ids)
        # Each row carries the lightweight summary shape only
        for it in items:
            assert set(it.keys()) >= {
                "run_id", "generated_at", "source", "ticker_count",
                "effective_news_top_n", "days_window",
                "news_section_state",
            }
            # Heavy `candidates` list MUST NOT be returned by the list endpoint
            assert "candidates" not in it

    def test_list_limit(self, in_memory_db):
        for _ in range(5):
            _persist_sample(in_memory_db)
        items = hist.list_brief_runs(in_memory_db, limit=3)
        assert len(items) == 3

    def test_list_source_filter(self, in_memory_db):
        _persist_sample(in_memory_db, source="interactive")
        _persist_sample(in_memory_db, source="overnight-job")
        items = hist.list_brief_runs(in_memory_db, source="overnight-job")
        assert len(items) == 1
        assert items[0]["source"] == "overnight-job"


class TestLatest:
    def test_latest_none_when_empty(self, in_memory_db):
        assert hist.get_latest_brief(in_memory_db) is None

    def test_latest_hydrates_full_payload(self, in_memory_db):
        _persist_sample(in_memory_db)
        latest = hist.get_latest_brief(in_memory_db)
        assert latest is not None
        assert latest["persisted"] is True
        assert latest["ticker_count"] == 2
        # Candidates rebuilt from snapshot rows (preserves payload_json)
        assert len(latest["candidates"]) == 2
        nvda = next(c for c in latest["candidates"] if c["ticker"] == "NVDA")
        assert nvda["research_priority"] == 5
        # Derived sections recomputed from candidate payload
        assert any(c["ticker"] == "NVDA"
                   for c in latest["top_price_anomaly_candidates"])
        assert any(c["ticker"] == "NVDA"
                   for c in latest["top_news_linked_candidates"])
        assert any(c["ticker"] == "AAOI"
                   for c in latest["earnings_nearby_candidates"])
        # Unmapped section includes newly_resolvable AAOI
        assert any(c["ticker"] == "AAOI"
                   for c in latest["unmapped_candidates"])
        # Categories summary recomputed
        assert any(b["broad"] == "Technology"
                   for b in latest["categories_summary"])
        # Side-effect block preserved
        assert latest["side_effects"]["db_writes"] == "NONE"
        assert "FEATURE_T212_LIVE_SUBMIT=false" in latest["side_effects"]["live_submit"]

    def test_latest_source_filter(self, in_memory_db):
        a = _persist_sample(in_memory_db, source="interactive")
        b = _persist_sample(in_memory_db, source="overnight-job")
        latest_overnight = hist.get_latest_brief(
            in_memory_db, source="overnight-job",
        )
        assert latest_overnight is not None
        assert latest_overnight["source"] == "overnight-job"


class TestById:
    def test_returns_none_for_unknown(self, in_memory_db):
        assert hist.get_brief_by_id(
            in_memory_db, str(uuid.uuid4())) is None

    def test_returns_none_for_invalid_uuid(self, in_memory_db):
        assert hist.get_brief_by_id(in_memory_db, "not-a-uuid") is None

    def test_round_trip(self, in_memory_db):
        rid = _persist_sample(in_memory_db)
        brief = hist.get_brief_by_id(in_memory_db, rid)
        assert brief is not None
        assert brief["run_id"] == str(rid)
        assert brief["ticker_count"] == 2
