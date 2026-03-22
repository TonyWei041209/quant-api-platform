"""Integration tests for Phase 3A — backtest engine."""
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
class TestBacktestEngine:
    def test_equal_weight_backtest(self, db):
        from libs.backtest.engine import run_backtest, PortfolioConfig
        result = run_backtest(
            db,
            instrument_ids=[AAPL, MSFT, NVDA],
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            config=PortfolioConfig(initial_capital=100_000, rebalance_frequency="monthly"),
        )
        assert not result.nav_series.empty
        assert len(result.trades) > 0
        assert "total_return" in result.metrics
        assert "sharpe_ratio" in result.metrics
        assert result.metrics["final_nav"] > 0

    def test_backtest_with_costs(self, db):
        from libs.backtest.engine import run_backtest, PortfolioConfig, CostModel
        result = run_backtest(
            db,
            instrument_ids=[AAPL, SPY],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            cost_model=CostModel(slippage_bps=10),
        )
        assert result.metrics["total_costs"] > 0
        assert result.metrics["total_trades"] > 0

    def test_backtest_single_instrument(self, db):
        from libs.backtest.engine import run_backtest
        result = run_backtest(
            db,
            instrument_ids=[SPY],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        assert not result.nav_series.empty
        assert "total_return" in result.metrics

    def test_backtest_summary_output(self, db):
        from libs.backtest.engine import run_backtest
        result = run_backtest(
            db,
            instrument_ids=[AAPL, MSFT],
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        )
        summary = result.summary()
        assert "Backtest Summary" in summary
        assert "total_return" in summary


@pytest.mark.unit
class TestTimeSplit:
    def test_simple_split(self):
        from libs.backtest.time_split import simple_split
        split = simple_split(date(2020, 1, 1), date(2024, 12, 31), train_ratio=0.7)
        assert split.train_start == date(2020, 1, 1)
        assert split.test_end == date(2024, 12, 31)
        assert split.train_end < split.test_start

    def test_walk_forward(self):
        from libs.backtest.time_split import walk_forward_splits
        splits = walk_forward_splits(
            date(2020, 1, 1), date(2024, 12, 31),
            train_days=504, test_days=63, step_days=63,
        )
        assert len(splits) > 0
        for s in splits:
            assert s.train_end < s.test_start
            assert s.test_end <= date(2024, 12, 31)

    def test_expanding_window(self):
        from libs.backtest.time_split import expanding_window_splits
        splits = expanding_window_splits(
            date(2020, 1, 1), date(2024, 12, 31),
        )
        assert len(splits) > 0
        # All splits should start training from same date
        for s in splits:
            assert s.train_start == date(2020, 1, 1)

    def test_no_lookahead(self):
        from libs.backtest.time_split import walk_forward_splits
        splits = walk_forward_splits(date(2020, 1, 1), date(2024, 12, 31))
        for s in splits:
            assert s.train_end < s.test_start, "Train must end before test starts"
