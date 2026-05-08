"""Unit tests — get_portfolio_summary uses snapshot-set semantics.

Verifies the ghost-holding fix described in
`docs/t212-near-real-time-broker-truth-plan.md`:

  - When the broker has any rows with sync_session_id set, the API returns
    only positions from the most recent sync_session_id (closed-out
    tickers from earlier sessions drop out — no ghosts).
  - When no rows have sync_session_id set, the legacy DISTINCT ON query
    is used so dashboards keep working during the rollout window.

Tests are hermetic: the database session is mocked at the SQL boundary.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from libs.portfolio.portfolio_service import (
    _latest_sync_session_id,
    get_portfolio_summary,
    is_instrument_held,
    get_watchlist_holdings_overlay,
)


def _row(*values):
    """Build a row-like object that supports indexing (matching SQLAlchemy)."""
    return values


@pytest.mark.unit
class TestLatestSyncSessionId:
    def test_returns_uuid_when_session_rows_exist(self):
        sid = uuid.uuid4()
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = _row(sid)
        result = _latest_sync_session_id(db, broker="trading212")
        assert result == sid

    def test_returns_none_when_no_session_rows(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = None
        result = _latest_sync_session_id(db, broker="trading212")
        assert result is None

    def test_returns_none_when_row_has_null_sid(self):
        db = MagicMock()
        db.execute.return_value.fetchone.return_value = _row(None)
        result = _latest_sync_session_id(db, broker="trading212")
        assert result is None


@pytest.mark.unit
class TestGetPortfolioSummarySessionSet:
    """Reproduce the ghost-holding scenario described in the plan doc.

    Session A: AMD + MU (older sync, AMD later closed)
    Session B: MU only (newer sync — AMD has been sold)

    Expected: only MU is returned. AMD (which still has a qty>0 row from
    session A) must NOT appear.
    """

    def _build_db_with_session_b_active(self):
        sid_b = uuid.uuid4()
        snapshot_at = datetime(2026, 5, 8, 21, 0, tzinfo=timezone.utc)
        # 1) account row
        acct = _row(
            uuid.uuid4(), "trading212", "default",
            1000.0, 1000.0, 4000.0, "USD", snapshot_at,
        )
        # 2) latest_sync_session_id query → returns session B's UUID
        sid_lookup = _row(sid_b)
        # 3) positions query bound to session B → MU only
        mu_row = _row(
            uuid.uuid4(), "trading212", uuid.uuid4(), "MU_US_EQ",
            5.22, 631.27, 733.10, 3826.6, 532.0,
            "USD", snapshot_at,
        )
        # 4) recent orders (empty for simplicity)
        # We return queries in execution order with three .execute() calls:
        #    a. account snapshot SELECT
        #    b. latest_sync_session_id SELECT
        #    c. positions SELECT (session-set path)
        #    d. orders SELECT
        db = MagicMock()
        execute_results = [
            MagicMock(fetchone=MagicMock(return_value=acct)),
            MagicMock(fetchone=MagicMock(return_value=sid_lookup)),
            MagicMock(fetchall=MagicMock(return_value=[mu_row])),
            MagicMock(fetchall=MagicMock(return_value=[])),
        ]
        db.execute.side_effect = execute_results
        return db

    def test_returns_only_session_b_positions_no_ghosts(self):
        db = self._build_db_with_session_b_active()
        result = get_portfolio_summary(db, broker="trading212")
        assert result["connected"] is True
        assert result["position_count"] == 1
        tickers = [p["broker_ticker"] for p in result["positions"]]
        assert tickers == ["MU_US_EQ"]
        assert "AMD_US_EQ" not in tickers

    def test_uses_session_set_query_path(self):
        db = self._build_db_with_session_b_active()
        get_portfolio_summary(db, broker="trading212")
        # The third SQL call (after account + sid lookup) is the positions
        # SELECT — must reference sync_session_id and be bound to the sid
        # from the previous lookup.
        assert db.execute.call_count >= 3
        third_call = db.execute.call_args_list[2]
        sql = str(third_call.args[0])
        assert "sync_session_id" in sql.lower()


@pytest.mark.unit
class TestGetPortfolioSummaryLegacyFallback:
    """When no rows have sync_session_id (pre-migration / pre-deploy state),
    the legacy DISTINCT ON (broker_ticker) query path must run."""

    def _build_db_with_legacy_fallback(self):
        snapshot_at = datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)
        acct = _row(
            uuid.uuid4(), "trading212", "default",
            500.0, 500.0, 2000.0, "USD", snapshot_at,
        )
        # latest_sync_session_id query → no rows → fall back
        sid_lookup_empty = None
        # legacy path returns latest qty>0 row per broker_ticker
        legacy_row = _row(
            uuid.uuid4(), "trading212", uuid.uuid4(), "AAPL_US_EQ",
            10.0, 150.0, 200.0, 2000.0, 500.0,
            "USD", snapshot_at,
        )
        db = MagicMock()
        db.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=acct)),
            MagicMock(fetchone=MagicMock(return_value=sid_lookup_empty)),
            MagicMock(fetchall=MagicMock(return_value=[legacy_row])),
            MagicMock(fetchall=MagicMock(return_value=[])),
        ]
        return db

    def test_uses_legacy_distinct_on_path(self):
        db = self._build_db_with_legacy_fallback()
        get_portfolio_summary(db, broker="trading212")
        # Third call uses DISTINCT ON, NOT sync_session_id binding
        assert db.execute.call_count >= 3
        third_call = db.execute.call_args_list[2]
        sql = str(third_call.args[0])
        assert "distinct on" in sql.lower()
        # The legacy path must NOT bind sid (param dict is just {"broker": ...})
        params = third_call.args[1] if len(third_call.args) > 1 else {}
        assert "sid" not in params

    def test_returns_legacy_positions(self):
        db = self._build_db_with_legacy_fallback()
        result = get_portfolio_summary(db, broker="trading212")
        assert result["position_count"] == 1
        assert result["positions"][0]["broker_ticker"] == "AAPL_US_EQ"


@pytest.mark.unit
class TestIsInstrumentHeldUsesSessionSet:
    def test_uses_session_when_available(self):
        sid = uuid.uuid4()
        iid = uuid.uuid4()
        snapshot_at = datetime(2026, 5, 8, 21, 0, tzinfo=timezone.utc)
        db = MagicMock()
        db.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=_row(sid))),
            MagicMock(fetchone=MagicMock(return_value=_row(
                "MU_US_EQ", 5.22, 631.27, 733.10, 3826.6, 532.0, snapshot_at
            ))),
        ]
        result = is_instrument_held(db, str(iid), broker="trading212")
        assert result["held"] is True
        # Second call must include sync_session_id binding
        second = db.execute.call_args_list[1]
        sql = str(second.args[0])
        assert "sync_session_id" in sql.lower()

    def test_falls_back_when_no_session(self):
        iid = uuid.uuid4()
        db = MagicMock()
        db.execute.side_effect = [
            MagicMock(fetchone=MagicMock(return_value=None)),
            MagicMock(fetchone=MagicMock(return_value=None)),
        ]
        result = is_instrument_held(db, str(iid), broker="trading212")
        assert result["held"] is False
        # Second call must NOT bind sid
        second = db.execute.call_args_list[1]
        params = second.args[1] if len(second.args) > 1 else {}
        assert "sid" not in params


@pytest.mark.unit
class TestWatchlistHoldingsOverlayUsesSessionSet:
    def test_session_set_path(self):
        sid = uuid.uuid4()
        db = MagicMock()
        # 1) watchlist items query
        # 2) latest_sync_session_id query → returns sid
        # 3) held query → returns empty (overlay tested elsewhere)
        db.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=[_row(uuid.uuid4())])),
            MagicMock(fetchone=MagicMock(return_value=_row(sid))),
            MagicMock(fetchall=MagicMock(return_value=[])),
        ]
        result = get_watchlist_holdings_overlay(db, "00000000-0000-0000-0000-000000000000")
        assert "held_items" in result
        # Third call binds sid + uses NO DISTINCT ON
        third = db.execute.call_args_list[2]
        sql = str(third.args[0])
        assert "sync_session_id" in sql.lower()
        assert "distinct on" not in sql.lower()
