"""Unit tests for Trading 212 adapter."""
import pytest
from libs.adapters.trading212_adapter import Trading212Adapter
from libs.core.exceptions import LiveSubmitDisabledError


@pytest.mark.unit
class TestTrading212Normalize:
    def setup_method(self):
        self.adapter = Trading212Adapter()

    def test_normalize_position(self, t212_positions):
        for raw in t212_positions:
            result = self.adapter.normalize_position(raw)
            assert "broker_ticker" in result
            assert "quantity" in result
            assert result["quantity"] > 0

    def test_normalize_order(self, t212_orders):
        for raw in t212_orders["items"]:
            result = self.adapter.normalize_order(raw)
            assert "broker_order_id" in result
            assert result["side"] in ("buy", "sell")
            assert "status" in result
