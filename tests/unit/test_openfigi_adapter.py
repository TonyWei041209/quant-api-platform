"""Unit tests for OpenFIGI adapter normalization."""
import pytest
from libs.adapters.openfigi_adapter import OpenFIGIAdapter


@pytest.mark.unit
class TestOpenFIGIAdapterNormalize:
    def setup_method(self):
        self.adapter = OpenFIGIAdapter()

    def test_normalize_figi_response(self):
        raw = {
            "figi": "BBG000B9XRY4",
            "compositeFIGI": "BBG000B9XRY4",
            "shareClassFIGI": "BBG001S5N8V8",
            "name": "APPLE INC",
            "ticker": "AAPL",
            "exchCode": "US",
            "marketSector": "Equity",
            "securityType": "Common Stock",
        }
        result = self.adapter.normalize(raw)
        assert result["figi"] == "BBG000B9XRY4"
        assert result["composite_figi"] == "BBG000B9XRY4"
        assert result["share_class_figi"] == "BBG001S5N8V8"
        assert result["ticker"] == "AAPL"

    def test_normalize_batch(self, openfigi_mapping):
        for entry in openfigi_mapping:
            if "data" in entry:
                for item in entry["data"]:
                    result = self.adapter.normalize(item)
                    assert "figi" in result
