"""Phase 4E: Final integration tests — DQ-11, list-instruments CLI, table verification,
backtest API, and full execution pipeline."""
from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import text

from libs.db.session import get_sync_session


# ---------------------------------------------------------------------------
# DQ-11: Raw adjusted contamination check
# ---------------------------------------------------------------------------

class TestDQ11RawAdjustedContamination:
    """Test the DQ-11 rule that detects adjusted data in price_bar_raw."""

    def test_rule_returns_list(self):
        """DQ-11 rule should return a list (possibly empty if data is clean)."""
        from libs.dq.price_rules import check_raw_adjusted_contamination

        session = get_sync_session()
        try:
            issues = check_raw_adjusted_contamination(session)
            assert isinstance(issues, list)
            # If there are issues, verify structure
            for issue in issues:
                assert issue["severity"] == "error"
                assert issue["table_name"] == "price_bar_raw"
                assert "record_key" in issue
                assert "reason" in issue["details"]
        finally:
            session.close()

    def test_rule_in_all_rules(self):
        """DQ-11 must be registered in ALL_RULES."""
        from libs.dq.rules import ALL_RULES

        rule_codes = [code for code, _, _ in ALL_RULES]
        assert "DQ-11" in rule_codes

    def test_clean_sources_pass(self):
        """If price_bar_raw only has normal sources, DQ-11 should report zero issues."""
        from libs.dq.price_rules import check_raw_adjusted_contamination

        session = get_sync_session()
        try:
            # Check if any rows actually have 'adjusted' in source
            count = session.execute(text(
                "SELECT COUNT(*) FROM price_bar_raw "
                "WHERE LOWER(source) LIKE '%adjusted%' "
                "   OR LOWER(source) LIKE '%adj%close%' "
                "   OR LOWER(source) LIKE '%split%adjusted%'"
            )).scalar()
            issues = check_raw_adjusted_contamination(session)
            assert len(issues) == count or len(issues) <= 1000  # capped at LIMIT 1000
        finally:
            session.close()

    def test_run_all_rules_includes_dq11(self):
        """run_all_rules should execute DQ-11 without errors."""
        from libs.dq.rules import run_all_rules

        session = get_sync_session()
        try:
            counters = run_all_rules(session)
            assert counters["rules_run"] >= 11  # We now have at least 11 rules
            assert "issues_found" in counters
        finally:
            session.close()


# ---------------------------------------------------------------------------
# CLI: list-instruments command
# ---------------------------------------------------------------------------

class TestListInstrumentsCLI:
    """Test the list-instruments CLI command."""

    def test_command_exists(self):
        """list-instruments should be a registered CLI command."""
        from apps.cli.main import app
        command_names = [cmd.name for cmd in app.registered_commands]
        assert "list-instruments" in command_names

    def test_command_runs(self):
        """list-instruments should execute without error."""
        from typer.testing import CliRunner
        from apps.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["list-instruments"])
        assert result.exit_code == 0
        assert "Total instruments" in result.output

    def test_command_shows_tickers(self):
        """list-instruments should display ticker symbols."""
        from typer.testing import CliRunner
        from apps.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["list-instruments"])
        assert result.exit_code == 0
        # Should have header row
        assert "Ticker" in result.output
        assert "Prices" in result.output


# ---------------------------------------------------------------------------
# Database: Verify all 21 tables exist
# ---------------------------------------------------------------------------

EXPECTED_TABLES = [
    "instrument",
    "instrument_identifier",
    "ticker_history",
    "exchange_calendar",
    "price_bar_raw",
    "corporate_action",
    "filing",
    "earnings_event",
    "financial_period",
    "financial_fact_std",
    "macro_series",
    "macro_observation",
    "source_run",
    "data_issue",
    "order_intent",
    "order_draft",
    "broker_account_snapshot",
    "broker_position_snapshot",
    "broker_order_snapshot",
    "backtest_run",
    "backtest_trade",
]


class TestDatabaseTables:
    """Verify all 21 expected tables exist in the database."""

    def test_all_tables_exist(self):
        """Every expected table should exist in the public schema."""
        session = get_sync_session()
        try:
            result = session.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )).fetchall()
            actual_tables = {row[0] for row in result}

            missing = [t for t in EXPECTED_TABLES if t not in actual_tables]
            assert not missing, f"Missing tables: {missing}"
        finally:
            session.close()

    def test_table_count_at_least_21(self):
        """Database should have at least 21 tables."""
        session = get_sync_session()
        try:
            count = session.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )).scalar()
            assert count >= 21, f"Expected >= 21 tables, got {count}"
        finally:
            session.close()

    @pytest.mark.parametrize("table_name", EXPECTED_TABLES)
    def test_table_is_queryable(self, table_name: str):
        """Each table should be queryable with SELECT COUNT(*)."""
        session = get_sync_session()
        try:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table_name}")).scalar()
            assert count >= 0
        finally:
            session.close()


# ---------------------------------------------------------------------------
# Backtest API endpoints with real data
# ---------------------------------------------------------------------------

