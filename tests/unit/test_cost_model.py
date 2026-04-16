"""Unit tests for the realistic backtest CostModel.

Covers:
- Legacy slippage_bps + commission_per_share (backward compat)
- New spread_bps
- New fx_fee_bps (conditional on currency != base_currency)
- New volume_impact_bps (conditional on participation > threshold)
- Graceful fallbacks (no currency, no volume data)
- Breakdown sums to total
"""
from __future__ import annotations

import pytest

from libs.backtest.engine import CostModel


class TestLegacyBehavior:
    """Verify legacy-only parameters still produce identical results."""

    def test_default_costmodel_only_slippage(self):
        cm = CostModel()  # defaults: slippage_bps=5
        r = cm.compute_cost_breakdown(qty=100, price=50.0)
        assert r["slippage"] == pytest.approx(2.5)  # 5 bps on 5000
        assert r["commission"] == 0
        assert r["spread"] == 0
        assert r["fx_fee"] == 0
        assert r["volume_impact"] == 0
        assert r["total"] == pytest.approx(2.5)

    def test_compute_cost_legacy_signature(self):
        """Verify the 2-arg positional form still works."""
        cm = CostModel(slippage_bps=10)
        # 10 bps on 10000 notional = 10
        assert cm.compute_cost(qty=200, price=50.0) == pytest.approx(10.0)

    def test_commission_min_enforced(self):
        cm = CostModel(slippage_bps=0, commission_per_share=0.001, commission_min=1.0)
        # 100 shares * 0.001 = 0.10, min = 1.0 -> 1.0
        r = cm.compute_cost_breakdown(qty=100, price=50.0)
        assert r["commission"] == pytest.approx(1.0)


class TestSpread:
    def test_spread_applied_to_notional(self):
        cm = CostModel(slippage_bps=0, spread_bps=20.0)
        # 20 bps on 10000 = 20
        r = cm.compute_cost_breakdown(qty=200, price=50.0)
        assert r["spread"] == pytest.approx(20.0)
        assert r["total"] == pytest.approx(20.0)

    def test_spread_applied_regardless_of_side(self):
        """Spread is half-spread per side — engine applies to both buy and sell trades."""
        cm = CostModel(slippage_bps=0, spread_bps=10.0)
        buy = cm.compute_cost_breakdown(qty=100, price=50.0)
        sell = cm.compute_cost_breakdown(qty=-100, price=50.0)
        # abs() is used, so both should be equal
        assert buy["spread"] == sell["spread"]


class TestFxFee:
    def test_fx_applied_when_currency_differs(self):
        cm = CostModel(slippage_bps=0, fx_fee_bps=15.0, base_currency="GBP")
        r = cm.compute_cost_breakdown(qty=100, price=50.0, currency="USD")
        # 15 bps on 5000 = 7.5
        assert r["fx_fee"] == pytest.approx(7.5)

    def test_fx_not_applied_when_same_currency(self):
        cm = CostModel(slippage_bps=0, fx_fee_bps=15.0, base_currency="GBP")
        r = cm.compute_cost_breakdown(qty=100, price=50.0, currency="GBP")
        assert r["fx_fee"] == 0

    def test_fx_not_applied_when_currency_missing(self):
        """Graceful fallback: no currency info => no FX fee."""
        cm = CostModel(slippage_bps=0, fx_fee_bps=15.0, base_currency="USD")
        r = cm.compute_cost_breakdown(qty=100, price=50.0, currency=None)
        assert r["fx_fee"] == 0

    def test_fx_not_applied_when_rate_zero(self):
        """Configured currency differs but fee rate is 0."""
        cm = CostModel(slippage_bps=0, fx_fee_bps=0.0, base_currency="GBP")
        r = cm.compute_cost_breakdown(qty=100, price=50.0, currency="USD")
        assert r["fx_fee"] == 0


