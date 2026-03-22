"""Unit tests for FMP adapter normalization."""
import pytest
from libs.adapters.fmp_adapter import FMPAdapter


@pytest.mark.unit
class TestFMPAdapterNormalize:
    def setup_method(self):
        self.adapter = FMPAdapter()

    def test_normalize_financial_income(self, fmp_income_statement):
        raw = fmp_income_statement[0]
        facts = self.adapter.normalize_financial(raw, "income")
        assert len(facts) > 0
        metric_codes = [f["metric_code"] for f in facts]
        assert "revenue" in metric_codes
        assert "netIncome" in metric_codes

    def test_normalize_financial_balance(self, fmp_balance_sheet):
        raw = fmp_balance_sheet[0]
        facts = self.adapter.normalize_financial(raw, "balance")
        assert len(facts) > 0
        metric_codes = [f["metric_code"] for f in facts]
        assert "totalAssets" in metric_codes

    def test_normalize_financial_cashflow(self, fmp_cashflow):
        raw = fmp_cashflow[0]
        facts = self.adapter.normalize_financial(raw, "cashflow")
        assert len(facts) > 0
        metric_codes = [f["metric_code"] for f in facts]
        assert "operatingCashFlow" in metric_codes

    def test_normalize_skips_metadata_fields(self, fmp_income_statement):
        raw = fmp_income_statement[0]
        facts = self.adapter.normalize_financial(raw, "income")
        metric_codes = [f["metric_code"] for f in facts]
        assert "date" not in metric_codes
        assert "symbol" not in metric_codes
        assert "fillingDate" not in metric_codes
