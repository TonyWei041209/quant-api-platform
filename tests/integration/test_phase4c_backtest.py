"""Phase 4C: Backtest persistence and strategy interface tests."""
from __future__ import annotations

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import text

from libs.db.session import get_sync_session as get_test_session


class TestBacktestPersistence:
    """Test backtest result persistence."""

    def test_persist_and_load_run(self):
        """Persist a backtest result and load it back."""
        from libs.backtest.engine import BacktestResult, Trade, CostModel, PortfolioConfig
        from libs.backtest.persistence import persist_backtest_result, load_backtest_run
        import pandas as pd

        session = get_test_session()
        try:
            # Get a real instrument_id
            row = session.execute(text(
                "SELECT instrument_id FROM instrument LIMIT 1"
            )).fetchone()
            if not row:
                pytest.skip("No instruments in database")

            iid = row[0]

            # Create a minimal backtest result
            nav_df = pd.DataFrame([
                {"trade_date": date(2024, 1, 2), "nav": 100000.0, "daily_return": None},
                {"trade_date": date(2024, 1, 3), "nav": 100500.0, "daily_return": 0.005},
                {"trade_date": date(2024, 1, 4), "nav": 100200.0, "daily_return": -0.003},
            ])

            trades = [
                Trade(
                    trade_date=date(2024, 1, 2),
                    instrument_id=iid,
                    ticker="TEST",
                    side="buy",
                    qty=100,
                    price=150.0,
                    cost=7.5,
                    notional=15000.0,
                ),
            ]

            result = BacktestResult(
                nav_series=nav_df,
                trades=trades,
                metrics={
                    "total_return": 0.002,
                    "annualized_return": 0.50,
                    "annualized_volatility": 0.15,
                    "sharpe_ratio": 3.33,
                    "max_drawdown": -0.003,
                    "total_trades": 1,
                    "total_turnover": 0.15,
                    "total_costs": 7.5,
                    "final_nav": 100200.0,
                    "initial_capital": 100000.0,
                },
                config={
                    "start_date": "2024-01-02",
                    "end_date": "2024-01-04",
                    "cost_model": {"slippage_bps": 5.0},
                },
            )

            run_id = persist_backtest_result(
                session=session,
                result=result,
                strategy_name="test_momentum",
                instrument_ids=[str(iid)],
                config=result.config,
                trades=trades,
            )
            session.commit()

            assert run_id is not None
            assert isinstance(run_id, uuid.UUID)

            # Load it back
            loaded = load_backtest_run(session, run_id)
            assert loaded is not None
            assert loaded.strategy_name == "test_momentum"
            assert loaded.total_return == pytest.approx(0.002)
            assert loaded.sharpe_ratio == pytest.approx(3.33)
            assert loaded.nav_series is not None
            assert len(loaded.nav_series) == 3

        finally:
            session.close()

    def test_list_runs(self):
        """List backtest runs."""
        from libs.backtest.persistence import list_backtest_runs

        session = get_test_session()
        try:
            runs = list_backtest_runs(session)
            assert isinstance(runs, list)
        finally:
            session.close()

    def test_load_trades(self):
        """Load trades for a run."""
        from libs.backtest.persistence import list_backtest_runs, load_backtest_trades

        session = get_test_session()
        try:
            runs = list_backtest_runs(session)
            if not runs:
                pytest.skip("No backtest runs")

            trades = load_backtest_trades(session, runs[0].run_id)
            assert isinstance(trades, list)
        finally:
            session.close()


class TestRealBacktest:
    """Test running a real backtest on DB data."""

    def test_run_equal_weight_backtest(self):
        """Run an equal-weight backtest on real DB data."""
        from libs.backtest.engine import run_backtest, CostModel, PortfolioConfig

        session = get_test_session()
        try:
            # Get instrument_ids
            rows = session.execute(text(
                "SELECT i.instrument_id::text FROM instrument i "
                "JOIN price_bar_raw p ON p.instrument_id = i.instrument_id "
                "GROUP BY i.instrument_id HAVING COUNT(*) > 100"
            )).fetchall()

            if not rows:
                pytest.skip("No instruments with enough price data")

            iids = [r[0] for r in rows[:4]]

            result = run_backtest(
                session=session,
                instrument_ids=iids,
                start_date=date(2023, 1, 1),
                end_date=date(2024, 12, 31),
                config=PortfolioConfig(max_positions=4, rebalance_frequency="monthly"),
                cost_model=CostModel(slippage_bps=5.0),
            )

            assert result.nav_series is not None
            assert not result.nav_series.empty
            assert "total_return" in result.metrics
            assert "sharpe_ratio" in result.metrics
            assert "max_drawdown" in result.metrics
            assert len(result.trades) > 0

        finally:
            session.close()

    def test_run_and_persist_backtest(self):
        """Run a backtest and persist results."""
        from libs.backtest.engine import run_and_persist_backtest, CostModel, PortfolioConfig

        session = get_test_session()
        try:
            rows = session.execute(text(
                "SELECT i.instrument_id::text FROM instrument i "
                "JOIN price_bar_raw p ON p.instrument_id = i.instrument_id "
                "GROUP BY i.instrument_id HAVING COUNT(*) > 100"
            )).fetchall()

            if not rows:
                pytest.skip("No instruments with enough price data")

            iids = [r[0] for r in rows[:2]]

            result, run_id = run_and_persist_backtest(
                session=session,
                instrument_ids=iids,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 6, 30),
                strategy_name="test_phase4c",
                config=PortfolioConfig(max_positions=2),
                cost_model=CostModel(slippage_bps=5.0),
            )
            session.commit()

            assert run_id is not None
            assert result.metrics.get("total_return") is not None

        finally:
            session.close()