class TestVolumeImpact:
    def test_impact_triggered_above_threshold(self):
        cm = CostModel(
            slippage_bps=0,
            volume_impact_bps=50.0,
            volume_impact_threshold=0.01,
        )
        # qty=1000 @ $10 notional=10000; daily_volume=50000
        # participation = 0.02, excess = 0.01 = threshold
        # impact_bps = 50 * (0.01/0.01) = 50 -> impact = 10000 * 50/10000 = 50
        r = cm.compute_cost_breakdown(qty=1000, price=10.0, daily_volume=50000)
        assert r["volume_impact"] == pytest.approx(50.0)

    def test_impact_not_triggered_below_threshold(self):
        cm = CostModel(
            slippage_bps=0,
            volume_impact_bps=50.0,
            volume_impact_threshold=0.01,
        )
        # participation = 0.002, below threshold
        r = cm.compute_cost_breakdown(qty=100, price=10.0, daily_volume=50000)
        assert r["volume_impact"] == 0

    def test_impact_scales_linearly_with_excess(self):
        cm = CostModel(
            slippage_bps=0,
            volume_impact_bps=100.0,
            volume_impact_threshold=0.01,
        )
        # participation = 0.03, excess = 0.02 = 2x threshold
        # impact_bps = 100 * 2 = 200 -> impact = 10000 * 200/10000 = 200
        r = cm.compute_cost_breakdown(qty=3000, price=10.0 / 3, daily_volume=100000)
        # Actually qty=3000, price=10/3 ~= 3.33, notional ~= 10000
        # participation = 3000/100000 = 0.03
        assert r["volume_impact"] == pytest.approx(200.0, rel=0.01)

    def test_impact_graceful_without_volume_data(self):
        cm = CostModel(slippage_bps=0, volume_impact_bps=50.0)
        r = cm.compute_cost_breakdown(qty=1000, price=10.0, daily_volume=None)
        assert r["volume_impact"] == 0

    def test_impact_graceful_with_zero_volume(self):
        cm = CostModel(slippage_bps=0, volume_impact_bps=50.0)
        r = cm.compute_cost_breakdown(qty=1000, price=10.0, daily_volume=0)
        assert r["volume_impact"] == 0


class TestCompositeT212Scenario:
    """Realistic T212 GBP account buying a US stock."""

    def test_t212_realistic_buy(self):
        cm = CostModel(
            commission_per_share=0.0,   # T212 is commission-free
            slippage_bps=5.0,            # conservative retail slippage
            spread_bps=10.0,             # typical US large cap spread
            fx_fee_bps=15.0,             # T212 FX fee
            base_currency="GBP",
            volume_impact_bps=0.0,       # large caps, no impact
        )
        # Buying 100 AAPL @ $150 = $15,000 notional
        r = cm.compute_cost_breakdown(qty=100, price=150.0, currency="USD")

        assert r["commission"] == 0
        assert r["slippage"] == pytest.approx(7.5)   # 5bps
        assert r["spread"] == pytest.approx(15.0)    # 10bps
        assert r["fx_fee"] == pytest.approx(22.5)    # 15bps
        assert r["volume_impact"] == 0
        # Total = 7.5 + 15 + 22.5 = 45
        assert r["total"] == pytest.approx(45.0)

        # Cost as % of notional
        cost_pct = r["total"] / (100 * 150) * 100
        assert cost_pct == pytest.approx(0.3)  # 30 bps total friction


class TestBreakdownInvariant:
    """total should always equal sum of components."""

    def test_breakdown_sums_to_total(self):
        cm = CostModel(
            commission_per_share=0.01,
            commission_min=1.0,
            slippage_bps=5,
            spread_bps=10,
            fx_fee_bps=15,
            base_currency="USD",
            volume_impact_bps=25,
            volume_impact_threshold=0.01,
        )
        r = cm.compute_cost_breakdown(
            qty=2000, price=20.0,
            currency="EUR",
            daily_volume=50000,  # 4% participation
        )
        parts = r["commission"] + r["slippage"] + r["spread"] + r["fx_fee"] + r["volume_impact"]
        assert r["total"] == pytest.approx(parts)
