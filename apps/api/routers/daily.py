"""Daily Brief API — what's worth looking at today."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.api.deps import get_sync_db
from libs.db.models.data_issue import DataIssue
from libs.db.models.earnings_event import EarningsEvent
from libs.db.models.instrument import Instrument
from libs.db.models.price_bar_raw import PriceBarRaw
from libs.db.models.source_run import SourceRun

router = APIRouter()


@router.get("/brief")
def daily_brief(db: Session = Depends(get_sync_db)):
    """Daily research brief — what's worth looking at today."""
    now = datetime.now(timezone.utc)
    today = now.date()

    # Data freshness
    total_instruments = db.query(Instrument).filter(Instrument.is_active == True).count()  # noqa: E712
    total_price_bars = db.query(func.count(PriceBarRaw.instrument_id)).scalar() or 0
    latest_bar_date = db.query(func.max(PriceBarRaw.trade_date)).scalar()

    # Instrument names for context
    active_instruments = db.query(Instrument).filter(Instrument.is_active == True).limit(10).all()
    instrument_names = [i.issuer_name_current for i in active_instruments]

    # Recent source runs
    recent_runs = db.query(SourceRun).order_by(SourceRun.started_at.desc()).limit(5).all()
    runs_summary = [{
        "run_id": str(r.run_id),
        "source": r.source,
        "job_name": r.job_name,
        "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "counters": r.counters,
    } for r in recent_runs]

    # DQ status
    unresolved_issues = db.query(DataIssue).filter(DataIssue.resolved_flag == False).count()  # noqa: E712

    # Upcoming earnings (next 7 days)
    upcoming_earnings = (
        db.query(EarningsEvent, Instrument)
        .join(Instrument, EarningsEvent.instrument_id == Instrument.instrument_id)
        .filter(EarningsEvent.report_date >= today)
        .filter(EarningsEvent.report_date <= today + timedelta(days=7))
        .order_by(EarningsEvent.report_date)
        .limit(20)
        .all()
    )
    earnings_list = [{
        "instrument_id": str(e.instrument_id),
        "issuer_name": inst.issuer_name_current,
        "report_date": str(e.report_date),
        "event_time_code": e.event_time_code,
        "eps_estimate": float(e.eps_estimate) if e.eps_estimate else None,
        "eps_actual": float(e.eps_actual) if e.eps_actual else None,
    } for e, inst in upcoming_earnings]

    # Recent backtests
    try:
        from libs.db.models.backtest import BacktestRun

        recent_bt = db.query(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(5).all()
        bt_list = [{
            "run_id": str(r.run_id),
            "strategy_name": r.strategy_name,
            "total_return": float(r.total_return) if r.total_return is not None else None,
            "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio is not None else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in recent_bt]
    except Exception:
        bt_list = []

    # Pending execution items
    from libs.db.models.order_draft import OrderDraft
    from libs.db.models.order_intent import OrderIntent

    pending_intents = db.query(OrderIntent).filter(OrderIntent.status == "pending").count()
    pending_drafts = db.query(OrderDraft).filter(OrderDraft.status == "pending_approval").count()

    return {
        "generated_at": now.isoformat(),
        "data_status": {
            "total_instruments": total_instruments,
            "total_price_bars": total_price_bars,
            "instrument_names": instrument_names,
            "latest_bar_date": str(latest_bar_date) if latest_bar_date else None,
            "data_freshness": "current" if latest_bar_date and (today - latest_bar_date).days <= 7 else "stale",
            "days_since_update": (today - latest_bar_date).days if latest_bar_date else None,
        },
        "dq_status": {
            "unresolved_issues": unresolved_issues,
            "status": "clean" if unresolved_issues == 0 else "issues_found",
        },
        "upcoming_earnings": earnings_list,
        "recent_source_runs": runs_summary,
        "recent_backtests": bt_list,
        "execution_status": {
            "pending_intents": pending_intents,
            "pending_drafts": pending_drafts,
        },
    }


@router.get("/recent-activity")
def recent_activity(limit: int = 20, db: Session = Depends(get_sync_db)):
    """Recent platform activity — what happened recently."""
    activities = []

    # Recent source runs
    recent_runs = db.query(SourceRun).order_by(SourceRun.started_at.desc()).limit(5).all()
    for r in recent_runs:
        activities.append({
            "type": "ingestion",
            "title": f"{r.job_name or r.source}",
            "detail": f"Status: {r.status}",
            "timestamp": r.started_at.isoformat() if r.started_at else None,
        })

    # Recent backtests
    try:
        from libs.db.models.backtest import BacktestRun

        recent_bt = db.query(BacktestRun).order_by(BacktestRun.created_at.desc()).limit(5).all()
        for r in recent_bt:
            ret = f"{r.total_return * 100:.1f}%" if r.total_return is not None else "--"
            activities.append({
                "type": "backtest",
                "title": f"Backtest: {r.strategy_name}",
                "detail": f"Return: {ret}",
                "timestamp": r.created_at.isoformat() if r.created_at else None,
            })
    except Exception:
        pass

    # Recent notes
    try:
        from libs.db.models.research_note import ResearchNote

        recent_notes = db.query(ResearchNote).order_by(ResearchNote.created_at.desc()).limit(5).all()
        for n in recent_notes:
            activities.append({
                "type": "note",
                "title": f"Note: {n.title}",
                "detail": n.note_type,
                "timestamp": n.created_at.isoformat() if n.created_at else None,
            })
    except Exception:
        pass

    # Recent presets used
    try:
        from libs.db.models.saved_preset import SavedPreset

        recent_presets = db.query(SavedPreset).filter(
            SavedPreset.last_used_at.isnot(None)
        ).order_by(SavedPreset.last_used_at.desc()).limit(5).all()
        for p in recent_presets:
            activities.append({
                "type": "preset",
                "title": f"Preset: {p.name}",
                "detail": f"{p.preset_type} · used {p.use_count}x",
                "timestamp": p.last_used_at.isoformat() if p.last_used_at else None,
                "context": {"preset_id": str(p.preset_id), "preset_type": p.preset_type},
            })
    except Exception:
        pass

    # Sort by timestamp desc
    activities.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return {"items": activities[:limit]}
