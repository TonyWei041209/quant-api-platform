"""Unit tests for libs.ingestion.sync_eod_prices_universe.

These tests are HERMETIC — they do NOT touch any DB, do NOT call any
external API, and do NOT create any Cloud resources. The planner is pure
data; the executor raises NotImplementedError until acceptance #5-#10
are signed off.

Coverage focus:
1. dry-run produces a plan but writes nothing
2. production write requires the two-flag handshake
3. universe ticker count = 36 and matches readiness script
4. yfinance_dev does NOT appear in production sync path
5. per-ticker failure model is documented (planner does not couple tickers)
6. summary contains the right side-effect attestations
7. default polygon delay is conservative (free-tier safe)
8. banned trading terms do not appear in plan descriptors
9. WRITE_PRODUCTION refuses non-production DB targets
10. WRITE_LOCAL refuses non-local DB targets
"""
from __future__ import annotations

from datetime import date

import pytest

from libs.ingestion.sync_eod_prices_universe import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_POLYGON_DELAY_SECONDS,
    SyncPlan,
    TickerPlan,
    build_sync_plan,
    execute_sync,
    render_plan_report,
    _classify_db_url,
)
from libs.scanner.scanner_universe import (
    SCANNER_RESEARCH_UNIVERSE,
    SCANNER_UNIVERSE_NAMES,
    get_universe,
)


# ---------------------------------------------------------------------------
# Universe constants
# ---------------------------------------------------------------------------

class TestUniverseConstants:
    def test_universe_has_exactly_36_tickers(self):
        assert len(SCANNER_RESEARCH_UNIVERSE) == 36

    def test_universe_has_no_duplicates(self):
        assert len(set(SCANNER_RESEARCH_UNIVERSE)) == 36

    def test_get_universe_returns_canonical(self):
        assert get_universe("scanner-research") == SCANNER_RESEARCH_UNIVERSE

    def test_unknown_universe_raises(self):
        with pytest.raises(ValueError):
            get_universe("nonexistent-universe")

    def test_universe_matches_readiness_script(self):
        """The bootstrap script and readiness script must use the same list."""
        # Readiness script's UNIVERSE constant
        from scripts.check_scanner_universe_provider_readiness import UNIVERSE as READINESS_UNIVERSE
        assert tuple(READINESS_UNIVERSE) == SCANNER_RESEARCH_UNIVERSE


# ---------------------------------------------------------------------------
# Dry-run planning (no DB session)
# ---------------------------------------------------------------------------

