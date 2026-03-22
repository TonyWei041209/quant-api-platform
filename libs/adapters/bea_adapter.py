"""BEA adapter — Bureau of Economic Analysis. Skeleton for Phase 1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.rate_limit import RateLimiter


@dataclass
class BEAAdapter(BaseAdapter):
    """Skeleton adapter for BEA data. TODO: implement in Phase 2."""

    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=5, period_seconds=1.0))

    @property
    def name(self) -> str:
        return "bea"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _base_url(self) -> str:
        return "https://apps.bea.gov/api/data"

    async def get_dataset_list(self) -> dict:
        """Fetch available datasets. TODO: implement full pipeline."""
        settings = get_settings()
        params = {"UserID": settings.bea_api_key, "method": "GETDATASETLIST", "ResultFormat": "JSON"}
        return await self.fetch_json("", params=params)

    def normalize(self, raw: Any) -> Any:
        return raw
