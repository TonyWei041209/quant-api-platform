"""Financial Modeling Prep adapter — prices, financials, earnings.

Uses the FMP 'stable' API endpoints (not legacy v3).
Docs: https://site.financialmodelingprep.com/developer/docs/stable
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.rate_limit import RateLimiter


@dataclass
class FMPAdapter(BaseAdapter):
    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=5, period_seconds=1.0))

    @property
    def name(self) -> str:
        return "fmp"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _base_url(self) -> str:
        return "https://financialmodelingprep.com"

    def _auth_params(self) -> dict[str, str]:
        settings = get_settings()
        return {"apikey": settings.fmp_api_key}

    async def fetch_json(self, path: str, **kwargs: Any) -> Any:
        params = kwargs.pop("params", {})
        params.update(self._auth_params())
        return await super().fetch_json(path, params=params, **kwargs)

    # ---- Price Data ----

    async def get_eod_prices(self, symbol: str, from_date: str = "", to_date: str = "") -> list[dict]:
        """Fetch historical daily prices via stable API.

        Returns list of {date, open, high, low, close, volume, ...}.
        NOTE: FMP stable returns split-adjusted data by default.
        We tag source='fmp' and must handle adjustment separately.
        """
        params: dict[str, str] = {"symbol": symbol}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        data = await self.fetch_json("/stable/historical-price-eod/full", params=params)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("historical", [data] if "date" in data else [])
        return []

    async def get_profile(self, symbol: str) -> dict:
        """Fetch company profile via stable API."""
        data = await self.fetch_json("/stable/profile", params={"symbol": symbol})
        if isinstance(data, dict):
            return data
        if isinstance(data, list) and data:
            return data[0]
        return {}

    # ---- Financial Statements ----

    async def get_income_statement(self, symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
        """Fetch income statements via stable API."""
        data = await self.fetch_json(
            "/stable/income-statement",
            params={"symbol": symbol, "period": period, "limit": str(limit)},
        )
        return data if isinstance(data, list) else []

    async def get_balance_sheet(self, symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
        """Fetch balance sheet via stable API."""
        data = await self.fetch_json(
            "/stable/balance-sheet-statement",
            params={"symbol": symbol, "period": period, "limit": str(limit)},
        )
        return data if isinstance(data, list) else []

    async def get_cash_flow(self, symbol: str, period: str = "annual", limit: int = 5) -> list[dict]:
        """Fetch cash flow statement via stable API."""
        data = await self.fetch_json(
            "/stable/cash-flow-statement",
            params={"symbol": symbol, "period": period, "limit": str(limit)},
        )
        return data if isinstance(data, list) else []

    # ---- Earnings (may require paid plan) ----

    async def get_earnings_calendar(self, from_date: str = "", to_date: str = "") -> list[dict]:
        """Fetch earnings calendar.

        NOTE: May return 404 on free tier. Caller should handle gracefully.
        """
        params: dict[str, str] = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        try:
            data = await self.fetch_json("/stable/earning-calendar", params=params)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    # ---- Normalization ----

    def normalize(self, raw: Any) -> Any:
        """Normalize FMP financial data to internal metric format."""
        return raw

    def normalize_price(self, raw: dict) -> dict:
        """Normalize a single price bar to internal format."""
        return {
            "trade_date": raw.get("date"),
            "open": raw.get("open"),
            "high": raw.get("high"),
            "low": raw.get("low"),
            "close": raw.get("close"),
            "volume": raw.get("volume", 0),
            "vwap": raw.get("vwap"),
        }

    def normalize_financial(self, raw: dict, statement_type: str) -> list[dict]:
        """Normalize a financial statement to long-form facts."""
        skip_keys = {
            "date", "symbol", "reportedCurrency", "cik", "fillingDate",
            "acceptedDate", "calendarYear", "period", "link", "finalLink",
        }
        facts = []
        for key, value in raw.items():
            if key in skip_keys or value is None:
                continue
            try:
                numeric_value = float(value)
            except (ValueError, TypeError):
                continue
            facts.append({
                "statement_type": statement_type,
                "metric_code": key,
                "metric_value": numeric_value,
                "unit": raw.get("reportedCurrency", "USD"),
            })
        return facts
