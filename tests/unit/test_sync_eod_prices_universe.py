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
    """execute_sync gating contract.

    Updated 2026-04-29: WRITE_LOCAL is now implemented (Phase A).
    WRITE_PRODUCTION remains hard-deferred until acceptance #5/#9 sign-off.
    """

    @pytest.mark.asyncio
    async def test_execute_sync_dry_run_refused(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        with pytest.raises(ValueError, match="DRY_RUN"):
            await execute_sync(plan, session=None)

    @pytest.mark.asyncio
    async def test_execute_sync_write_production_still_not_implemented(self):
        """WRITE_PRODUCTION must remain hard-deferred. If someone implements
        production write, this test MUST be deliberately updated together
        with acceptance #5 / #8 / #9 / #10 sign-off."""
        from libs.ingestion.sync_eod_prices_universe import PRODUCTION_WRITE_DEFERRED_MESSAGE
        # Build a fake production-classified plan
        class _FakeBindProd:
            url = "postgresql://u:p@/d?host=/cloudsql/proj:asia-east2:db"
        class _FakeSessionProd:
            def get_bind(self): return _FakeBindProd()
            def execute(self, *a, **kw):
                class _R:
                    def fetchall(self): return []
                return _R()
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="WRITE_PRODUCTION",
            confirm_production_write=True,
            session=_FakeSessionProd(),
        )
        with pytest.raises(NotImplementedError) as exc_info:
            await execute_sync(plan, session=_FakeSessionProd())
        assert "acceptance" in str(exc_info.value).lower()


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


# ---------------------------------------------------------------------------
# WRITE_LOCAL execute_sync — behaviour with mocked adapters and session
# ---------------------------------------------------------------------------

from libs.ingestion.sync_eod_prices_universe import (
    SyncResult, TickerSyncResult, render_sync_result,
)


class _FakeLocalBind:
    url = "postgresql+psycopg2://u:p@localhost:5432/quant_platform"


class _FakeProdBind:
    url = "postgresql://u:p@/d?host=/cloudsql/proj:asia-east2:db"


class _FakeSession:
    """Minimal fake session: classifies as local; resolves no instrument_ids
    by default (override via tickers_with_iid). Tracks commit/rollback calls."""
    def __init__(self, bind=None, latest_dates=None, tickers_with_iid=None):
        self._bind = bind or _FakeLocalBind()
        self._latest_dates = latest_dates or {}
        # Map ticker → fake uuid string
        self._iids = {t: f"00000000-0000-0000-0000-{i:012d}"
                      for i, t in enumerate(tickers_with_iid or [])}
        self.commit_count = 0
        self.rollback_count = 0

    def get_bind(self):
        return self._bind

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def execute(self, sql, params=None):
        sql_text = str(sql)
        # Latest trade date query returns whatever caller seeded
        if "MAX(p.trade_date)" in sql_text:
            class _R:
                def __init__(self, rows): self._rows = rows
                def fetchall(self): return self._rows
            return _R([(t, d) for t, d in self._latest_dates.items()])
        # Instrument id lookup
        if "FROM instrument_identifier" in sql_text and "id_value = ANY" in sql_text:
            class _R:
                def __init__(self, rows): self._rows = rows
                def fetchall(self): return self._rows
            requested = (params or {}).get("tickers", [])
            return _R([(t, self._iids[t]) for t in requested if t in self._iids])
        # Anything else
        class _R:
            def fetchall(self): return []
        return _R()


class TestWriteLocalDbTargetGuard:
    """WRITE_LOCAL must refuse non-local DB targets."""

    @pytest.mark.asyncio
    async def test_write_local_against_production_db_refused_at_planner(self):
        """planner-level guard"""
        with pytest.raises(ValueError, match="db_target"):
            build_sync_plan(
                universe_name="scanner-research",
                tickers=("NVDA",),
                write_mode="WRITE_LOCAL",
                confirm_production_write=False,
                session=_FakeSession(bind=_FakeProdBind()),
            )

    @pytest.mark.asyncio
    async def test_execute_sync_defense_in_depth_blocks_non_local(self):
        """Even if planner is fooled into producing a WRITE_LOCAL plan with
        non-local target (impossible via build_sync_plan but possible by
        manual construction), execute_sync must still refuse."""
        from libs.ingestion.sync_eod_prices_universe import SyncPlan
        from datetime import date
        # Hand-build a plan with WRITE_LOCAL + db_target=production
        plan = SyncPlan(
            universe_name="scanner-research",
            tickers=("NVDA",),
            write_mode="WRITE_LOCAL",
            db_target="production",  # contradiction
            db_url_label="(forced)",
            polygon_delay_seconds=0.0,
            lookback_days=7,
            bootstrap_days=540,
            primary_source="polygon",
            fallback_source="fmp",
            today=date(2026, 4, 29),
            per_ticker=[],
        )
        with pytest.raises(ValueError, match="REFUSED"):
            await execute_sync(plan, session=_FakeSession())


