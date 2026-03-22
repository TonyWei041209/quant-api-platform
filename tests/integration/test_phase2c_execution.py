"""Integration tests for Phase 2C — execution layer hardening."""
from __future__ import annotations

import uuid
from datetime import datetime, UTC

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from libs.db.models.instrument import Instrument
from libs.db.models.order_intent import OrderIntent
from libs.db.models.order_draft import OrderDraft


def get_test_session() -> Session:
    engine = create_engine(
        "postgresql+psycopg2://quant:quant_dev_password@localhost:5432/quant_platform",
        echo=False,
    )
    return sessionmaker(engine, expire_on_commit=False)()


@pytest.fixture
def db():
    session = get_test_session()
    yield session
    session.rollback()
    session.close()


AAPL = "be811ed4-ffa0-4953-8e48-71d40a9539f4"


@pytest.mark.integration
class TestRiskChecks:
    def test_positive_quantity_check(self):
        from libs.execution.risk_checks import check_positive_quantity

        class MockDraft:
            qty = 10
        assert check_positive_quantity(MockDraft()).passed

        class MockDraft2:
            qty = 0
        assert not check_positive_quantity(MockDraft2()).passed

    def test_max_position_size(self):
        from libs.execution.risk_checks import check_max_position_size

        class MockDraft:
            qty = 100
        assert check_max_position_size(MockDraft(), max_qty=10000).passed

        class MockDraft2:
            qty = 20000
        assert not check_max_position_size(MockDraft2(), max_qty=10000).passed

    def test_max_notional(self):
        from libs.execution.risk_checks import check_max_notional

        class MockDraft:
            qty = 100
            limit_price = 200.0
        result = check_max_notional(MockDraft(), max_notional=1_000_000)
        assert result.passed  # 100 * 200 = 20000 < 1M

    def test_limit_price_required(self):
        from libs.execution.risk_checks import check_limit_price_required

        class MockDraft:
            order_type = "limit"
            limit_price = None
            stop_price = None
        assert not check_limit_price_required(MockDraft()).passed

    def test_trading_day_check(self, db):
        from libs.execution.risk_checks import check_trading_day
        result = check_trading_day(db)
        # Should return a result (pass or fail depending on day)
        assert result.rule == "trading_day"


@pytest.mark.integration
class TestOrderLifecycle:
    def test_create_approve_lifecycle(self, db):
        from libs.execution.intents import create_intent
        from libs.execution.drafts import create_draft_from_intent, approve_draft

        intent = create_intent(db, "test_strategy", AAPL, "buy", target_qty=10)
        db.flush()

        draft = create_draft_from_intent(db, intent.intent_id, order_type="limit", qty=10, limit_price=150.0)
        db.flush()

        assert draft.status == "pending_approval"

        approved = approve_draft(db, draft.draft_id)
        assert approved.status == "approved"
        assert approved.approved_at is not None

    def test_reject_draft(self, db):
        from libs.execution.intents import create_intent
        from libs.execution.drafts import create_draft_from_intent, reject_draft

        intent = create_intent(db, "test_strategy", AAPL, "buy", target_qty=5)
        db.flush()
        draft = create_draft_from_intent(db, intent.intent_id, order_type="market", qty=5)
        db.flush()

        rejected = reject_draft(db, draft.draft_id, "test rejection")
        assert rejected.status == "rejected"


@pytest.mark.integration
class TestExecutionAPI:
    def test_risk_check_api(self):
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)

        # Create intent
        resp = client.post("/execution/intents", json={
            "strategy_name": "api_test",
            "instrument_id": AAPL,
            "side": "buy",
            "target_qty": 10,
        })
        assert resp.status_code == 200
        intent_id = resp.json()["intent_id"]

        # Create draft
        resp = client.post(f"/execution/drafts/from-intent/{intent_id}", json={
            "order_type": "limit",
            "qty": 10,
            "limit_price": 150.0,
        })
        assert resp.status_code == 200
        draft_id = resp.json()["draft_id"]

        # Run risk check
        resp = client.get(f"/execution/drafts/{draft_id}/risk-check")
        assert resp.status_code == 200
        data = resp.json()
        assert "checks" in data
        assert len(data["checks"]) >= 5
