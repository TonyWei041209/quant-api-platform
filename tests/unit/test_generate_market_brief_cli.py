"""CLI command `generate-market-brief` — argument plumbing tests.

These tests stub out the brief composition + persistence so we
exercise the typer command without hitting the DB or any provider.
The point is to verify:

  * the command is registered on the typer app
  * --write-snapshot=False does NOT call the persistence service
  * --write-snapshot=True calls persist_market_brief_snapshot exactly
    once with the mode passed via --mode
  * --db-target validation refuses unknown values
"""
from __future__ import annotations

import json
import sys
import inspect
import io
import tokenize

import pytest
from typer.testing import CliRunner

import apps.cli.main as cli_main


runner = CliRunner()


def _strip(src: str) -> str:
    out: list[str] = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    return "".join(out)


@pytest.fixture
def stub_brief(monkeypatch):
    """Stub build_overnight_brief + get_sync_session so the CLI runs
    without touching the DB or any provider."""
    sample = {
        "ticker_count": 0,
        "universe_scope": {"merged_ticker_count": 0},
        "candidates": [],
        "provider_diagnostics": {
            "news": {"section_state": "empty"},
        },
        "side_effects": {
            "db_writes": "NONE",
            "live_submit": "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)",
        },
    }

    async def fake_build(*args, **kwargs):
        return sample

    class _FakeSession:
        def close(self):
            pass

    from libs.market_brief import overnight_brief_service as obs
    monkeypatch.setattr(obs, "build_overnight_brief", fake_build)
    monkeypatch.setattr(cli_main, "get_sync_session", lambda: _FakeSession())
    return sample


def test_command_is_registered():
    cmd_names = [c.name for c in cli_main.app.registered_commands]
    assert "generate-market-brief" in cmd_names


def test_unknown_db_target_refused(stub_brief):
    result = runner.invoke(
        cli_main.app,
        ["generate-market-brief", "--db-target=staging"],
    )
    assert result.exit_code == 1
    assert "unknown --db-target" in (result.stderr + result.stdout).lower()


def test_no_snapshot_when_flag_off(stub_brief, monkeypatch):
    calls = {"n": 0}

    def fake_persist(*args, **kwargs):
        calls["n"] += 1
        return None

    from libs.research_snapshot import snapshot_service as svc
    monkeypatch.setattr(svc, "persist_market_brief_snapshot", fake_persist)
    # Note: the CLI imports persist_* through libs.research_snapshot, so
    # patch there too.
    import libs.research_snapshot as rs
    monkeypatch.setattr(rs, "persist_market_brief_snapshot", fake_persist)

    result = runner.invoke(
        cli_main.app,
        ["generate-market-brief", "--db-target=local"],
    )
    assert result.exit_code == 0, result.stdout + result.stderr
    # The command emits one JSON line with status=ok
    assert "\"status\": \"ok\"" in result.stdout
    # No persistence
    assert calls["n"] == 0


def test_snapshot_called_with_mode_when_flag_on(stub_brief, monkeypatch):
    received = {}

    class _FakeResult:
        def to_dict(self):
            return {"ok": True, "rows_written": 1}

    def fake_persist(db, brief, *, source):
        received["source"] = source
        received["called"] = True
        return _FakeResult()

    import libs.research_snapshot as rs
    monkeypatch.setattr(rs, "persist_market_brief_snapshot", fake_persist)
    monkeypatch.setattr(rs, "is_snapshot_write_enabled", lambda: True)

    result = runner.invoke(cli_main.app, [
        "generate-market-brief",
        "--write-snapshot",
        "--mode=overnight",
        "--db-target=local",
    ])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert received.get("called") is True
    assert received.get("source") == "overnight"
    # Both JSON lines emitted
    assert "snapshot_done" in result.stdout


def test_snapshot_skipped_when_feature_flag_off(stub_brief, monkeypatch):
    received = {"called": False}

    def fake_persist(*args, **kwargs):
        received["called"] = True
        raise RuntimeError("should NOT be called when flag off")

    import libs.research_snapshot as rs
    monkeypatch.setattr(rs, "persist_market_brief_snapshot", fake_persist)
    monkeypatch.setattr(rs, "is_snapshot_write_enabled", lambda: False)

    result = runner.invoke(cli_main.app, [
        "generate-market-brief",
        "--write-snapshot",
        "--mode=overnight",
        "--db-target=local",
    ])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert received["called"] is False
    assert "snapshot_skipped" in result.stdout


class TestNoForbiddenSymbols:
    def test_cli_command_research_only(self):
        # Inspect the function source — strip docstrings/comments first
        # so the negation language ("NEVER calls...") doesn't trip us.
        src = _strip(inspect.getsource(cli_main.generate_market_brief_cmd))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "/equity/orders/limit", "/equity/orders/market",
            "broker_account_snapshot", "broker_position_snapshot",
            "broker_order_snapshot",
            "FEATURE_T212_LIVE_SUBMIT",
            "selenium", "playwright", "puppeteer", "webdriver",
            "BeautifulSoup",
        ):
            assert needle.lower() not in src.lower(), (
                f"generate-market-brief CLI must not contain {needle!r}"
            )
