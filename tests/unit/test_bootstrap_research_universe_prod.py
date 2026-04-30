"""Unit tests for libs.ingestion.bootstrap_research_universe_prod.

These tests are HERMETIC — they do NOT touch any DB, do NOT call any external
API, and do NOT create any Cloud resources. They cover:

1. Universe constants (32 target, 4 protected, 3 ETF)
2. asset_type_for mapping
3. Plan handshake (four flags, db_target gating)
4. Protected tickers HARD-EXCLUDED from plan (defense-in-depth at plan layer)
5. Idempotency: tickers with existing instrument_identifier rows are skipped
6. Per-ticker failure isolation
7. FMP profile fallback rules (issuer→ticker, exchange→UNKNOWN, currency→USD,
   country→US)
8. Source policy: yfinance_dev / Polygon NOT imported, FMP only
9. Banned trading-language check
10. Scaffolding-only tables guard (no price_bar_raw, no broker, no execution)
11. DB_TARGET_OVERRIDE behavior
12. execute_bootstrap rejection of DRY_RUN / unsupported write modes
13. Defense-in-depth: hand-built plan with mismatched db_target refused
14. Side-effect attestations on result
"""
from __future__ import annotations

from datetime import date

import pytest

from libs.ingestion.bootstrap_research_universe_prod import (
    BootstrapPlan,
    BootstrapResult,
    DEFAULT_EFFECTIVE_FROM,
    DEFAULT_FMP_DELAY_SECONDS,
    PRODUCTION_WRITE_GUARD_MESSAGE,
    TickerBootstrap,
    TickerBootstrapResult,
    _classify_db_url,
    _normalize_profile,
    build_bootstrap_plan,
    execute_bootstrap,
    render_bootstrap_plan_report,
    render_bootstrap_result,
)
from libs.scanner.scanner_universe import (
    BOOTSTRAP_TARGET_TICKERS,
    ETF_TICKERS,
    PROTECTED_TICKERS,
    SCANNER_RESEARCH_UNIVERSE,
    asset_type_for,
)


# ---------------------------------------------------------------------------
# Universe constants
# ---------------------------------------------------------------------------


class TestUniverseConstants:
    def test_protected_set_is_exactly_four_tickers(self):
        assert len(PROTECTED_TICKERS) == 4
        assert PROTECTED_TICKERS == frozenset({"NVDA", "AAPL", "MSFT", "SPY"})

    def test_etf_set_is_exactly_three_tickers(self):
        assert len(ETF_TICKERS) == 3
        assert ETF_TICKERS == frozenset({"SPY", "QQQ", "IWM"})

    def test_bootstrap_target_count_is_thirty_two(self):
        assert len(BOOTSTRAP_TARGET_TICKERS) == 32

    def test_bootstrap_target_excludes_all_protected(self):
        for protected in PROTECTED_TICKERS:
            assert protected not in BOOTSTRAP_TARGET_TICKERS

    def test_bootstrap_target_is_universe_minus_protected(self):
        expected = tuple(t for t in SCANNER_RESEARCH_UNIVERSE if t not in PROTECTED_TICKERS)
        assert BOOTSTRAP_TARGET_TICKERS == expected

    def test_bootstrap_target_no_duplicates(self):
        assert len(set(BOOTSTRAP_TARGET_TICKERS)) == len(BOOTSTRAP_TARGET_TICKERS)

    def test_bootstrap_universe_plus_protected_equals_full_universe(self):
        union = set(BOOTSTRAP_TARGET_TICKERS) | set(PROTECTED_TICKERS)
        assert union == set(SCANNER_RESEARCH_UNIVERSE)


# ---------------------------------------------------------------------------
# asset_type_for
# ---------------------------------------------------------------------------


class TestAssetTypeFor:
    def test_etf_tickers_classified_as_etf(self):
        for t in ETF_TICKERS:
            assert asset_type_for(t) == "ETF"

    def test_equity_tickers_classified_as_equity(self):
        for t in ("NVDA", "AAPL", "TSLA", "JPM", "XOM"):
            assert asset_type_for(t) == "EQUITY"

    def test_lowercase_input_handled(self):
        assert asset_type_for("spy") == "ETF"
        assert asset_type_for("nvda") == "EQUITY"

    def test_unknown_ticker_defaults_to_equity(self):
        # Conservative default — only the explicit ETF set returns ETF
        assert asset_type_for("UNKNOWN_NEW_TICKER") == "EQUITY"


