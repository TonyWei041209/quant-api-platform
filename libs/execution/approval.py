"""Approval gate for order execution.

Flow: signal -> intent -> draft -> approval -> submit
Strategy code MUST NOT directly call broker submit.
"""
from __future__ import annotations

from libs.core.logging import get_logger

logger = get_logger(__name__)


def validate_approval(draft) -> tuple[bool, str]:
    """Validate that a draft is ready for submission.

    Returns (is_valid, reason).
    """
    if draft.status != "approved":
        return False, f"Draft status is '{draft.status}', must be 'approved'"
    if draft.approved_at is None:
        return False, "Draft has not been approved (approved_at is null)"
    if draft.qty <= 0:
        return False, "Order quantity must be positive"
    return True, "OK"
