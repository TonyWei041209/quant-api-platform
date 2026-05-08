"""Unit tests — sync_trading212_readonly attaches one sync_session_id per run.

Verifies that every BrokerPositionSnapshot row written by a single call
shares the same sync_session_id UUID, which is what the snapshot-set
semantics in get_portfolio_summary() depends on.

Hermetic: adapter is mocked; no DB session is created (we capture the
objects passed to session.add and inspect them).
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from libs.ingestion import sync_trading212_readonly as sync_module


@pytest.mark.unit
def test_every_position_row_shares_one_sync_session_id():
    fake_session = MagicMock()
    fake_session.execute.return_value.fetchall.return_value = []

    fake_adapter = MagicMock()
    fake_adapter.get_account_summary = AsyncMock(return_value={
        "id": 99, "currencyCode": "USD", "totalValue": 1000.0,
        "cash": {"free": 500, "total": 1000},
    })
    fake_adapter.get_positions = AsyncMock(return_value=[
        {"instrument": {"ticker": "MU_US_EQ"}, "quantity": 1},
        {"instrument": {"ticker": "NOK_US_EQ"}, "quantity": 2},
        {"instrument": {"ticker": "AAPL_US_EQ"}, "quantity": 3},
    ])
    fake_adapter.get_orders = AsyncMock(return_value=[])
    fake_adapter.normalize_position = lambda raw: {
        "broker_ticker": raw["instrument"]["ticker"],
        "quantity": raw["quantity"],
        "avg_cost": 100.0,
        "current_price": 110.0,
        "current_value": 110.0 * raw["quantity"],
        "pnl": 10.0 * raw["quantity"],
    }

    monkey_added: list = []
    fake_session.add.side_effect = lambda obj: monkey_added.append(obj)

    # Patch Trading212Adapter constructor to return our mock
    orig_adapter_cls = sync_module.Trading212Adapter
    sync_module.Trading212Adapter = MagicMock(return_value=fake_adapter)
    try:
        counters = asyncio.run(sync_module.sync_trading212_readonly(fake_session))
    finally:
        sync_module.Trading212Adapter = orig_adapter_cls

    assert counters["positions"] == 3
    assert counters["account_snapshots"] == 1
    assert "sync_session_id" in counters
    assert counters["sync_session_id"]  # UUID string

    position_rows = [
        obj for obj in monkey_added
        if type(obj).__name__ == "BrokerPositionSnapshot"
    ]
    assert len(position_rows) == 3
    sids = {row.sync_session_id for row in position_rows}
    assert len(sids) == 1, "All position rows in a single sync must share one sync_session_id"
    only_sid = sids.pop()
    assert only_sid is not None
    assert str(only_sid) == counters["sync_session_id"]


@pytest.mark.unit
def test_two_separate_runs_produce_distinct_sync_session_ids():
    """Two calls to sync_trading212_readonly must mint different UUIDs.

    Otherwise the snapshot-set semantics fail to isolate runs from each
    other and ghost positions can re-emerge.
    """
    captured_sids: list = []

    def make_session():
        s = MagicMock()
        s.execute.return_value.fetchall.return_value = []
        s.add.side_effect = lambda obj: (
            captured_sids.append(obj.sync_session_id)
            if type(obj).__name__ == "BrokerPositionSnapshot"
            else None
        )
        return s

    fake_adapter = MagicMock()
    fake_adapter.get_account_summary = AsyncMock(return_value={
        "id": 1, "currencyCode": "USD", "totalValue": 1.0, "cash": {},
    })
    fake_adapter.get_positions = AsyncMock(return_value=[
        {"instrument": {"ticker": "MU_US_EQ"}, "quantity": 1},
    ])
    fake_adapter.get_orders = AsyncMock(return_value=[])
    fake_adapter.normalize_position = lambda raw: {
        "broker_ticker": raw["instrument"]["ticker"],
        "quantity": 1, "avg_cost": 1.0, "current_price": 1.0,
        "current_value": 1.0, "pnl": 0.0,
    }

    orig_adapter_cls = sync_module.Trading212Adapter
    sync_module.Trading212Adapter = MagicMock(return_value=fake_adapter)
    try:
        asyncio.run(sync_module.sync_trading212_readonly(make_session()))
        asyncio.run(sync_module.sync_trading212_readonly(make_session()))
    finally:
        sync_module.Trading212Adapter = orig_adapter_cls

    assert len(captured_sids) == 2
    assert captured_sids[0] != captured_sids[1]
