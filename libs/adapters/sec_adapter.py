"""SEC EDGAR adapter — company tickers, submissions, companyfacts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.logging import get_logger
from libs.core.rate_limit import RateLimiter
from libs.core.retry import default_retry

logger = get_logger(__name__)


@dataclass
class SECAdapter(BaseAdapter):
    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=10, period_seconds=1.0))

    @property
    def name(self) -> str:
        return "sec"

    @property
    def auth_mode(self) -> str:
        return "user_agent"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "User-Agent": settings.sec_user_agent or "QuantPlatform admin@example.com",
            "Accept": "application/json",
        }

    def _base_url(self) -> str:
        return "https://data.sec.gov"

    @default_retry
    async def _fetch_absolute(self, url: str) -> Any:
        """Fetch from an absolute URL (for www.sec.gov endpoints)."""
        await self.rate_limiter().acquire()
        async with httpx.AsyncClient(headers=self._build_headers(), timeout=30.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()

    async def get_company_tickers(self) -> list[dict]:
        """Fetch company_tickers.json from SEC (served from www.sec.gov)."""
        data = await self._fetch_absolute("https://www.sec.gov/files/company_tickers.json")
        return list(data.values()) if isinstance(data, dict) else data

    async def get_company_tickers_exchange(self) -> list[dict]:
        """Fetch company_tickers_exchange.json."""
        data = await self._fetch_absolute("https://www.sec.gov/files/company_tickers_exchange.json")
        if isinstance(data, dict) and "data" in data:
            fields = data.get("fields", [])
            return [dict(zip(fields, row)) for row in data["data"]]
        return data if isinstance(data, list) else []

    async def get_submissions(self, cik: str) -> dict:
        """Fetch submissions for a CIK."""
        cik_padded = cik.zfill(10)
        return await self.fetch_json(f"/submissions/CIK{cik_padded}.json")

    async def get_company_facts(self, cik: str) -> dict:
        """Fetch companyfacts for a CIK."""
        cik_padded = cik.zfill(10)
        return await self.fetch_json(f"/api/xbrl/companyfacts/CIK{cik_padded}.json")

    def normalize(self, raw: Any) -> Any:
        """Normalize SEC company ticker entry to internal format."""
        if isinstance(raw, dict) and "cik_str" in raw:
            return {
                "cik": str(raw["cik_str"]),
                "ticker": raw.get("ticker", ""),
                "issuer_name": raw.get("title", ""),
            }
        return raw
