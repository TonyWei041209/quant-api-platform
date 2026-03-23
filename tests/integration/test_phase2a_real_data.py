"""Integration tests for Phase 2A — real data validation."""
from __future__ import annotations

from datetime import date, datetime, UTC

import pytest
from sqlalchemy import create_engine, text, func
from sqlalchemy.orm import sessionmaker, Session

from libs.db.models import *


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
    session.close()


@pytest.mark.integration
class TestRealPriceData:
    def test_price_bars_exist(self, db):
        """Verify real price bars were ingested."""
        count = db.execute(text("SELECT COUNT(*) FROM price_bar_raw")).scalar()
        assert count >= 6000, f"Expected >= 6000 price bars, got {count}"

    def test_aapl_prices_reasonable(self, db):
        """AAPL prices should be in reasonable range."""
        result = db.execute(text(
            "SELECT MIN(close), MAX(close), COUNT(*) FROM price_bar_raw "
            "WHERE instrument_id = (SELECT instrument_id FROM instrument_identifier "
            "WHERE id_type='ticker' AND id_value='AAPL' LIMIT 1)"
        )).fetchone()
        min_close, max_close, count = float(result[0]), float(result[1]), result[2]
        assert count > 1000
        assert min_close > 50   # AAPL shouldn't be below $50 since 2020
        assert max_close < 500  # AAPL shouldn't be above $500

    def test_nvda_has_split_data(self, db):
        """NVDA should have split records (10:1 in June 2024)."""
        count = db.execute(text(
            "SELECT COUNT(*) FROM corporate_action "
            "WHERE instrument_id = (SELECT instrument_id FROM instrument_identifier "
            "WHERE id_type='ticker' AND id_value='NVDA' LIMIT 1) "
            "AND action_type = 'split'"
        )).scalar()
        assert count >= 1, "NVDA should have at least 1 split record"

    def test_dividends_exist(self, db):
        """AAPL should have dividend records."""
        count = db.execute(text(
            "SELECT COUNT(*) FROM corporate_action "
            "WHERE instrument_id = (SELECT instrument_id FROM instrument_identifier "
            "WHERE id_type='ticker' AND id_value='AAPL' LIMIT 1) "
            "AND action_type = 'cash_dividend'"
        )).scalar()
        assert count >= 10, f"AAPL should have >= 10 dividends, got {count}"


@pytest.mark.integration
class TestRealEarningsEvents:
    def test_earnings_events_exist(self, db):
        """Verify earnings events were ingested."""
        count = db.execute(text("SELECT COUNT(*) FROM earnings_event")).scalar()
        assert count >= 50, f"Expected >= 50 earnings events, got {count}"

    def test_earnings_have_eps(self, db):
        """Some earnings should have EPS actual data."""
        count = db.execute(text(
            "SELECT COUNT(*) FROM earnings_event WHERE eps_actual IS NOT NULL"
        )).scalar()
        assert count >= 10, f"Expected >= 10 events with EPS actual"


@pytest.mark.integration
class TestEventStudyOnRealData:
    def test_aapl_event_study_returns_results(self, db):
        """Event study on AAPL should return results with real data."""
        from libs.research.event_study import earnings_event_study
        aapl_id = "be811ed4-ffa0-4953-8e48-71d40a9539f4"
        df = earnings_event_study(db, aapl_id, asof_date=date(2024, 12, 31))
        assert not df.empty, "Event study should return results for AAPL"
        assert "ret_1d" in df.columns
        # Should have events with return data
        has_returns = df.dropna(subset=["ret_1d"])
        assert len(has_returns) >= 10

    def test_nvda_event_study_returns_results(self, db):
        """Event study on NVDA should work despite the stock split."""
        from libs.research.event_study import earnings_event_study
        nvda_id = "2c2ee218-621d-4926-88ea-18cf64651598"
        df = earnings_event_study(db, nvda_id, asof_date=date(2024, 12, 31))
        assert not df.empty


@pytest.mark.integration
class TestAdjustedPricesOnRealData:
    def test_nvda_split_adjusted(self, db):
        """NVDA split-adjusted prices should show continuity."""
        from libs.research.adjusted_prices import get_split_adjusted_prices
        nvda_id = "2c2ee218-621d-4926-88ea-18cf64651598"
        df = get_split_adjusted_prices(db, nvda_id, date(2024, 6, 1), date(2024, 6, 30))
        assert not df.empty
        # Pre-split prices should have adj_factor > 1
        pre_split = df[df["adj_factor"] > 1]
        post_split = df[df["adj_factor"] == 1]
        assert len(pre_split) > 0, "Should have pre-split adjusted bars"
        assert len(post_split) > 0, "Should have post-split bars"

    def test_aapl_total_return_adjusted(self, db):
        """AAPL total-return-adjusted should incorporate dividends."""
        from libs.research.adjusted_prices import get_total_return_adjusted_prices
        aapl_id = "be811ed4-ffa0-4953-8e48-71d40a9539f4"
        df = get_total_return_adjusted_prices(db, aapl_id, date(2024, 1, 1), date(2024, 12, 31))
        assert not df.empty
        # tr_factor should be < 1 for most dates (dividends reduce historical factor)
        assert (df["tr_factor"] <= 1.0).all()


@pytest.mark.integration
class TestAPIWithRealData:
    def test_instrument_summary_has_financials(self):
        """API summary should return real financial data."""
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.get("/research/instrument/be811ed4-ffa0-4953-8e48-71d40a9539f4/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["latest_financials"]) > 0
        assert len(data["recent_prices"]) > 0

    def test_event_study_api(self):
        """Event study API should work with real data."""
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.post("/research/event-study/earnings", json={
            "instrument_id": "be811ed4-ffa0-4953-8e48-71d40a9539f4",
            "windows": [1, 3, 5, 10],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) > 0

    def test_instrument_prices_api(self):
        """Prices API should return real price data."""
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.get("/research/instrument/be811ed4-ffa0-4953-8e48-71d40a9539f4/prices?start=2024-01-01&end=2024-03-31")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["prices"]) > 50
