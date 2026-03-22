"""Unit tests for adjusted price calculations."""
import pytest


@pytest.mark.unit
class TestSplitAdjustment:
    def test_split_factor(self):
        """4:1 split should multiply pre-split prices by 4."""
        split_from, split_to = 1, 4
        factor = split_to / split_from
        pre_split_price = 400.0
        adjusted = pre_split_price / factor
        assert adjusted == pytest.approx(100.0)

    def test_reverse_split_factor(self):
        """1:10 reverse split."""
        split_from, split_to = 10, 1
        factor = split_to / split_from
        pre_price = 5.0
        adjusted = pre_price / factor
        assert adjusted == pytest.approx(50.0)


@pytest.mark.unit
class TestDividendAdjustment:
    def test_dividend_factor(self):
        """Dividend adjustment: f = (P_prev - D) / P_prev."""
        prev_close = 100.0
        dividend = 2.0
        factor = (prev_close - dividend) / prev_close
        assert factor == pytest.approx(0.98)

    def test_zero_dividend(self):
        prev_close = 100.0
        dividend = 0.0
        factor = (prev_close - dividend) / prev_close
        assert factor == pytest.approx(1.0)
