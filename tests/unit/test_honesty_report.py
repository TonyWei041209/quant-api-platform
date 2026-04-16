"""Unit tests for the Strategy Honesty Report verdict logic.

Only the pure verdict-classification function is unit-tested here. The full
endpoint is covered by integration tests (requires DB + price data).
"""
from __future__ import annotations

from apps.api.routers.backtest import _verdict_from_retention


class TestVerdictHonest:
    def test_near_full_retention_is_honest(self):
        v, reason = _verdict_from_retention(99.5, 1.79)
        assert v == "honest"
        assert "durable" in reason.lower() or "honest" in reason.lower()

    def test_exactly_85_retention_is_honest(self):
        v, _ = _verdict_from_retention(85.0, 1.0)
        assert v == "honest"


class TestVerdictDegraded:
    def test_70_retention_is_degraded(self):
        v, reason = _verdict_from_retention(70.0, 0.5)
        assert v == "degraded"
        assert "edge" in reason.lower() or "significant" in reason.lower()

    def test_exactly_50_retention_is_degraded(self):
        v, _ = _verdict_from_retention(50.0, 0.3)
        assert v == "degraded"

    def test_just_below_85_is_degraded(self):
        v, _ = _verdict_from_retention(84.9, 0.8)
        assert v == "degraded"


class TestVerdictIllusion:
    def test_low_retention_is_illusion(self):
        v, reason = _verdict_from_retention(30.0, 0.1)
        assert v == "illusion"
        assert "illusion" in reason.lower() or "curve-fit" in reason.lower()

    def test_just_below_50_is_illusion(self):
        v, _ = _verdict_from_retention(49.9, 0.2)
        assert v == "illusion"

    def test_negative_realistic_return_forces_illusion(self):
        """Even if retention math looks high, a negative realistic return
        means the strategy has no true edge after costs."""
        v, reason = _verdict_from_retention(200.0, -0.05)
        assert v == "illusion"
        assert "unprofitable" in reason.lower() or "illusion" in reason.lower()

    def test_zero_realistic_return_is_illusion(self):
        v, _ = _verdict_from_retention(100.0, 0.0)
        assert v == "illusion"


class TestVerdictEdgeCases:
    def test_near_100_retention_with_tiny_positive_return(self):
        """Retention high but absolute return tiny is still honest by our rule
        — that's the caller's problem, not the verdict function's."""
        v, _ = _verdict_from_retention(95.0, 0.001)
        assert v == "honest"

    def test_verdict_function_is_pure(self):
        """Same inputs -> same outputs, no side effects."""
        r1 = _verdict_from_retention(70.0, 0.5)
        r2 = _verdict_from_retention(70.0, 0.5)
        assert r1 == r2
