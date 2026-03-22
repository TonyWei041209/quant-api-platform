"""Sync macroeconomic data — Phase 1 skeleton.

TODO: Implement full macro pipeline in Phase 2 with:
- FRED API integration
- BEA GDP/PCE series
- BLS employment data
- Treasury rates
- Vintage/real-time support for PIT macro
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def sync_macro(session: Session) -> dict:
    """Skeleton for macro data sync. Phase 1: no-op with logging."""
    run = SourceRun(
        run_id=new_id(), source="macro", job_name="sync_macro",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"series_synced": 0, "observations_synced": 0}

    logger.info("sync_macro.skeleton", message="Macro sync is a Phase 1 skeleton. No data fetched.")

    # TODO: Implement BEA, BLS, Treasury adapters
    # TODO: Support realtime_start/realtime_end for PIT macro

    run.status = "success"
    run.finished_at = utc_now()
    run.counters = counters
    session.commit()

    return counters