# ---------------------------------------------------------------------------
# Pinned defaults
# ---------------------------------------------------------------------------


class TestPinnedDefaults:
    def test_default_fmp_delay(self):
        assert DEFAULT_FMP_DELAY_SECONDS == 1.0

    def test_default_effective_from(self):
        assert DEFAULT_EFFECTIVE_FROM == date(2020, 1, 1)


# ---------------------------------------------------------------------------
# DB URL classification — mirrors sync_eod_prices_universe semantics
# ---------------------------------------------------------------------------


class TestDbUrlClassification:
    def test_localhost_classified_as_local(self):
        assert _classify_db_url(
            "postgresql+psycopg2://q:x@localhost:5432/quant"
        ) == "local"

    def test_127_classified_as_local(self):
        assert _classify_db_url(
            "postgresql+psycopg2://q:x@127.0.0.1:5432/quant"
        ) == "local"

    def test_cloudsql_classified_as_production(self):
        assert _classify_db_url(
            "postgresql://q:p@/db?host=/cloudsql/PROJ:asia-east2:inst"
        ) == "production"

    def test_unknown_classified_as_unknown(self):
        assert _classify_db_url("postgresql://q:p@some-host/db") == "unknown"


class TestDbTargetOverride:
    """DB_TARGET_OVERRIDE env var must take precedence over URL pattern."""

    def test_override_local_forces_local(self, monkeypatch):
        monkeypatch.setenv("DB_TARGET_OVERRIDE", "local")
        # Even a Cloud SQL-looking URL must classify as local under override
        assert _classify_db_url(
            "postgresql://q:p@/db?host=/cloudsql/PROJ:r:inst"
        ) == "local"

    def test_override_production_forces_production(self, monkeypatch):
        monkeypatch.setenv("DB_TARGET_OVERRIDE", "production")
        # Even a public-IP URL (which would normally classify as unknown)
        # must classify as production under override — this is exactly the
        # B1.1 fix scenario.
        assert _classify_db_url(
            "postgresql+psycopg2://q:p@34.150.76.29:5432/quantdb"
        ) == "production"

    def test_invalid_override_raises(self, monkeypatch):
        monkeypatch.setenv("DB_TARGET_OVERRIDE", "staging")
        with pytest.raises(ValueError, match="DB_TARGET_OVERRIDE must be"):
            _classify_db_url("postgresql://q:p@localhost/quant")

    def test_empty_override_falls_through(self, monkeypatch):
        monkeypatch.setenv("DB_TARGET_OVERRIDE", "")
        assert _classify_db_url("postgresql://q:p@localhost/quant") == "local"


# ---------------------------------------------------------------------------
# Profile fallback rules
# ---------------------------------------------------------------------------


