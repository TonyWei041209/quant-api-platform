"""Unit tests for SEC adapter normalization."""
import pytest
from libs.adapters.sec_adapter import SECAdapter


@pytest.mark.unit
class TestSECAdapterNormalize:
    def setup_method(self):
        self.adapter = SECAdapter()

    def test_normalize_company_ticker(self):
        raw = {"cik_str": "320193", "ticker": "AAPL", "title": "Apple Inc."}
        result = self.adapter.normalize(raw)
        assert result["cik"] == "320193"
        assert result["ticker"] == "AAPL"
        assert result["issuer_name"] == "Apple Inc."

    def test_normalize_missing_fields(self):
        raw = {"cik_str": "999999"}
        result = self.adapter.normalize(raw)
        assert result["cik"] == "999999"
        assert result["ticker"] == ""

    def test_normalize_passthrough(self):
        raw = {"something": "else"}
        result = self.adapter.normalize(raw)
        assert result == raw

    def test_normalize_batch(self, sec_company_tickers):
        for key, entry in sec_company_tickers.items():
            result = self.adapter.normalize(entry)
            assert "cik" in result
            assert "ticker" in result
            assert "issuer_name" in result
