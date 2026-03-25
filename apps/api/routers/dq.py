"""Data-quality endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.db.models.data_issue import DataIssue
from libs.db.models.source_run import SourceRun

router = APIRouter()


@router.get("/issues")
def list_issues(
    limit: int = Query(100, ge=1, le=1000),
    severity: Optional[str] = Query(None),
    resolved: Optional[bool] = Query(None),
    db: Session = Depends(get_sync_db),
) -> dict:
    q = db.query(DataIssue)
    if severity is not None:
        q = q.filter(DataIssue.severity == severity.upper())
    if resolved is not None:
        q = q.filter(DataIssue.resolved_flag == resolved)
    total = q.count()
    items = q.order_by(DataIssue.issue_time.desc()).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "issue_id": str(i.issue_id),
                "issue_time": str(i.issue_time),
                "severity": i.severity,
                "rule_code": i.rule_code,
                "table_name": i.table_name,
                "record_key": i.record_key,
                "details": i.details,
                "resolved_flag": i.resolved_flag,
            }
            for i in items
        ],
    }


@router.get("/source-runs")
def list_source_runs(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_sync_db),
) -> dict:
    total = db.query(SourceRun).count()
    items = db.query(SourceRun).order_by(SourceRun.started_at.desc()).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "run_id": str(r.run_id),
                "source": r.source,
                "job_name": r.job_name,
                "started_at": str(r.started_at),
                "finished_at": str(r.finished_at) if r.finished_at else None,
                "status": r.status,
                "counters": r.counters,
                "error_message": r.error_message,
            }
            for r in items
        ],
    }


@router.post("/run")
def run_dq(db: Session = Depends(get_sync_db)) -> dict:
    from libs.dq.rules import run_all_rules

    counters = run_all_rules(db)
    return {"status": "completed", "summary": counters}
