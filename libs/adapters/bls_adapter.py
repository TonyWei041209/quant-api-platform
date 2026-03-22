"""BLS adapter — Bureau of Labor Statistics. Skeleton for Phase 1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.rate_limit import RateLimiter


@dataclass
class BLSAdapter(BaseAdapter):
    """Skeleton adapter for BLS data. TODO: implement in Phase 2."""

    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=5, period_seconds=1.0))

    @property
    def name(self) -> str:
        return "bls"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _base_url(self) -> str:
        return "https://api.bls.gov/publicAPI/v2"

    async def get_series(self, series_ids: list[str], start_year: int, end_year: int) -> dict:
        """Fetch time series data. TODO: implement full pipeline."""
        settings = get_settings()
        payload = {
            "seriesid": series_ids,
            "startyear": str(start_year),
            "endyear": str(end_year),
            "registrationkey": settings.bls_api_key,
        }
        resp = await self.fetch("POST", "/timeseries/data/", json=payload)
        return resp.json()

    def normalize(self, raw: Any) -> Any:
        return raw