async def _noop_sleep(_seconds: float) -> None:
    """Test sleep substitute — instant."""
    return None


class TestWriteLocalIdempotencyAndCounting:
    """Verify execute_sync correctly counts inserted vs skipped via mocked
    polygon/fmp callables."""

    @pytest.mark.asyncio
    async def test_successful_polygon_path(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA", "AMD"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=_FakeSession(tickers_with_iid=["NVDA", "AMD"]),
        )

        async def fake_polygon(session, ticker, iid, fd, td):
            # Pretend each ticker returned 5 inserted, 2 skipped
            return 5, 2

        async def fake_fmp(session, ticker, iid, fd, td):
            raise AssertionError("FMP must not be called when Polygon succeeds")

        result = await execute_sync(
            plan,
            session=_FakeSession(tickers_with_iid=["NVDA", "AMD"]),
            sleep_fn=_noop_sleep,
            polygon_call=fake_polygon,
            fmp_call=fake_fmp,
        )

        assert result.mode == "WRITE_LOCAL"
        assert result.db_target == "local"
        assert result.ticker_count == 2
        assert sorted(result.succeeded) == ["AMD", "NVDA"]
        assert result.failed == []
        assert result.bars_inserted_total == 10  # 5 × 2
        assert result.bars_existing_or_skipped_total == 4  # 2 × 2
        assert all(p.source_used == "polygon" for p in result.per_ticker)


class TestWriteLocalFmpFallback:
    @pytest.mark.asyncio
    async def test_fmp_invoked_when_polygon_fails(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=_FakeSession(tickers_with_iid=["NVDA"]),
        )

        polygon_called = []
        fmp_called = []

        async def fake_polygon(session, ticker, iid, fd, td):
            polygon_called.append(ticker)
            raise RuntimeError("polygon network failure simulated")

        async def fake_fmp(session, ticker, iid, fd, td):
            fmp_called.append(ticker)
            return 7, 0

        result = await execute_sync(
            plan,
            session=_FakeSession(tickers_with_iid=["NVDA"]),
            sleep_fn=_noop_sleep,
            polygon_call=fake_polygon,
            fmp_call=fake_fmp,
        )

        assert polygon_called == ["NVDA"]
        assert fmp_called == ["NVDA"]
        assert result.succeeded == ["NVDA"]
        assert result.failed == []
        assert result.bars_inserted_total == 7
        assert result.per_ticker[0].source_used == "fmp"
        assert "polygon network failure" in (result.per_ticker[0].polygon_error or "")


class TestWriteLocalPerTickerIsolation:
    @pytest.mark.asyncio
    async def test_one_ticker_failure_does_not_abort_batch(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA", "AMD", "MSFT"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=_FakeSession(tickers_with_iid=["NVDA", "AMD", "MSFT"]),
        )

        async def fake_polygon(session, ticker, iid, fd, td):
            if ticker == "AMD":
                raise RuntimeError("simulated AMD failure")
            return 3, 1

        async def fake_fmp(session, ticker, iid, fd, td):
            # FMP also fails for AMD
            if ticker == "AMD":
                raise RuntimeError("AMD fmp also fails")
            raise AssertionError("FMP not expected for non-AMD")

        result = await execute_sync(
            plan,
            session=_FakeSession(tickers_with_iid=["NVDA", "AMD", "MSFT"]),
            sleep_fn=_noop_sleep,
            polygon_call=fake_polygon,
            fmp_call=fake_fmp,
        )

        assert sorted(result.succeeded) == ["MSFT", "NVDA"]
        assert len(result.failed) == 1
        assert result.failed[0][0] == "AMD"
        assert result.bars_inserted_total == 6  # 3 × 2 surviving tickers
        assert result.bars_existing_or_skipped_total == 2


class TestWriteLocalUnresolvableInstrument:
    @pytest.mark.asyncio
    async def test_ticker_without_instrument_id_marked_failed(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA", "ZZZZ"),  # ZZZZ has no instrument_id
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=_FakeSession(tickers_with_iid=["NVDA"]),  # only NVDA mapped
        )

        polygon_called = []

        async def fake_polygon(session, ticker, iid, fd, td):
            polygon_called.append(ticker)
            return 1, 0

        async def fake_fmp(session, ticker, iid, fd, td):
            raise AssertionError("must not be called")

        result = await execute_sync(
            plan,
            session=_FakeSession(tickers_with_iid=["NVDA"]),
            sleep_fn=_noop_sleep,
            polygon_call=fake_polygon,
            fmp_call=fake_fmp,
        )

        assert result.succeeded == ["NVDA"]
        assert len(result.failed) == 1
        assert result.failed[0][0] == "ZZZZ"
        assert "instrument_id not resolved" in result.failed[0][1]
        assert polygon_called == ["NVDA"]  # ZZZZ never reached the adapter


