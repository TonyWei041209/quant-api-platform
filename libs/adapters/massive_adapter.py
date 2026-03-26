"""Massive / Polygon-style adapter — EOD bars, splits, dividends."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.rate_limit import RateLimiter


@dataclass
class MassiveAdapter(BaseAdapter):
    """Adapter for stock market aggregates API (e.g. Polygon / Massive)."""

    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=5, period_seconds=1.0))

    @property
    def name(self) -> str:
        return "massive"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _base_url(self) -> str:
        return "https://api.polygon.io"

    def _auth_params(self) -> dict[str, str]:
        settings = get_settings()
        return {"apiKey": settings.massive_api_key}

    async def fetch_json(self, path: str, **kwargs) -> Any:
        params = kwargs.pop("params", {})
        params.update(self._auth_params())
        return await super().fetch_json(path, params=params, **kwargs)

    async def get_eod_bars(
        self, ticker: str, from_date: str, to_date: str, adjusted: bool = False,
    ) -> list[dict]:
        """Fetch daily bars. IMPORTANT: adjusted=false for raw unadjusted prices."""
        params = {
            "adjusted": str(adjusted).lower(),
            "sort": "asc",
            "limit": "50000",
        }
        data = await self.fetch_json(
            f"/v2/aggs/ticker/{ticker}/range/1/day/{from_date}/{to_date}",
            params=params,
        )
        return data.get("results", [])

    async def get_splits(self, ticker: str) -> list[dict]:
        """Fetch stock splits."""
        data = await self.fetch_json(f"/v3/reference/splits", params={"ticker": ticker})
        return data.get("results", [])

    async def get_dividends(self, ticker: str) -> list[dict]:
        """Fetch cash dividends."""
        data = await self.fetch_json(f"/v3/reference/dividends", params={"ticker": ticker})
        return data.get("results", [])

    def normalize(self, raw: Any) -> Any:
        """Normalize a single bar to internal format."""
        if isinstance(raw, dict) and "o" in raw:
            return {
                "open": raw["o"],
                "high": raw["h"],
                "low": raw["l"],
                "close": raw["c"],
                "volume": raw.get("v", 0),
                "vwap": raw.get("vw"),
                "trade_date": raw.get("t"),  # unix ms
            }
        return raw

    def normalize_split(self, raw: dict) -> dict:
        """Normalize a split record."""
        return {
            "split_from": raw.get("split_from"),
            "split_to": raw.get("split_to"),
            "ex_date": raw.get("execution_date"),
        }

    def normalize_dividend(self, raw: dict) -> dict:
        """Normalize a dividend record."""
        return {
            "cash_amount": raw.get("cash_amount"),
            "currency": raw.get("currency", "USD"),
            "ex_date": raw.get("ex_dividend_date"),
            "pay_date": raw.get("pay_date"),
            "record_date": raw.get("record_date"),
        }
