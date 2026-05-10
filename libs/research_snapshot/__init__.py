"""Research snapshot persistence — append-only history for the
Scanner and the Overnight Market Brief.

The public surface (``persist_scanner_snapshot``,
``persist_market_brief_snapshot``) is wrapped in a try/except so
persistence failure NEVER breaks an API response — we still return the
research payload to the caller and log the failure.

Behaviour is gated by env flag ``FEATURE_RESEARCH_SNAPSHOT_WRITE``
(default: enabled in production, but flip-off-able via Cloud Run
revision env var).
"""
from libs.research_snapshot.snapshot_service import (
    SCHEMA_VERSION,
    is_snapshot_write_enabled,
    persist_market_brief_snapshot,
    persist_scanner_snapshot,
)

__all__ = [
    "SCHEMA_VERSION",
    "is_snapshot_write_enabled",
    "persist_market_brief_snapshot",
    "persist_scanner_snapshot",
]