class TestWriteLocalSummaryAttestations:
    @pytest.mark.asyncio
    async def test_result_attests_no_dangerous_side_effects(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=_FakeSession(tickers_with_iid=["NVDA"]),
        )

        async def ok(session, ticker, iid, fd, td):
            return 1, 0

        result = await execute_sync(
            plan, session=_FakeSession(tickers_with_iid=["NVDA"]),
            sleep_fn=_noop_sleep,
            polygon_call=ok, fmp_call=ok,
        )

        assert result.cloud_run_jobs_created == "NONE"
        assert result.scheduler_changes == "NONE"
        assert result.production_deploy == "NONE"
        assert result.execution_objects == "NONE"
        assert result.broker_write == "NONE"
        assert "LOCKED" in result.live_submit
        assert "LOCAL" in result.db_writes_performed.upper()

    @pytest.mark.asyncio
    async def test_render_sync_result_no_banned_phrases(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=_FakeSession(tickers_with_iid=["NVDA"]),
        )

        async def ok(session, ticker, iid, fd, td):
            return 2, 0

        result = await execute_sync(
            plan, session=_FakeSession(tickers_with_iid=["NVDA"]),
            sleep_fn=_noop_sleep,
            polygon_call=ok, fmp_call=ok,
        )
        rendered = render_sync_result(result).lower()
        for banned in ["buy now", "sell now", "enter long", "enter position",
                       "target price", "position size", "guaranteed"]:
            assert banned not in rendered, f"banned phrase '{banned}' in rendered result"


class TestPerTickerCommit:
    """Defence: each successful ticker must commit so partial progress
    persists when the caller's session is closed without explicit commit."""

    @pytest.mark.asyncio
    async def test_each_success_commits(self):
        sess = _FakeSession(tickers_with_iid=["NVDA", "AMD"])
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA", "AMD"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=sess,
        )

        async def ok(session, ticker, iid, fd, td):
            return 1, 0

        await execute_sync(
            plan, session=sess,
            sleep_fn=_noop_sleep, polygon_call=ok, fmp_call=ok,
        )
        assert sess.commit_count == 2  # one per successful ticker

    @pytest.mark.asyncio
    async def test_double_provider_failure_rolls_back_only(self):
        sess = _FakeSession(tickers_with_iid=["NVDA"])
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=0.0,
            session=sess,
        )

        async def fail(session, ticker, iid, fd, td):
            raise RuntimeError("simulated provider error")

        result = await execute_sync(
            plan, session=sess,
            sleep_fn=_noop_sleep, polygon_call=fail, fmp_call=fail,
        )
        assert result.failed == [("NVDA", result.failed[0][1])]  # captured failure
        assert sess.commit_count == 0  # nothing succeeded → no commits
        assert sess.rollback_count >= 1  # at least one rollback after polygon error


class TestRateLimitDelayInjectable:
    @pytest.mark.asyncio
    async def test_sleep_fn_called_between_tickers(self):
        plan = build_sync_plan(
            universe_name="scanner-research",
            tickers=("NVDA", "AMD", "MSFT"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            polygon_delay_seconds=13.0,
            session=_FakeSession(tickers_with_iid=["NVDA", "AMD", "MSFT"]),
        )

        sleep_calls = []

        async def fake_sleep(s):
            sleep_calls.append(s)

        async def ok(session, ticker, iid, fd, td):
            return 1, 0

        await execute_sync(
            plan, session=_FakeSession(tickers_with_iid=["NVDA", "AMD", "MSFT"]),
            sleep_fn=fake_sleep, polygon_call=ok, fmp_call=ok,
        )

        # 3 tickers → 2 inter-ticker sleeps (no sleep before first)
        assert len(sleep_calls) == 2
        assert all(s == 13.0 for s in sleep_calls)


class TestWriteLocalDoesNotImportYfinanceDev:
    """Defence: the production sync path module must not import or
    reference yfinance_dev as a usable source."""

    def test_module_does_not_import_dev_load_prices(self):
        import libs.ingestion.sync_eod_prices_universe as mod
        import inspect
        src = inspect.getsource(mod)
        # No import of dev_load_prices, and no use of "yfinance_dev" string literal as a source
        assert "from libs.ingestion.dev_load_prices" not in src
        assert "import dev_load_prices" not in src
        # As before: yfinance_dev must not appear as a string literal source value
        assert '"yfinance_dev"' not in src
        assert "'yfinance_dev'" not in src
