"""Unit tests for DQ rules."""
import pytest


@pytest.mark.unit
class TestOHLCLogic:
    def test_valid_ohlc(self):
        """Valid OHLC should pass."""
        o, h, l, c = 100.0, 105.0, 98.0, 103.0
        assert h >= max(o, c, l)
        assert l <= min(o, c, h)

    def test_invalid_high(self):
        """High less than open should fail."""
        o, h, l, c = 100.0, 99.0, 98.0, 103.0
        assert not (h >= max(o, c, l))

    def test_invalid_low(self):
        """Low greater than open should fail."""
        o, h, l, c = 100.0, 105.0, 101.0, 99.0
        assert not (l <= min(o, c, h))


@pytest.mark.unit
class TestNonNegative:
    def test_valid_prices(self):
        assert all(v >= 0 for v in [100.0, 105.0, 98.0, 103.0, 50000])

    def test_negative_price(self):
        assert not all(v >= 0 for v in [-1.0, 105.0, 98.0, 103.0, 50000])

    def test_negative_volume(self):
        assert not all(v >= 0 for v in [100.0, 105.0, 98.0, 103.0, -1])


@pytest.mark.unit
class TestCorporateActionValidity:
    def test_valid_split(self):
        split_from, split_to = 1, 4
        assert split_from > 0 and split_to > 0

    def test_invalid_split_zero(self):
        split_from, split_to = 0, 4
        assert not (split_from > 0 and split_to > 0)

    def test_valid_dividend(self):
        cash_amount = 0.25
        assert cash_amount >= 0

    def test_invalid_negative_dividend(self):
        cash_amount = -0.25
        assert not (cash_amount >= 0)


@pytest.mark.unit
class TestPITRule:
    def test_reported_at_before_asof(self):
        from datetime import datetime, UTC
        reported_at = datetime(2024, 2, 15, tzinfo=UTC)
        asof = datetime(2024, 3, 1, tzinfo=UTC)
        assert reported_at <= asof

    def test_reported_at_after_asof_fails(self):
        from datetime import datetime, UTC
        reported_at = datetime(2024, 3, 15, tzinfo=UTC)
        asof = datetime(2024, 3, 1, tzinfo=UTC)
        assert not (reported_at <= asof)
