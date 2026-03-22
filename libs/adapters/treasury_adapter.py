"""Treasury adapter — US Treasury fiscal data. Skeleton for Phase 1."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.rate_limit import RateLimiter


@dataclass
class TreasuryAdapter(BaseAdapter):
    """Skeleton adapter for Treasury fiscal data. TODO: implement in Phase 2."""

    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=5, period_seconds=1.0))

    @property
    def name(self) -> str:
        return "treasury"

    @property
    def auth_mode(self) -> str:
        return "none"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        return {"Accept": "application/json"}

    def _base_url(self) -> str:
        settings = get_settings()
        return settings.treasury_api_base_url

    async def get_treasury_rates(self, page_size: int = 100) -> dict:
        """Fetch average interest rates. TODO: implement full pipeline."""
        return await self.fetch_json(
            "/v2/accounting/od/avg_interest_rates",
            params={"page[size]": str(page_size), "sort": "-record_date"},
        )

    def normalize(self, raw: Any) -> Any:
        return raw
