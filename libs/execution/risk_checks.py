"""Pre-submission risk checks.

Phase 1: basic sanity checks.
TODO Phase 2: position limits, sector concentration, drawdown limits.
"""
from __future__ import annotations

from libs.core.logging import get_logger

logger = get_logger(__name__)


def pre_submit_risk_check(draft, account_snapshot=None) -> tuple[bool, str]:
    """Run risk checks before order submission.

    Returns (passed, reason).
    """
    # Basic sanity
    if draft.qty <= 0:
        return False, "Quantity must be positive"
    if draft.order_type == "limit" and draft.limit_price is None:
        return False, "Limit order requires a limit price"
    if draft.order_type == "stop" and draft.stop_price is None:
        return False, "Stop order requires a stop price"

    # TODO: Check position limits
    # TODO: Check account buying power
    # TODO: Check sector concentration
    # TODO: Check max order value

    logger.info("risk_check.passed", draft_id=str(draft.draft_id))
    return True, "All risk checks passed"
