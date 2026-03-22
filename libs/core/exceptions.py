"""Application exceptions."""
from __future__ import annotations


class QunatPlatformError(Exception):
    """Base exception for the platform."""


class AdapterError(QunatPlatformError):
    """Error from a data adapter."""

    def __init__(self, adapter: str, message: str, raw: dict | None = None) -> None:
        self.adapter = adapter
        self.raw = raw
        super().__init__(f"[{adapter}] {message}")


class RateLimitExceeded(AdapterError):
    """Rate limit hit on an external API."""


class DataQualityError(QunatPlatformError):
    """A data quality check failed."""


class ExecutionPolicyError(QunatPlatformError):
    """An execution policy violation."""


class LiveSubmitDisabledError(ExecutionPolicyError):
    """Live submit is disabled by feature flag."""

    def __init__(self) -> None:
        super().__init__("Live order submission is disabled by policy (FEATURE_T212_LIVE_SUBMIT=false)")
