"""Unit tests for Massive/Polygon adapter normalization."""
import pytest
from libs.adapters.massive_adapter import MassiveAdapter


@pytest.mark.unit
class TestMassiveAdapterNormalize:
    def setup_method(self):
        self.adapter = MassiveAdapter()

    def test_normalize_bar(self):
        raw = {"o": 184.50, "h": 186.80, "l": 183.90, "c": 186.10, "v": 52345678, "vw": 185.23, "t": 1704067200000}
        result = self.adapter.normalize(raw)
        assert result["open"] == 184.50
        assert result["high"] == 186.80
        assert result["low"] == 183.90
        assert result["close"] == 186.10
        assert result["volume"] == 52345678
        assert result["vwap"] == 185.23

    def test_normalize_split(self):
        raw = {"split_from": 1, "split_to": 4, "execution_date": "2020-08-31"}
        result = self.adapter.normalize_split(raw)
        assert result["split_from"] == 1
        assert result["split_to"] == 4
        assert result["ex_date"] == "2020-08-31"

    def test_normalize_dividend(self):
        raw = {"cash_amount": 0.25, "currency": "USD", "ex_dividend_date": "2024-02-09", "pay_date": "2024-02-15", "record_date": "2024-02-12"}
        result = self.adapter.normalize_dividend(raw)
        assert result["cash_amount"] == 0.25
        assert result["ex_date"] == "2024-02-09"

    def test_normalize_batch_bars(self, massive_eod_bars):
        for bar in massive_eod_bars["results"]:
            result = self.adapter.normalize(bar)
            assert result["open"] > 0
            assert result["high"] >= result["low"]