class TestStrategyInterface:
    """Test strategy interface abstractions."""

    def test_momentum_signal_provider(self):
        """Test MomentumSignalProvider generates signals from DB."""
        from libs.backtest.strategy import MomentumSignalProvider, AllActiveUniverse

        session = get_test_session()
        try:
            universe = AllActiveUniverse()
            iids = universe.get_universe(session, date(2024, 12, 31))

            if not iids:
                pytest.skip("No active instruments")

            provider = MomentumSignalProvider(lookback_days=63)
            signals = provider.generate_signals(session, iids, date(2024, 12, 31))

            assert isinstance(signals, list)
            if signals:
                s = signals[0]
                assert hasattr(s, "instrument_id")
                assert hasattr(s, "weight")
                assert hasattr(s, "score")
        finally:
            session.close()

    def test_equal_weight_constructor(self):
        """Test EqualWeightConstructor."""
        from libs.backtest.strategy import Signal, EqualWeightConstructor

        constructor = EqualWeightConstructor(max_positions=3)
        signals = [
            Signal(instrument_id=uuid.uuid4(), ticker="A", weight=1.0, score=0.10),
            Signal(instrument_id=uuid.uuid4(), ticker="B", weight=1.0, score=0.05),
            Signal(instrument_id=uuid.uuid4(), ticker="C", weight=1.0, score=0.08),
            Signal(instrument_id=uuid.uuid4(), ticker="D", weight=1.0, score=0.02),
        ]

        weights = constructor.construct(signals, {})
        assert len(weights) == 3  # max_positions
        # All should be roughly equal
        for w in weights.values():
            assert w == pytest.approx(1.0 / 3.0)

    def test_max_position_risk_overlay(self):
        """Test MaxPositionRiskOverlay."""
        from libs.backtest.strategy import MaxPositionRiskOverlay

        overlay = MaxPositionRiskOverlay(max_weight=0.30)
        weights = {uuid.uuid4(): 0.5, uuid.uuid4(): 0.3, uuid.uuid4(): 0.2}

        adjusted = overlay.apply(weights, {})
        # After capping at 0.30 and renormalizing, weights should sum to 1.0
        assert sum(adjusted.values()) == pytest.approx(1.0, abs=0.01)
        # No single weight should exceed max_weight * 1.5 (renormalization tolerance)
        for w in adjusted.values():
            assert w <= 0.45


class TestBacktestAPI:
    """Test backtest API endpoints."""

    def test_list_runs_endpoint(self):
        """GET /backtest/runs returns runs."""
        from fastapi.testclient import TestClient
        from apps.api.main import app

        client = TestClient(app)
        resp = client.get("/backtest/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data

    def test_run_backtest_endpoint(self):
        """POST /backtest/run creates a backtest."""
        from fastapi.testclient import TestClient
        from apps.api.main import app

        client = TestClient(app)
        resp = client.post("/backtest/run", json={
            "strategy": "api_test",
            "tickers": ["AAPL", "MSFT"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "commission_bps": 5.0,
            "slippage_bps": 5.0,
            "max_positions": 2,
            "rebalance_freq": "monthly",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "metrics" in data

        # Now fetch it
        run_id = data["run_id"]
        resp2 = client.get(f"/backtest/runs/{run_id}")
        assert resp2.status_code == 200

        # Fetch trades
        resp3 = client.get(f"/backtest/runs/{run_id}/trades")
        assert resp3.status_code == 200
        assert "trades" in resp3.json()

        # Fetch NAV
        resp4 = client.get(f"/backtest/runs/{run_id}/nav")
        assert resp4.status_code == 200
        assert "nav_series" in resp4.json()