class TestDryRunPlanWithoutSession:
    def test_dry_run_default_works_without_session(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
            session=None,
            today=date(2026, 4, 29),
        )
        assert plan.write_mode == "DRY_RUN"
        assert plan.db_target == "unknown"
        assert len(plan.per_ticker) == 36

    def test_dry_run_all_tickers_get_bootstrap_when_no_session(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
            session=None,
        )
        assert all(p.is_bootstrap for p in plan.per_ticker)

    def test_default_polygon_delay_is_conservative(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        assert plan.polygon_delay_seconds >= 12.0, \
            "Default delay must be safe under Polygon free-tier (5/min)"
        assert DEFAULT_POLYGON_DELAY_SECONDS >= 12.0

    def test_estimated_runtime_realistic(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        # 36 × 13 = 468 seconds ≈ 7.8 minutes
        assert 400 < plan.estimated_runtime_seconds < 700


# ---------------------------------------------------------------------------
# Two-flag production write handshake
# ---------------------------------------------------------------------------

class TestProductionWriteHandshake:
    def test_write_production_without_confirm_raises(self):
        with pytest.raises(ValueError, match="confirm_production_write"):
            build_sync_plan(
                universe_name="scanner-research",
                tickers=SCANNER_RESEARCH_UNIVERSE,
                write_mode="WRITE_PRODUCTION",
                confirm_production_write=False,
            )

    def test_write_production_against_unknown_db_raises(self):
        with pytest.raises(ValueError, match="db_target"):
            build_sync_plan(
                universe_name="scanner-research",
                tickers=SCANNER_RESEARCH_UNIVERSE,
                write_mode="WRITE_PRODUCTION",
                confirm_production_write=True,
                session=None,  # → db_target=unknown
            )

    def test_write_local_against_unknown_db_raises(self):
        with pytest.raises(ValueError, match="db_target"):
            build_sync_plan(
                universe_name="scanner-research",
                tickers=SCANNER_RESEARCH_UNIVERSE,
                write_mode="WRITE_LOCAL",
                confirm_production_write=False,
                session=None,
            )


# ---------------------------------------------------------------------------
# DB URL classification
# ---------------------------------------------------------------------------

class TestDbUrlClassification:
    def test_localhost_classified_as_local(self):
        assert _classify_db_url(
            "postgresql+psycopg2://quant:x@localhost:5432/quant_platform"
        ) == "local"

    def test_127_0_0_1_classified_as_local(self):
        assert _classify_db_url(
            "postgresql+psycopg2://quant:x@127.0.0.1:5432/quant_platform"
        ) == "local"

    def test_cloudsql_classified_as_production(self):
        assert _classify_db_url(
            "postgresql://quantuser:p@/quantdb?host=/cloudsql/PROJ:asia-east2:quant-api-db"
        ) == "production"

    def test_unknown_classified_as_unknown(self):
        assert _classify_db_url("postgresql://quantuser:p@some-other-host/db") == "unknown"


# ---------------------------------------------------------------------------
# Source policy — yfinance_dev FORBIDDEN in production sync path
# ---------------------------------------------------------------------------

class TestSourcePolicy:
    def test_primary_source_is_polygon(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        assert plan.primary_source == "polygon"

    def test_fallback_source_is_fmp(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        assert plan.fallback_source == "fmp"

    def test_yfinance_dev_not_in_module_source(self):
        """Module source itself must not import or reference yfinance_dev as
        a usable source — only as a forbidden mention in policy comments."""
        import libs.ingestion.sync_eod_prices_universe as mod
        import inspect
        src = inspect.getsource(mod)
        # yfinance_dev IS allowed to appear in policy comments saying
        # "must not use" — but should NOT appear as a Literal source value
        assert '"yfinance_dev"' not in src, \
            "yfinance_dev appears as a string literal — likely used as a source"
        assert "'yfinance_dev'" not in src, \
            "yfinance_dev appears as a string literal — likely used as a source"

    def test_module_source_explicitly_forbids_yfinance_dev_in_docstring(self):
        import libs.ingestion.sync_eod_prices_universe as mod
        # Docstring should explicitly state yfinance_dev forbidden
        assert "yfinance_dev" in (mod.__doc__ or "")
        assert "MUST NOT" in (mod.__doc__ or "")


# ---------------------------------------------------------------------------
# Banned trading-language check
# ---------------------------------------------------------------------------

class TestBannedTradingLanguage:
    def test_plan_descriptors_contain_no_banned_phrases(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        assert plan.banned_phrases_check == []

    def test_render_plan_report_no_buy_sell_target(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        report = render_plan_report(plan).lower()
        # Trading-action words must not appear in the rendered plan summary
        forbidden_substrings = [
            "buy now", "sell now", "enter long", "enter position",
            "target price", "position size", "leverage on",
            "guaranteed", "certain to rise",
        ]
        for f in forbidden_substrings:
            assert f not in report, f"Banned substring '{f}' found in plan report"


# ---------------------------------------------------------------------------
# Plan report attestations
# ---------------------------------------------------------------------------

class TestPlanReportAttestations:
    def test_dry_run_report_contains_required_attestations(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        report = render_plan_report(plan)
        for required in [
            "DRY RUN",
            "NO DB WRITES",
            "DB writes performed     : NONE",
            "Cloud Run jobs created  : NONE",
            "Scheduler changes       : NONE",
            "Production deploy       : NONE",
            "Execution objects       : NONE",
            "Broker write            : NONE",
            "LOCKED",
            "data_mode               : daily_eod",
            "primary_source          : polygon",
            "fallback_source         : fmp",
            "yfinance_dev allowed    : NO",
            "ticker_count            : 36",
            "REMAINS DEFERRED",
        ]:
            assert required in report, f"Missing required attestation: {required}"

    def test_estimated_polygon_calls_equals_ticker_count(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        assert plan.estimated_polygon_calls == 36


# ---------------------------------------------------------------------------
# execute_sync gating
# ---------------------------------------------------------------------------

class TestExecuteSyncGating:
    def test_execute_sync_dry_run_refused(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        with pytest.raises(ValueError, match="DRY_RUN"):
            execute_sync(plan)

    def test_execute_sync_not_implemented_yet(self):
        """execute_sync intentionally NotImplementedError until acceptance
        #5-#10 are signed off. This test pins that contract — if someone
        implements execute_sync, this test must be deliberately updated."""
        # Construct a plan that would otherwise be valid for WRITE_LOCAL,
        # but bypass the session check by patching module-level helpers.
        # Easiest: use the planner with a fake session that classifies as local.
        class _FakeBind:
            url = "postgresql://u:p@localhost:5432/d"
        class _FakeSession:
            def get_bind(self): return _FakeBind()
            def execute(self, *a, **kw):
                class _R:
                    def fetchall(self): return []
                return _R()
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=_FakeSession(),
        )
        with pytest.raises(NotImplementedError):
            execute_sync(plan)


# ---------------------------------------------------------------------------
# Per-ticker failure isolation (documented contract)
# ---------------------------------------------------------------------------

class TestPerTickerIsolationContract:
    def test_planner_does_not_couple_tickers(self):
        """Each ticker has its own TickerPlan, so per-ticker failures during
        execution can be isolated. Verify structure."""
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        assert isinstance(plan.per_ticker, list)
        assert all(isinstance(p, TickerPlan) for p in plan.per_ticker)
        # Each ticker plan is self-contained
        for p in plan.per_ticker:
            assert p.ticker
            assert p.plan_start <= p.plan_end


# ---------------------------------------------------------------------------
# Default values pinned (so future edits surface deliberately)
# ---------------------------------------------------------------------------

class TestPinnedDefaults:
    def test_default_lookback_days(self):
        assert DEFAULT_LOOKBACK_DAYS == 7

    def test_default_polygon_delay_is_13_seconds(self):
        assert DEFAULT_POLYGON_DELAY_SECONDS == 13.0
