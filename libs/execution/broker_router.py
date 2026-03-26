"""Broker router — routes approved drafts to the correct broker adapter.

CRITICAL POLICY:
- Strategy code MUST NOT call broker submit directly
- All submissions go through: intent -> draft -> approval -> risk_check -> submit
- Live submit is disabled by default (FEATURE_T212_LIVE_SUBMIT=false)
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from libs.adapters.trading212_adapter import Trading212Adapter
from libs.core.config import get_settings
from libs.core.exceptions import ExecutionPolicyError, LiveSubmitDisabledError
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.execution.approval import validate_approval
from libs.execution.risk_checks import pre_submit_risk_check

logger = get_logger(__name__)


async def submit_draft(session: Session, draft) -> dict:
    """Submit an approved draft to the broker.

    This is the ONLY approved path for order submission.
    """
    # Validate approval
    is_valid, reason = validate_approval(draft)
    if not is_valid:
        raise ExecutionPolicyError(f"Draft not approved: {reason}")

    # Risk checks
    passed, risk_reason = pre_submit_risk_check(draft)
    if not passed:
        raise ExecutionPolicyError(f"Risk check failed: {risk_reason}")

    settings = get_settings()

    if draft.broker == "trading212":
        use_demo = not draft.is_live_enabled
        if draft.is_live_enabled and not settings.feature_t212_live_submit:
            raise LiveSubmitDisabledError()

        adapter = Trading212Adapter(use_demo=use_demo)

        # Resolve ticker from instrument_id via identifier table
        from sqlalchemy import text as sa_text
        ticker_row = session.execute(
            sa_text("SELECT id_value FROM instrument_identifier WHERE instrument_id = :iid AND id_type = 'ticker' AND is_primary = true LIMIT 1"),
            {"iid": str(draft.intent.instrument_id) if hasattr(draft, 'intent') and draft.intent else None}
        ).fetchone()
        broker_ticker = ticker_row[0] if ticker_row else ""

        if draft.order_type == "limit":
            result = await adapter.submit_limit_order(
                ticker=broker_ticker,
                qty=float(draft.qty),
                limit_price=float(draft.limit_price),
            )
        elif draft.order_type == "market":
            result = await adapter.submit_market_order(
                ticker=broker_ticker,
                qty=float(draft.qty),
            )
        else:
            raise ExecutionPolicyError(f"Unsupported order type: {draft.order_type}")

        draft.submitted_at = utc_now()
        draft.status = "submitted"
        session.flush()

        logger.info("broker_router.submitted", draft_id=str(draft.draft_id), broker="trading212")
        return result
    else:
        raise ExecutionPolicyError(f"Unknown broker: {draft.broker}")
