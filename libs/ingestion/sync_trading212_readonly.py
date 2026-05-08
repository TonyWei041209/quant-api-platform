"""Sync Trading 212 read-only data (account, positions, orders)."""
from __future__ import annotations

from sqlalchemy import text as sql_text
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


def _build_ticker_map(session: Session) -> dict[str, str]:
    """Build a mapping from normalized ticker → instrument_id using ticker_history + identifiers."""
    ticker_map: dict[str, str] = {}
    # From ticker_history (canonical)
    rows = session.execute(sql_text(
        "SELECT ticker, instrument_id FROM ticker_history WHERE ticker IS NOT NULL"
    )).fetchall()
    for row in rows:
        ticker_map[row[0].upper()] = str(row[1])
    # From instrument_identifier type=ticker
    rows = session.execute(sql_text(
        "SELECT id_value, instrument_id FROM instrument_identifier WHERE id_type = 'ticker' AND id_value IS NOT NULL"
    )).fetchall()
    for row in rows:
        ticker_map[row[0].upper()] = str(row[1])
    return ticker_map


def _resolve_instrument_id(broker_ticker: str | None, ticker_map: dict[str, str]) -> str | None:
    """Extract a standard ticker from T212 broker_ticker format and look up instrument_id.

    T212 format: {TICKER}_{EXCHANGE}_{TYPE} e.g. NVDA_US_EQ, SMSNl_EQ
    """
    if not broker_ticker:
        return None
    # Split on _ and take first segment as ticker candidate
    parts = broker_ticker.split("_")
    ticker = parts[0].upper()
    if ticker in ticker_map:
        return ticker_map[ticker]
    # Try the full broker_ticker as-is (unlikely but safe)
    if broker_ticker.upper() in ticker_map:
        return ticker_map[broker_ticker.upper()]
    return None


async def sync_trading212_readonly(session: Session, use_demo: bool = False) -> dict:
    """Sync account, positions, and orders from Trading 212 (read-only).

    Every position row written in a single call shares the same
    `sync_session_id` UUID. This lets `get_portfolio_summary()` return only
    the most recent snapshot-set, eliminating ghost positions from tickers
    that were closed between syncs (T212 only returns currently-held
    positions, so closed ones never get a qty=0 marker on their own).
    """
    sync_session_id = new_id()
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
            summary = await adapter.get_account_summary()
            session.add(BrokerAccountSnapshot(
                snapshot_id=new_id(),
                broker="trading212",
                account_id=str(summary.get("id", "default")),
                cash_free=summary.get("cash", {}).get("free") if isinstance(summary.get("cash"), dict) else summary.get("free"),
                cash_total=summary.get("cash", {}).get("total") if isinstance(summary.get("cash"), dict) else summary.get("total"),
                portfolio_value=summary.get("totalValue") or summary.get("portfolio_value"),
                currency=summary.get("currencyCode", "USD"),
                raw_payload=summary,
            ))
            counters["account_snapshots"] += 1
        except Exception as e:
            counters["errors"] += 1
            logger.error("sync_t212.account_error", error=str(e))

        # Positions — with instrument_id mapping; all rows share sync_session_id
        try:
            ticker_map = _build_ticker_map(session)
            positions = await adapter.get_positions()
            mapped = 0
            unmapped_tickers = []
            for raw in positions:
                norm = adapter.normalize_position(raw)
                bt = norm.get("broker_ticker")
                inst_id = _resolve_instrument_id(bt, ticker_map)
                if inst_id:
                    mapped += 1
                else:
                    unmapped_tickers.append(bt)
                session.add(BrokerPositionSnapshot(
                    snapshot_id=new_id(),
                    broker="trading212",
                    account_id="default",
                    instrument_id=inst_id,
                    broker_ticker=bt,
                    quantity=norm.get("quantity", 0),
                    avg_cost=norm.get("avg_cost"),
                    current_price=norm.get("current_price"),
                    market_value=norm.get("current_value") or (
                        (norm.get("quantity", 0) or 0) * (norm.get("current_price", 0) or 0)
                    ),
                    pnl=norm.get("pnl"),
                    sync_session_id=sync_session_id,
                    raw_payload=raw,
                ))
                counters["positions"] += 1
            if unmapped_tickers:
                logger.warning("sync_t212.unmapped_tickers", tickers=unmapped_tickers, mapped=mapped, total=len(positions))
            else:
                logger.info("sync_t212.all_mapped", mapped=mapped)
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
                    avg_fill_price=norm.get("fill_price"),
                    status=norm.get("status", "unknown"),
                    raw_payload=raw,
                ))
                counters["orders"] += 1
        except Exception as e:
            counters["errors"] += 1
            logger.error("sync_t212.orders_error", error=str(e))

        # Surface the sync_session_id in run.counters (for source_run audit)
        # and the structured log so operators can correlate. Stored as str
        # because counters is a JSONB blob.
        counters["sync_session_id"] = str(sync_session_id)
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