class TestNormalizeProfile:
    def test_full_profile_no_fallbacks(self):
        raw = {
            "companyName": "Tesla, Inc.",
            "exchange": "NASDAQ",
            "currency": "USD",
            "country": "US",
        }
        out = _normalize_profile("TSLA", raw)
        assert out["issuer_name_current"] == "Tesla, Inc."
        assert out["exchange_primary"] == "NASDAQ"
        assert out["currency"] == "USD"
        assert out["country_code"] == "US"
        assert out["used_fallback_issuer"] is False
        assert out["used_fallback_exchange"] is False
        assert out["used_fallback_currency"] is False
        assert out["used_fallback_country"] is False

    def test_empty_profile_uses_all_fallbacks(self):
        out = _normalize_profile("ZZZZ", {})
        assert out["issuer_name_current"] == "ZZZZ"  # fallback to ticker
        assert out["exchange_primary"] == "UNKNOWN"
        assert out["currency"] == "USD"
        assert out["country_code"] == "US"
        assert out["used_fallback_issuer"] is True
        assert out["used_fallback_exchange"] is True
        assert out["used_fallback_currency"] is True
        assert out["used_fallback_country"] is True

    def test_none_profile_uses_all_fallbacks(self):
        out = _normalize_profile("ZZZZ", None)
        assert out["issuer_name_current"] == "ZZZZ"
        assert out["exchange_primary"] == "UNKNOWN"
        assert out["currency"] == "USD"
        assert out["country_code"] == "US"

    def test_partial_profile_partial_fallbacks(self):
        raw = {"companyName": "Foo Corp", "currency": None}  # only issuer present
        out = _normalize_profile("FOO", raw)
        assert out["issuer_name_current"] == "Foo Corp"
        assert out["exchange_primary"] == "UNKNOWN"
        assert out["currency"] == "USD"
        assert out["country_code"] == "US"
        assert out["used_fallback_issuer"] is False
        assert out["used_fallback_exchange"] is True
        assert out["used_fallback_currency"] is True
        assert out["used_fallback_country"] is True

    def test_alternate_field_names_accepted(self):
        # Some FMP responses use exchangeShortName / primaryExchange
        raw = {
            "name": "Foo Corp",
            "exchangeShortName": "NYSE",
            "currency_code": "USD",
            "country_code": "US",
        }
        out = _normalize_profile("FOO", raw)
        assert out["issuer_name_current"] == "Foo Corp"
        assert out["exchange_primary"] == "NYSE"
        assert out["currency"] == "USD"
        assert out["country_code"] == "US"


# ---------------------------------------------------------------------------
# Plan handshake — protected exclusion + four-flag enforcement
# ---------------------------------------------------------------------------


class TestPlanProtectedExclusion:
    """Protected tickers must never appear in the plan target list."""

    def test_protected_excluded_from_target_even_if_requested(self):
        # Caller asks for the full universe — plan must drop the 4 protected
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
            session=None,
        )
        # No protected tickers in target_tickers
        for protected in PROTECTED_TICKERS:
            assert protected not in plan.target_tickers
        # All protected tickers recorded in protected_excluded
        assert set(plan.protected_excluded) == PROTECTED_TICKERS
        # Final target count = 32
        assert len(plan.target_tickers) == 32

    def test_no_protected_tickers_in_per_ticker(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
            session=None,
        )
        for tp in plan.per_ticker:
            assert tp.ticker not in PROTECTED_TICKERS

    def test_caller_passing_only_protected_yields_empty_target(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=tuple(PROTECTED_TICKERS),
            write_mode="DRY_RUN",
            confirm_production_write=False,
            session=None,
        )
        assert plan.target_tickers == ()
        assert set(plan.protected_excluded) == PROTECTED_TICKERS
        assert plan.per_ticker == []


class TestPlanWriteHandshake:
    def test_write_production_without_confirm_raises(self):
        with pytest.raises(ValueError, match="confirm_production_write"):
            build_bootstrap_plan(
                universe_name="scanner-research",
                tickers=BOOTSTRAP_TARGET_TICKERS,
                write_mode="WRITE_PRODUCTION",
                confirm_production_write=False,
            )

    def test_write_production_against_unknown_db_raises(self):
        with pytest.raises(ValueError, match="db_target"):
            build_bootstrap_plan(
                universe_name="scanner-research",
                tickers=BOOTSTRAP_TARGET_TICKERS,
                write_mode="WRITE_PRODUCTION",
                confirm_production_write=True,
                session=None,  # → db_target=unknown
            )

    def test_write_local_against_unknown_db_raises(self):
        with pytest.raises(ValueError, match="db_target"):
            build_bootstrap_plan(
                universe_name="scanner-research",
                tickers=BOOTSTRAP_TARGET_TICKERS,
                write_mode="WRITE_LOCAL",
                confirm_production_write=False,
                session=None,
            )

    def test_dry_run_works_without_session(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=BOOTSTRAP_TARGET_TICKERS,
            write_mode="DRY_RUN",
            confirm_production_write=False,
            session=None,
            today=date(2026, 4, 30),
        )
        assert plan.write_mode == "DRY_RUN"
        assert plan.db_target == "unknown"
        assert len(plan.per_ticker) == 32
        # When no session, nothing is "already_exists" — execute would
        # process all, but we never call execute with a None session.
        assert all(not p.already_exists for p in plan.per_ticker)


