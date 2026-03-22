"""Simple token-bucket rate limiter."""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """Token-bucket rate limiter for async HTTP clients."""

    max_requests: int
    period_seconds: float
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.max_requests)
        self._last_refill = time.monotonic()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(
                self.max_requests,
                self._tokens + elapsed * (self.max_requests / self.period_seconds),
            )
            self._last_refill = now

            if self._tokens < 1:
                wait = (1 - self._tokens) * (self.period_seconds / self.max_requests)
                await asyncio.sleep(wait)
                self._tokens = 0
            else:
                self._tokens -= 1
