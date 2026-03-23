"""Pre-submission risk checks.

All checks run BEFORE order submission. Any failure blocks the submit.
"""
from __future__ import annotations

from datetime import date, datetime, UTC

from sqlalchemy import text
from sqlalchemy.orm import Session

from libs.core.config import get_settings
from libs.core.logging import get_logger

logger = get_logger(__name__)


class RiskCheckResult:
    """Result of a risk check."""
    def __init__(self, passed: bool, reason: str, rule: str):
        self.passed = passed
        self.reason = reason
        self.rule = rule

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"RiskCheck({status}: {self.rule} — {self.reason})"


def check_positive_quantity(draft) -> RiskCheckResult:
    """Quantity must be positive."""
    if draft.qty <= 0:
        return RiskCheckResult(False, f"Quantity {draft.qty} must be positive", "positive_qty")
    return RiskCheckResult(True, "OK", "positive_qty")


def check_limit_price_required(draft) -> RiskCheckResult:
    """Limit orders must have a limit price."""
    if draft.order_type == "limit" and draft.limit_price is None:
        return RiskCheckResult(False, "Limit order requires limit_price", "limit_price_required")
    if draft.order_type == "stop" and draft.stop_price is None:
        return RiskCheckResult(False, "Stop order requires stop_price", "stop_price_required")
    return RiskCheckResult(True, "OK", "limit_price_required")


def check_max_position_size(draft, max_qty: float = 10000) -> RiskCheckResult:
    """Single order quantity must not exceed max_qty."""
    if float(draft.qty) > max_qty:
        return RiskCheckResult(False, f"Qty {draft.qty} exceeds max {max_qty}", "max_position_size")
    return RiskCheckResult(True, "OK", "max_position_size")


def check_max_notional(draft, max_notional: float = 1_000_000) -> RiskCheckResult:
    """Order notional value must not exceed max_notional."""
    price = float(draft.limit_price or 0)
    if price == 0:
        return RiskCheckResult(True, "No price to check (market order)", "max_notional")
    notional = float(draft.qty) * price
    if notional > max_notional:
        return RiskCheckResult(False, f"Notional ${notional:,.0f} exceeds max ${max_notional:,.0f}", "max_notional")
    return RiskCheckResult(True, "OK", "max_notional")


def check_duplicate_order(session: Session, draft) -> RiskCheckResult:
    """Prevent duplicate orders: no other pending/approved draft for same intent."""
    from libs.db.models.order_draft import OrderDraft
    existing = session.query(OrderDraft).filter(
        OrderDraft.intent_id == draft.intent_id,
        OrderDraft.draft_id != draft.draft_id,
        OrderDraft.status.in_(["pending_approval", "approved", "submitted"]),
    ).count()
    if existing > 0:
        return RiskCheckResult(False, f"Found {existing} active draft(s) for same intent", "duplicate_order")
    return RiskCheckResult(True, "OK", "duplicate_order")


def check_stale_intent(session: Session, draft, max_age_hours: int = 24) -> RiskCheckResult:
    """Reject orders from stale intents (older than max_age_hours)."""
    from libs.db.models.order_intent import OrderIntent
    intent = session.get(OrderIntent, draft.intent_id)
    if intent is None:
        return RiskCheckResult(False, "Intent not found", "stale_intent")

    now = datetime.now(UTC)
    age = now - intent.created_at.replace(tzinfo=UTC)
    if age.total_seconds() > max_age_hours * 3600:
        hours = age.total_seconds() / 3600
        return RiskCheckResult(False, f"Intent is {hours:.1f}h old (max {max_age_hours}h)", "stale_intent")
    return RiskCheckResult(True, "OK", "stale_intent")


def check_trading_day(session: Session) -> RiskCheckResult:
    """Check if today is a trading day."""
    today = date.today()
    result = session.execute(text(
        "SELECT is_open FROM exchange_calendar "
        "WHERE exchange = 'NYSE' AND trade_date = :today"
    ), {"today": today}).fetchone()

    if result is None:
        return RiskCheckResult(True, "No calendar data for today, allowing", "trading_day")
    if not result[0]:
        return RiskCheckResult(False, f"Market is closed on {today}", "trading_day")
    return RiskCheckResult(True, "OK", "trading_day")


def pre_submit_risk_check(
    session: Session,
    draft,
    max_qty: float = 10000,
    max_notional: float = 1_000_000,
    max_intent_age_hours: int = 24,
) -> tuple[bool, list[RiskCheckResult]]:
    """Run all risk checks. Returns (all_passed, results_list)."""
    results = [
        check_positive_quantity(draft),
        check_limit_price_required(draft),
        check_max_position_size(draft, max_qty),
        check_max_notional(draft, max_notional),
        check_duplicate_order(session, draft),
        check_stale_intent(session, draft, max_intent_age_hours),
        check_trading_day(session),
    ]

    all_passed = all(r.passed for r in results)

    for r in results:
        if not r.passed:
            logger.warning("risk_check.failed", rule=r.rule, reason=r.reason)
        else:
            logger.debug("risk_check.passed", rule=r.rule)

    return all_passed, results