# ---------------------------------------------------------------------------
# Banned trading language
# ---------------------------------------------------------------------------


class TestBannedTradingLanguage:
    def test_plan_descriptors_no_banned_phrases(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=BOOTSTRAP_TARGET_TICKERS,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        assert plan.banned_phrases_check == []

    def test_render_plan_report_no_banned_phrases(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=BOOTSTRAP_TARGET_TICKERS,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        report = render_bootstrap_plan_report(plan).lower()
        for f in [
            "buy now", "sell now", "enter long", "enter position",
            "target price", "position size", "leverage on",
            "guaranteed", "certain to rise",
        ]:
            assert f not in report, f"Banned substring '{f}' in plan report"

    def test_render_result_no_banned_phrases(self):
        result = BootstrapResult(
            mode="WRITE_LOCAL",
            db_target="local",
            db_url_label="(forced)",
            universe_name="scanner-research",
            requested_count=1,
            target_count=1,
            succeeded=["AMD"],
            skipped_already_exists=[],
            failed=[],
            instruments_inserted=1,
            identifiers_inserted=1,
            ticker_histories_inserted=1,
            runtime_seconds=0.5,
            per_ticker=[],
        )
        rendered = render_bootstrap_result(result).lower()
        for f in [
            "buy now", "sell now", "enter long", "enter position",
            "target price", "position size", "guaranteed",
        ]:
            assert f not in rendered


# ---------------------------------------------------------------------------
# Source policy: no yfinance_dev, no Polygon, no execution/broker
# ---------------------------------------------------------------------------


class TestSourcePolicy:
    def test_no_yfinance_dev_in_module(self):
        import libs.ingestion.bootstrap_research_universe_prod as mod
        import inspect
        src = inspect.getsource(mod)
        assert '"yfinance_dev"' not in src
        assert "'yfinance_dev'" not in src
        assert "import yfinance" not in src

    def test_no_polygon_or_massive_in_module(self):
        import libs.ingestion.bootstrap_research_universe_prod as mod
        import inspect
        src = inspect.getsource(mod)
        # Bootstrap is an instrument-master operation; pricing providers must
        # NOT be imported here.
        assert "MassiveAdapter" not in src
        assert "from libs.adapters.massive_adapter" not in src

    def test_no_execution_imports(self):
        """Strip the module docstring + render output strings (which
        legitimately list forbidden things as policy commentary) and check
        the executable code body contains no real imports / class refs."""
        import libs.ingestion.bootstrap_research_universe_prod as mod
        import inspect
        src = inspect.getsource(mod)
        # Forbidden Python symbols that would indicate execution-layer usage
        # (CamelCase model classes, real import paths). Lowercase column
        # names like 'order_intent' may appear in docstrings/render output
        # as policy commentary — those are fine.
        for forbidden in [
            "OrderIntent", "OrderDraft",
            "from libs.execution",
            "import libs.execution",
            "ExecutionStateMachine",
        ]:
            assert forbidden not in src, f"forbidden execution import/symbol '{forbidden}' present"

    def test_no_broker_imports(self):
        """No real broker adapters or broker model classes imported. The
        live-submit attestation string ``FEATURE_T212_LIVE_SUBMIT`` legitimately
        appears in the rendered output and is allowed."""
        import libs.ingestion.bootstrap_research_universe_prod as mod
        import inspect
        src = inspect.getsource(mod)
        for forbidden in [
            "from libs.adapters.trading212",
            "import trading212",
            "Trading212Adapter",
            "from libs.db.models.broker_",
            "BrokerAccountSnapshot",
            "BrokerPositionSnapshot",
            "BrokerOrderSnapshot",
        ]:
            assert forbidden not in src, f"forbidden broker reference '{forbidden}' present"

    def test_no_price_bar_raw_import(self):
        import libs.ingestion.bootstrap_research_universe_prod as mod
        import inspect
        src = inspect.getsource(mod)
        # price_bar_raw belongs to sync_eod_prices_universe; bootstrap is
        # explicitly scaffolding-only.
        assert "PriceBarRaw" not in src
        assert "price_bar_raw" not in src.lower() or "price_bar_raw" in mod.__doc__.lower()

    def test_module_docstring_documents_source_policy(self):
        import libs.ingestion.bootstrap_research_universe_prod as mod
        # Docstring must explicitly mention yfinance_dev forbidden
        assert "yfinance_dev" in (mod.__doc__ or "")
        assert "MUST NOT" in (mod.__doc__ or "")


# ---------------------------------------------------------------------------
# Plan report attestations
# ---------------------------------------------------------------------------


class TestPlanReportAttestations:
    def test_report_contains_required_attestations(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=BOOTSTRAP_TARGET_TICKERS,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        report = render_bootstrap_plan_report(plan)
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
            "primary_source          : fmp",
            "yfinance_dev allowed    : NO",
            "target_count            : 32",
            "instrument_identifier   : 1 row per ticker",
        ]:
            assert required in report, f"Missing required attestation: {required}"

    def test_report_lists_protected_tickers_excluded(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=SCANNER_RESEARCH_UNIVERSE,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        report = render_bootstrap_plan_report(plan)
        # Must show all four protected tickers were excluded
        for protected in PROTECTED_TICKERS:
            assert protected in report

    def test_report_documents_tables_not_touched(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=BOOTSTRAP_TARGET_TICKERS,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        report = render_bootstrap_plan_report(plan)
        for explicit_no in [
            "price_bar_raw",
            "corporate_action",
            "earnings_event",
            "watchlist",
            "broker",
            "order_intent / order_draft",
        ]:
            assert explicit_no in report


# ---------------------------------------------------------------------------
# execute_bootstrap — gating
# ---------------------------------------------------------------------------


class TestExecuteBootstrapGating:
    @pytest.mark.asyncio
    async def test_execute_bootstrap_dry_run_refused(self):
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=BOOTSTRAP_TARGET_TICKERS,
            write_mode="DRY_RUN",
            confirm_production_write=False,
        )
        with pytest.raises(ValueError, match="DRY_RUN"):
            await execute_bootstrap(plan, session=None)

    @pytest.mark.asyncio
    async def test_unsupported_write_mode_rejected(self):
        plan = BootstrapPlan(
            universe_name="scanner-research",
            target_tickers=("AMD",),
            requested_tickers=("AMD",),
            protected_excluded=(),
            write_mode="WRITE_UNKNOWN",  # type: ignore[arg-type]
            db_target="local",
            db_url_label="(forced)",
            fmp_delay_seconds=0.0,
            effective_from=DEFAULT_EFFECTIVE_FROM,
            today=date(2026, 4, 30),
            per_ticker=[],
        )
        with pytest.raises(ValueError, match="Unsupported write_mode"):
            await execute_bootstrap(plan, session=None)


# ---------------------------------------------------------------------------
# Defense-in-depth — execute_bootstrap re-checks db_target
# ---------------------------------------------------------------------------


class _FakeLocalBind:
    url = "postgresql+psycopg2://u:p@localhost:5432/quant"


class _FakeProdBind:
    url = "postgresql://u:p@/d?host=/cloudsql/proj:asia-east2:db"


class _FakeSession:
    """Minimal fake session for hermetic tests."""
    def __init__(self, bind=None, existing_tickers=None):
        self._bind = bind or _FakeLocalBind()
        self._existing = set(existing_tickers or [])
        self.commit_count = 0
        self.rollback_count = 0
        self.executed_inserts = []  # capture model writes for inspection

    def get_bind(self):
        return self._bind

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1

    def execute(self, sql, params=None):
        sql_text = str(sql)
        # Existing-ticker lookup
        if "FROM instrument_identifier" in sql_text and "id_value = ANY" in sql_text:
            class _R:
                def __init__(self, rows): self._rows = rows
                def fetchall(self): return self._rows
            requested = (params or {}).get("tickers", [])
            return _R([(t,) for t in requested if t in self._existing])
        # Fallback for compiled INSERT statements (instrument / identifier /
        # ticker_history). We treat them as 1-row inserts.
        self.executed_inserts.append(sql_text[:60])

        class _R:
            rowcount = 1
        return _R()


class TestDefenseInDepthDbTarget:
    @pytest.mark.asyncio
    async def test_write_local_with_production_target_refused(self):
        # Hand-build a contradictory plan
        plan = BootstrapPlan(
            universe_name="scanner-research",
            target_tickers=("AMD",),
            requested_tickers=("AMD",),
            protected_excluded=(),
            write_mode="WRITE_LOCAL",
            db_target="production",  # contradiction
            db_url_label="(forced)",
            fmp_delay_seconds=0.0,
            effective_from=DEFAULT_EFFECTIVE_FROM,
            today=date(2026, 4, 30),
            per_ticker=[TickerBootstrap(
                ticker="AMD",
                already_exists=False,
                asset_type="EQUITY",
                note="scaffold needed",
            )],
        )
        with pytest.raises(ValueError, match="REFUSED"):
            await execute_bootstrap(plan, session=_FakeSession())

    @pytest.mark.asyncio
    async def test_write_production_with_local_target_refused(self):
        plan = BootstrapPlan(
            universe_name="scanner-research",
            target_tickers=("AMD",),
            requested_tickers=("AMD",),
            protected_excluded=(),
            write_mode="WRITE_PRODUCTION",
            db_target="local",  # contradiction
            db_url_label="(forced)",
            fmp_delay_seconds=0.0,
            effective_from=DEFAULT_EFFECTIVE_FROM,
            today=date(2026, 4, 30),
            per_ticker=[TickerBootstrap(
                ticker="AMD",
                already_exists=False,
                asset_type="EQUITY",
                note="scaffold needed",
            )],
        )
        with pytest.raises(ValueError, match="REFUSED"):
            await execute_bootstrap(plan, session=_FakeSession())

    @pytest.mark.asyncio
    async def test_planner_refuses_production_target_with_local_url(self):
        """Planner-level guard: passing a local-bound session with WRITE_PRODUCTION
        must be refused at build_bootstrap_plan time."""
        with pytest.raises(ValueError, match="db_target"):
            build_bootstrap_plan(
                universe_name="scanner-research",
                tickers=("AMD",),
                write_mode="WRITE_PRODUCTION",
                confirm_production_write=True,
                session=_FakeSession(bind=_FakeLocalBind()),
            )


# ---------------------------------------------------------------------------
# Idempotency: existing ticker is skipped
# ---------------------------------------------------------------------------


async def _noop_sleep(_seconds: float) -> None:
    return None


class TestIdempotency:
    @pytest.mark.asyncio
    async def test_existing_ticker_marked_already_exists_at_plan(self):
        sess = _FakeSession(existing_tickers=["AMD"])
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("AMD", "TSLA"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )
        amd = next(p for p in plan.per_ticker if p.ticker == "AMD")
        tsla = next(p for p in plan.per_ticker if p.ticker == "TSLA")
        assert amd.already_exists is True
        assert tsla.already_exists is False

    @pytest.mark.asyncio
    async def test_existing_ticker_skipped_during_execute_no_fmp_call(self):
        sess = _FakeSession(existing_tickers=["AMD"])
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("AMD", "TSLA"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )

        fmp_called = []

        async def fake_fmp(ticker):
            fmp_called.append(ticker)
            return {"companyName": f"{ticker} Corp", "exchange": "NASDAQ",
                    "currency": "USD", "country": "US"}

        result = await execute_bootstrap(
            plan, session=sess,
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        # AMD is already-exists; only TSLA hits FMP
        assert fmp_called == ["TSLA"]
        assert "AMD" in result.skipped_already_exists
        assert "TSLA" in result.succeeded

    @pytest.mark.asyncio
    async def test_existing_ticker_no_db_writes(self):
        sess = _FakeSession(existing_tickers=["AMD"])
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("AMD",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )

        async def fake_fmp(ticker):
            raise AssertionError("FMP must not be called for already-existing ticker")

        result = await execute_bootstrap(
            plan, session=sess,
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        assert result.skipped_already_exists == ["AMD"]
        assert result.succeeded == []
        assert result.instruments_inserted == 0
        assert result.identifiers_inserted == 0
        assert result.ticker_histories_inserted == 0


# ---------------------------------------------------------------------------
# Per-ticker isolation
# ---------------------------------------------------------------------------


class TestPerTickerIsolation:
    @pytest.mark.asyncio
    async def test_one_ticker_fmp_failure_does_not_abort_others(self):
        sess = _FakeSession()
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("AMD", "TSLA", "GOOGL"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )

        async def fake_fmp(ticker):
            if ticker == "TSLA":
                raise RuntimeError("simulated TSLA FMP failure")
            return {"companyName": f"{ticker} Corp"}

        result = await execute_bootstrap(
            plan, session=sess,
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        # AMD and GOOGL succeed (with full fallbacks because mocked profile
        # only has companyName); TSLA also succeeds because FMP failure does
        # NOT prevent scaffolding — fallbacks kick in.
        assert sorted(result.succeeded) == ["AMD", "GOOGL", "TSLA"]
        # TSLA's per-ticker record has fmp_error populated
        tsla = next(p for p in result.per_ticker if p.ticker == "TSLA")
        assert tsla.fmp_error is not None
        assert "TSLA FMP failure" in tsla.fmp_error
        # TSLA used the issuer fallback (because FMP errored, profile is None)
        assert tsla.used_fallback_issuer is True
        assert tsla.issuer_name == "TSLA"  # ticker fallback
        assert tsla.exchange == "UNKNOWN"
        assert tsla.currency == "USD"
        assert tsla.country_code == "US"

    @pytest.mark.asyncio
    async def test_db_write_failure_records_failure_does_not_abort(self):
        """AMD scaffolding succeeds (3 inserts: instrument/identifier/history).
        TSLA's first insert (instrument) fails — TSLA is recorded as failed
        but the batch continues (in this test there's nothing after TSLA).
        Each ticker's writes are isolated by per-ticker commit/rollback."""
        class _FailingSession(_FakeSession):
            def __init__(self):
                super().__init__()
                self.calls = 0

            def execute(self, sql, params=None):
                sql_text = str(sql)
                if "FROM instrument_identifier" in sql_text and "id_value = ANY" in sql_text:
                    return super().execute(sql, params)
                self.calls += 1
                # AMD writes: calls 1 (instrument), 2 (identifier), 3 (history).
                # TSLA writes start at call 4 — fail on TSLA's first insert.
                if self.calls == 4:
                    raise RuntimeError("simulated DB insert failure on TSLA")
                class _R:
                    rowcount = 1
                return _R()

        sess = _FailingSession()
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("AMD", "TSLA"),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )

        async def fake_fmp(ticker):
            return {"companyName": f"{ticker} Corp"}

        result = await execute_bootstrap(
            plan, session=sess,
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        # AMD succeeds; TSLA fails — failure does NOT abort the batch
        assert "AMD" in result.succeeded
        assert any(t == "TSLA" for t, _ in result.failed)
        # Rollback was called for TSLA failure
        assert sess.rollback_count >= 1
        # AMD's 3 inserts persisted via per-ticker commit
        assert result.instruments_inserted == 1
        assert result.identifiers_inserted == 1
        assert result.ticker_histories_inserted == 1


# ---------------------------------------------------------------------------
# Successful WRITE_LOCAL path — full scaffolding
# ---------------------------------------------------------------------------


class TestSuccessfulWriteLocal:
    @pytest.mark.asyncio
    async def test_successful_run_inserts_three_rows_per_ticker(self):
        sess = _FakeSession()
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("AMD",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )

        async def fake_fmp(ticker):
            return {
                "companyName": "Advanced Micro Devices, Inc.",
                "exchange": "NASDAQ",
                "currency": "USD",
                "country": "US",
            }

        result = await execute_bootstrap(
            plan, session=sess,
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        assert result.succeeded == ["AMD"]
        assert result.failed == []
        assert result.instruments_inserted == 1
        assert result.identifiers_inserted == 1
        assert result.ticker_histories_inserted == 1
        assert sess.commit_count == 1

    @pytest.mark.asyncio
    async def test_etf_ticker_gets_etf_asset_type(self):
        sess = _FakeSession()
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("QQQ",),  # not protected, is ETF
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )
        # Pre-execute: per_ticker shows ETF
        qqq_plan = plan.per_ticker[0]
        assert qqq_plan.asset_type == "ETF"

        async def fake_fmp(ticker):
            return {"companyName": "Invesco QQQ Trust", "exchange": "NASDAQ"}

        result = await execute_bootstrap(
            plan, session=sess,
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        assert result.succeeded == ["QQQ"]
        qqq_result = result.per_ticker[0]
        assert qqq_result.asset_type == "ETF"

    @pytest.mark.asyncio
    async def test_equity_ticker_gets_equity_asset_type(self):
        sess = _FakeSession()
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("TSLA",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )
        tsla_plan = plan.per_ticker[0]
        assert tsla_plan.asset_type == "EQUITY"


# ---------------------------------------------------------------------------
# Side-effect attestations on result
# ---------------------------------------------------------------------------


class TestResultSideEffectAttestations:
    @pytest.mark.asyncio
    async def test_result_attests_no_dangerous_side_effects(self):
        sess = _FakeSession()
        plan = build_bootstrap_plan(
            universe_name="scanner-research",
            tickers=("AMD",),
            write_mode="WRITE_LOCAL",
            confirm_production_write=False,
            session=sess,
            fmp_delay_seconds=0.0,
        )

        async def fake_fmp(ticker):
            return {"companyName": "AMD"}

        result = await execute_bootstrap(
            plan, session=sess,
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        assert result.cloud_run_jobs_created == "NONE"
        assert result.scheduler_changes == "NONE"
        assert result.production_deploy == "NONE"
        assert result.execution_objects == "NONE"
        assert result.broker_write == "NONE"
        assert "LOCKED" in result.live_submit
        # WRITE_LOCAL label
        assert "LOCAL" in result.db_writes_performed.upper()
        assert "instrument" in result.db_writes_performed
        assert "instrument_identifier" in result.db_writes_performed
        assert "ticker_history" in result.db_writes_performed

    def test_render_result_includes_attestations(self):
        result = BootstrapResult(
            mode="WRITE_LOCAL",
            db_target="local",
            db_url_label="postgresql:***@localhost",
            universe_name="scanner-research",
            requested_count=32,
            target_count=32,
            succeeded=["AMD"] * 32,
            skipped_already_exists=[],
            failed=[],
            instruments_inserted=32,
            identifiers_inserted=32,
            ticker_histories_inserted=32,
            runtime_seconds=33.4,
            per_ticker=[],
        )
        rendered = render_bootstrap_result(result)
        for required in [
            "Cloud Run jobs created       : NONE",
            "Scheduler changes            : NONE",
            "Production deploy            : NONE",
            "Execution objects            : NONE",
            "Broker write                 : NONE",
            "LOCKED",
        ]:
            assert required in rendered

    @pytest.mark.asyncio
    async def test_production_mode_label_distinguishes_from_local(self):
        # We can't actually exercise WRITE_PRODUCTION without a prod-bound
        # session, but we can hand-build a plan with db_target=production
        # and verify the result label.
        plan = BootstrapPlan(
            universe_name="scanner-research",
            target_tickers=("AMD",),
            requested_tickers=("AMD",),
            protected_excluded=(),
            write_mode="WRITE_PRODUCTION",
            db_target="production",
            db_url_label="(forced)",
            fmp_delay_seconds=0.0,
            effective_from=DEFAULT_EFFECTIVE_FROM,
            today=date(2026, 4, 30),
            per_ticker=[TickerBootstrap(
                ticker="AMD",
                already_exists=False,
                asset_type="EQUITY",
                note="scaffold needed",
            )],
        )

        async def fake_fmp(ticker):
            return {"companyName": "AMD"}

        result = await execute_bootstrap(
            plan, session=_FakeSession(),
            sleep_fn=_noop_sleep, fmp_profile_fetch=fake_fmp,
        )
        assert "PRODUCTION" in result.db_writes_performed.upper()
        assert "Cloud SQL" in result.db_writes_performed


# ---------------------------------------------------------------------------
# Production-write guard message presence
# ---------------------------------------------------------------------------


class TestProductionWriteGuardMessage:
    def test_guard_message_lists_four_flags(self):
        msg = PRODUCTION_WRITE_GUARD_MESSAGE
        for flag in ["--no-dry-run", "--write", "--db-target=production",
                     "--confirm-production-write"]:
            assert flag in msg

    def test_guard_message_references_runbook(self):
        assert "runbook" in PRODUCTION_WRITE_GUARD_MESSAGE.lower()