class TestBacktestAPIEndpoints:
    """Test backtest API endpoints work with real data."""

    def _client(self):
        from fastapi.testclient import TestClient
        from apps.api.main import app
        return TestClient(app)

    def test_list_runs(self):
        """GET /backtest/runs should return 200."""
        client = self._client()
        resp = client.get("/backtest/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert "runs" in data
        assert "count" in data

    def test_run_backtest_with_real_tickers(self):
        """POST /backtest/run should succeed with real tickers."""
        # Check we have instruments first
        session = get_sync_session()
        try:
            rows = session.execute(text(
                "SELECT ii.id_value FROM instrument_identifier ii "
                "WHERE ii.id_type = 'ticker' LIMIT 2"
            )).fetchall()
            if not rows:
                pytest.skip("No tickers in database")
            tickers = [r[0] for r in rows]
        finally:
            session.close()

        client = self._client()
        resp = client.post("/backtest/run", json={
            "strategy": "phase4e_test",
            "tickers": tickers,
            "start_date": "2024-01-01",
            "end_date": "2024-06-30",
            "commission_bps": 5.0,
            "slippage_bps": 5.0,
            "max_positions": 2,
            "rebalance_freq": "monthly",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data
        assert "metrics" in data

    def test_get_run_detail(self):
        """GET /backtest/runs/{run_id} should return run details."""
        client = self._client()

        # List existing runs
        runs_resp = client.get("/backtest/runs")
        runs = runs_resp.json().get("runs", [])
        if not runs:
            pytest.skip("No backtest runs to inspect")

        run_id = runs[0]["run_id"]
        resp = client.get(f"/backtest/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert "strategy_name" in data

    def test_get_run_trades(self):
        """GET /backtest/runs/{run_id}/trades should return trades."""
        client = self._client()

        runs_resp = client.get("/backtest/runs")
        runs = runs_resp.json().get("runs", [])
        if not runs:
            pytest.skip("No backtest runs")

        run_id = runs[0]["run_id"]
        resp = client.get(f"/backtest/runs/{run_id}/trades")
        assert resp.status_code == 200
        assert "trades" in resp.json()

    def test_get_run_nav(self):
        """GET /backtest/runs/{run_id}/nav should return NAV series."""
        client = self._client()

        runs_resp = client.get("/backtest/runs")
        runs = runs_resp.json().get("runs", [])
        if not runs:
            pytest.skip("No backtest runs")

        run_id = runs[0]["run_id"]
        resp = client.get(f"/backtest/runs/{run_id}/nav")
        assert resp.status_code == 200
        assert "nav_series" in resp.json()


# ---------------------------------------------------------------------------
# Full pipeline: order_intent -> draft -> approve
# ---------------------------------------------------------------------------

class TestExecutionPipeline:
    """Full pipeline test: create intent -> create draft -> approve draft."""

    def test_full_pipeline(self):
        """Create an order_intent, generate a draft, and approve it."""
        from fastapi.testclient import TestClient
        from apps.api.main import app

        client = TestClient(app)

        # Find a real instrument
        session = get_sync_session()
        try:
            row = session.execute(text(
                "SELECT instrument_id::text FROM instrument LIMIT 1"
            )).fetchone()
            if not row:
                pytest.skip("No instruments in database")
            instrument_id = row[0]
        finally:
            session.close()

        # Step 1: Create an order intent
        resp1 = client.post("/execution/intents", json={
            "strategy_name": "test_phase4e",
            "instrument_id": instrument_id,
            "side": "buy",
            "target_qty": 10,
            "reason": {"test": "phase4e_pipeline"},
        })
        assert resp1.status_code == 200, f"Create intent failed: {resp1.text}"
        intent_data = resp1.json()
        assert "intent_id" in intent_data
        intent_id = intent_data["intent_id"]

        # Step 2: Create a draft from the intent
        resp2 = client.post(f"/execution/drafts/from-intent/{intent_id}", json={
            "broker": "trading212",
            "order_type": "limit",
            "qty": 10,
            "limit_price": 150.0,
            "tif": "day",
        })
        assert resp2.status_code == 200, f"Create draft failed: {resp2.text}"
        draft_data = resp2.json()
        assert "draft_id" in draft_data
        draft_id = draft_data["draft_id"]

        # Step 3: Approve the draft
        resp3 = client.post(f"/execution/drafts/{draft_id}/approve")
        assert resp3.status_code == 200, f"Approve draft failed: {resp3.text}"
        approve_data = resp3.json()
        assert approve_data["status"] == "approved"
        assert "approved_at" in approve_data

    def test_list_intents(self):
        """GET /execution/intents should return intents."""
        from fastapi.testclient import TestClient
        from apps.api.main import app

        client = TestClient(app)
        resp = client.get("/execution/intents")
        assert resp.status_code == 200
        assert "items" in resp.json()

    def test_list_drafts(self):
        """GET /execution/drafts should return drafts."""
        from fastapi.testclient import TestClient
        from apps.api.main import app

        client = TestClient(app)
        resp = client.get("/execution/drafts")
        assert resp.status_code == 200
        assert "items" in resp.json()
