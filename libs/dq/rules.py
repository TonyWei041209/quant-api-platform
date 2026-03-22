"""DQ rule runner — orchestrates all data quality checks."""
from __future__ import annotations

from sqlalchemy.orm import Session

from libs.core.logging import get_logger
from libs.dq.price_rules import check_ohlc_logic, check_non_negative_prices, check_trading_day_consistency
from libs.dq.corporate_action_rules import check_corporate_action_validity
from libs.dq.pit_rules import check_pit_reported_at
from libs.dq.filing_rules import check_duplicate_accession
from libs.dq.reporting import record_issue

logger = get_logger(__name__)

ALL_RULES = [
    ("DQ-1", "OHLC logic check", check_ohlc_logic),
    ("DQ-2", "Non-negative price/volume check", check_non_negative_prices),
    ("DQ-3", "Duplicate accession number check", check_duplicate_accession),
    ("DQ-4", "Trading day consistency check", check_trading_day_consistency),
    ("DQ-5", "Corporate action validity", check_corporate_action_validity),
    ("DQ-6", "PIT reported_at check", check_pit_reported_at),
]


def run_all_rules(session: Session) -> dict:
    """Run all DQ rules and record issues."""
    counters = {"rules_run": 0, "issues_found": 0, "rules_skipped": 0}

    for rule_code, description, check_fn in ALL_RULES:
        if check_fn is None:
            logger.info("dq.skip", rule=rule_code, reason="not implemented yet")
            counters["rules_skipped"] += 1
            continue

        try:
            issues = check_fn(session)
            for issue in issues:
                record_issue(session, rule_code=rule_code, **issue)
                counters["issues_found"] += 1
            counters["rules_run"] += 1
            logger.info("dq.rule_complete", rule=rule_code, issues=len(issues))
        except Exception as e:
            logger.error("dq.rule_error", rule=rule_code, error=str(e))

    session.commit()
    logger.info("dq.complete", **counters)
    return counters
