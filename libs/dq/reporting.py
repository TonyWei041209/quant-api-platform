"""DQ issue reporting — writes issues to data_issue table."""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from libs.core.ids import new_id
from libs.db.models.data_issue import DataIssue


def record_issue(
    session: Session,
    rule_code: str,
    severity: str,
    table_name: str,
    record_key: str | None = None,
    details: dict[str, Any] | None = None,
) -> DataIssue:
    """Record a DQ issue into the data_issue table."""
    issue = DataIssue(
        issue_id=new_id(),
        severity=severity,
        rule_code=rule_code,
        table_name=table_name,
        record_key=record_key,
        details=details,
    )
    session.add(issue)
    return issue
