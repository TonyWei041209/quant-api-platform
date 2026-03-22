"""Base adapter with common functionality for all data source adapters."""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

import httpx

from libs.core.config import get_settings
from libs.core.exceptions import AdapterError, RateLimitExceeded
from libs.core.logging import get_logger
from libs.core.rate_limit import RateLimiter
from libs.core.retry import default_retry

logger = get_logger(__name__)


@dataclass
class BaseAdapter(abc.ABC):
    """Abstract base for all external data adapters."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def auth_mode(self) -> str:
        """e.g. 'api_key', 'user_agent', 'none'"""
        ...

    @abc.abstractmethod
    def rate_limiter(self) -> RateLimiter: ...

    @abc.abstractmethod
    def _build_headers(self) -> dict[str, str]: ...

    @abc.abstractmethod
    def _base_url(self) -> str: ...

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url(),
            headers=self._build_headers(),
            timeout=30.0,
        )

    @default_retry
    async def fetch(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        await self.rate_limiter().acquire()
        async with self._client() as client:
            resp = await client.request(method, path, **kwargs)
            if resp.status_code == 429:
                raise RateLimitExceeded(self.name, "Rate limit exceeded", {"status": 429})
            resp.raise_for_status()
            logger.info("adapter.fetch", adapter=self.name, path=path, status=resp.status_code)
            return resp

    async def fetch_json(self, path: str, **kwargs: Any) -> Any:
        resp = await self.fetch("GET", path, **kwargs)
        return resp.json()

    @abc.abstractmethod
    def normalize(self, raw: Any) -> Any:
        """Transform raw API response to internal representation."""
        ...

    def checkpoint_key(self, **kwargs: Any) -> str:
        """Build a key for tracking ingestion progress."""
        parts = [self.name] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return ":".join(parts)
