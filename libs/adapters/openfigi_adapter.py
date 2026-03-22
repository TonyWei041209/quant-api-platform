"""OpenFIGI adapter — identifier mapping."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.rate_limit import RateLimiter


@dataclass
class OpenFIGIAdapter(BaseAdapter):
    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=20, period_seconds=60.0))

    @property
    def name(self) -> str:
        return "openfigi"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        settings = get_settings()
        headers = {"Content-Type": "application/json"}
        if settings.openfigi_api_key:
            headers["X-OPENFIGI-APIKEY"] = settings.openfigi_api_key
        return headers

    def _base_url(self) -> str:
        return "https://api.openfigi.com"

    async def map_identifiers(self, jobs: list[dict]) -> list[dict]:
        """Map identifiers via /v3/mapping endpoint. Max 100 jobs per request."""
        resp = await self.fetch("POST", "/v3/mapping", json=jobs)
        return resp.json()

    async def map_ticker(self, ticker: str, exchange_code: str = "US") -> list[dict]:
        """Convenience: map a single ticker."""
        jobs = [{"idType": "TICKER", "idValue": ticker, "exchCode": exchange_code}]
        results = await self.map_identifiers(jobs)
        if results and isinstance(results[0], dict) and "data" in results[0]:
            return results[0]["data"]
        return []

    def normalize(self, raw: Any) -> Any:
        """Normalize OpenFIGI response to flat identifier records."""
        if isinstance(raw, dict) and "figi" in raw:
            return {
                "figi": raw.get("figi"),
                "composite_figi": raw.get("compositeFIGI"),
                "share_class_figi": raw.get("shareClassFIGI"),
                "name": raw.get("name"),
                "ticker": raw.get("ticker"),
                "exchange_code": raw.get("exchCode"),
                "market_sector": raw.get("marketSector"),
                "security_type": raw.get("securityType"),
            }
        return raw
