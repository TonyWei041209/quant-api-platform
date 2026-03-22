"""Sync Trading 212 read-only data (account, positions, orders)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from libs.adapters.trading212_adapter import Trading212Adapter
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.core.time import utc_now
from libs.db.models.broker_account_snapshot import BrokerAccountSnapshot
from libs.db.models.broker_position_snapshot import BrokerPositionSnapshot
from libs.db.models.broker_order_snapshot import BrokerOrderSnapshot
from libs.db.models.source_run import SourceRun

logger = get_logger(__name__)


async def sync_trading212_readonly(session: Session, use_demo: bool = True) -> dict:
    """Sync account, positions, and orders from Trading 212 (read-only)."""
    run = SourceRun(
        run_id=new_id(), source="trading212", job_name="sync_trading212_readonly",
        started_at=utc_now(), status="running",
    )
    session.add(run)
    session.flush()

    counters = {"account_snapshots": 0, "positions": 0, "orders": 0, "errors": 0}

    try:
        adapter = Trading212Adapter(use_demo=use_demo)

        # Account snapshot
        try:
            cash = await adapter.get_account_cash()
            info = await adapter.get_account_info()
            session.add(BrokerAccountSnapshot(
                snapshot_id=new_id(),
                broker="trading212",
                account_id=str(info.get("id", "unknown")),
                cash_free=cash.get("free"),
                cash_total=cash.get("total"),
                portfolio_value=cash.get("pplValue"),
                currency=info.get("currencyCode", "USD"),
                raw_payload={"cash": cash, "info": info},
            ))
            counters["account_snapshots"] += 1
        except Exception as e:
            counters["errors"] += 1
            logger.error("sync_t212.account_error", error=str(e))

        # Positions
        try:
            positions = await adapter.get_positions()
            for raw in positions:
                norm = adapter.normalize_position(raw)
                session.add(BrokerPositionSnapshot(
                    snapshot_id=new_id(),
                    broker="trading212",
                    account_id="default",
                    broker_ticker=norm.get("broker_ticker"),
                    quantity=norm.get("quantity", 0),
                    avg_cost=norm.get("avg_cost"),
                    current_price=norm.get("current_price"),
                    market_value=norm.get("market_value"),
                    pnl=norm.get("pnl"),
                    raw_payload=raw,
                ))
                counters["positions"] += 1
        except Exception as e:
            counters["errors"] += 1
            logger.error("sync_t212.positions_error", error=str(e))

        # Orders
        try:
            orders = await adapter.get_orders()
            for raw in orders:
                norm = adapter.normalize_order(raw)
                session.add(BrokerOrderSnapshot(
                    snapshot_id=new_id(),
                    broker="trading212",
                    account_id="default",
                    broker_order_id=norm.get("broker_order_id", ""),
                    broker_ticker=norm.get("broker_ticker"),
                    side=norm.get("side", "buy"),
                    order_type=norm.get("order_type", "unknown"),
                    qty=norm.get("qty", 0),
                    filled_qty=norm.get("filled_qty"),
                    avg_fill_price=norm.get("avg_fill_price"),
                    status=norm.get("status", "unknown"),
                    raw_payload=raw,
                ))
                counters["orders"] += 1
        except Exception as e:
            counters["errors"] += 1
            logger.error("sync_t212.orders_error", error=str(e))

        session.commit()
        run.status = "success"
        run.finished_at = utc_now()
        run.counters = counters
        session.commit()
        logger.info("sync_t212.complete", **counters)

    except Exception as e:
        run.status = "failed"
        run.error_message = str(e)
        run.finished_at = utc_now()
        session.commit()
        raise

    return counters
