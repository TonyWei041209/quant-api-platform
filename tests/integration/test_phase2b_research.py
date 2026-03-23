"""Integration tests for Phase 2B — research layer enhancements."""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session


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


AAPL = "be811ed4-ffa0-4953-8e48-71d40a9539f4"
MSFT = "84be5961-aab5-465f-a826-2609894a1a1a"
NVDA = "2c2ee218-621d-4926-88ea-18cf64651598"
SPY = "f48147fd-f684-4668-b54c-cd4ca2bd29ed"


@pytest.mark.integration
class TestFactorPrimitives:
    def test_daily_returns(self, db):
        from libs.research.factors import get_daily_returns
        df = get_daily_returns(db, AAPL, date(2024, 1, 1), asof_date=date(2024, 3, 31))
        assert not df.empty
        assert "daily_return" in df.columns
        assert len(df) > 50

    def test_rolling_volatility(self, db):
        from libs.research.factors import rolling_volatility
        df = rolling_volatility(db, AAPL, window=20, start_date=date(2024, 1, 1), asof_date=date(2024, 6, 30))
        assert not df.empty
        assert "volatility" in df.columns
        # After 20 days, volatility should be computed
        non_null = df["volatility"].dropna()
        assert len(non_null) > 0
        assert all(v > 0 for v in non_null)

    def test_cumulative_return(self, db):
        from libs.research.factors import cumulative_return
        df = cumulative_return(db, AAPL, date(2024, 1, 1), asof_date=date(2024, 12, 31))
        assert not df.empty
        assert "cum_return" in df.columns

    def test_drawdown(self, db):
        from libs.research.factors import drawdown
        df = drawdown(db, NVDA, date(2024, 1, 1), asof_date=date(2024, 12, 31))
        assert not df.empty
        assert "drawdown" in df.columns
        assert "max_drawdown" in df.columns
        assert df["drawdown"].min() < 0  # Should have some drawdown

    def test_relative_strength(self, db):
        from libs.research.factors import relative_strength
        df = relative_strength(db, AAPL, SPY, date(2024, 1, 1), asof_date=date(2024, 12, 31))
        assert not df.empty
        assert "relative_strength" in df.columns

    def test_momentum(self, db):
        from libs.research.factors import momentum
        result = momentum(db, AAPL, lookback_days=60, skip_recent=5, asof_date=date(2024, 12, 31))
        assert result is not None
        assert isinstance(result, float)

    def test_valuation_snapshot(self, db):
        from libs.research.factors import valuation_snapshot
        snap = valuation_snapshot(db, AAPL, asof_date=date(2024, 12, 31))
        assert snap["latest_price"] is not None
        assert snap["latest_price"] > 0
        assert snap.get("revenue") is not None

    def test_performance_summary(self, db):
        from libs.research.factors import performance_summary
        stats = performance_summary(db, AAPL, date(2024, 1, 1), asof_date=date(2024, 12, 31))
        assert "total_return" in stats
        assert "annualized_volatility" in stats
        assert "max_drawdown" in stats
        assert "sharpe_ratio" in stats
        assert stats["trading_days"] > 200


@pytest.mark.integration
class TestScreeners:
    def test_liquidity_screen(self, db):
        from libs.research.screeners import screen_by_liquidity
        df = screen_by_liquidity(db, min_avg_volume=0, asof_date=date(2024, 12, 31))
        assert not df.empty
        assert len(df) >= 4  # Should have all 4 instruments

    def test_returns_screen(self, db):
        from libs.research.screeners import screen_by_returns
        df = screen_by_returns(db, lookback_days=63, asof_date=date(2024, 12, 31))
        assert not df.empty
        assert "period_return" in df.columns

    def test_fundamentals_screen(self, db):
        from libs.research.screeners import screen_by_fundamentals
        df = screen_by_fundamentals(db, asof_date=date(2024, 12, 31))
        assert not df.empty
        assert "revenue" in df.columns

    def test_rank_universe(self, db):
        from libs.research.screeners import rank_universe
        df = rank_universe(db, asof_date=date(2024, 12, 31))
        assert not df.empty
        assert "composite_rank" in df.columns


@pytest.mark.integration
class TestEventStudyEnhanced:
    def test_earnings_summary_all_tickers(self, db):
        from libs.research.event_study import earnings_event_study_summary
        result = earnings_event_study_summary(db, asof_date=date(2024, 12, 31))
        assert result["total_events"] > 0
        assert "1d" in result["windows"]
        assert result["windows"]["1d"]["sample_count"] > 0

    def test_earnings_summary_filtered(self, db):
        from libs.research.event_study import earnings_event_study_summary
        result = earnings_event_study_summary(db, asof_date=date(2024, 12, 31), instrument_ids=[AAPL])
        assert result["total_events"] > 0
        assert "AAPL" in result["by_ticker"]


@pytest.mark.integration
class TestResearchAPIs:
    def test_performance_api(self):
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.get(f"/research/instrument/{AAPL}/performance?start=2024-01-01&end=2024-12-31")
        assert resp.status_code == 200
        data = resp.json()
        assert "performance" in data
        assert "total_return" in data["performance"]

    def test_valuation_api(self):
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.get(f"/research/instrument/{AAPL}/valuation")
        assert resp.status_code == 200
        data = resp.json()
        assert "valuation" in data
        assert data["valuation"]["latest_price"] > 0

    def test_screener_liquidity_api(self):
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.get("/research/screener/liquidity?min_avg_volume=0")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) >= 4

    def test_event_study_summary_api(self):
        from fastapi.testclient import TestClient
        from apps.api.main import app
        client = TestClient(app)
        resp = client.post("/research/event-study/earnings/summary", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_events"] > 0
