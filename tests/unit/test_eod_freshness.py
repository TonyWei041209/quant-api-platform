"""EOD freshness invariant — unit tests.

Pure-function tests with no DB and no provider HTTP. The helper is
designed to be hermetic so the four ``freshness_status`` branches can
be exercised deterministically.

Coverage:
  * fresh / provider_lag / stale / partial statuses
  * empty DB → stale
  * mirror-bootstrap bar-less tickers don't get counted as stale
  * strict_mode flag is surfaced but never controls flow inside the helper
  * the render block prints all the expected fields
  * source-grep guard on the module to confirm no broker / order /
    live-submit / scraping references
"""
from __future__ import annotations

import inspect
import io
import tokenize
from datetime import date

import pytest

from libs.ingestion import eod_freshness as ef


def _strip(src: str) -> str:
    out: list[str] = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (
                tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING,
            ):
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    return "".join(out)


class TestExpectedMinTradeDate:
    def test_tuesday_today_gives_monday_expected(self):
        # 2026-05-12 is a Tuesday — previous weekday is Monday 2026-05-11
        assert ef.expected_min_trade_date_for(date(2026, 5, 12)) == date(2026, 5, 11)

    def test_monday_today_gives_friday_expected(self):
        # 2026-05-11 is a Monday — previous weekday is Friday 2026-05-08
        assert ef.expected_min_trade_date_for(date(2026, 5, 11)) == date(2026, 5, 8)

    def test_saturday_today_gives_friday_expected(self):
        # 2026-05-09 is a Saturday — previous weekday is Friday 2026-05-08
        assert ef.expected_min_trade_date_for(date(2026, 5, 9)) == date(2026, 5, 8)

    def test_sunday_today_gives_friday_expected(self):
        # 2026-05-10 is a Sunday — previous weekday is Friday 2026-05-08
        assert ef.expected_min_trade_date_for(date(2026, 5, 10)) == date(2026, 5, 8)


class TestStrictModeFlag:
    @pytest.mark.parametrize("v", ["1", "true", "yes", "on", "TRUE"])
    def test_truthy_values(self, monkeypatch, v):
        monkeypatch.setenv("EOD_FRESHNESS_STRICT_MODE", v)
        assert ef.is_strict_mode_enabled() is True

    @pytest.mark.parametrize("v", ["", "0", "false", "no", "off", "FALSE"])
    def test_falsy_values(self, monkeypatch, v):
        monkeypatch.setenv("EOD_FRESHNESS_STRICT_MODE", v)
        assert ef.is_strict_mode_enabled() is False

    def test_unset_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv("EOD_FRESHNESS_STRICT_MODE", raising=False)
        assert ef.is_strict_mode_enabled() is False


class TestFreshnessStatus:
    """The four canonical statuses from the docstring."""

    def test_fresh_status(self):
        """db_max equals expected_min_trade_date → fresh."""
        # Today = Tue 2026-05-12, expected_min = Mon 2026-05-11
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 11),
        )
        assert r.freshness_status == "fresh"
        assert r.warning_message is None
        assert r.expected_min_trade_date == date(2026, 5, 11)

    def test_fresh_when_db_ahead_of_expected(self):
        """db_max > expected_min still counts as fresh."""
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 12),  # already has today
        )
        assert r.freshness_status == "fresh"

    def test_provider_lag_status(self):
        """1-2 days behind expected_min → provider_lag (transient)."""
        # Today = Wed 2026-05-13, expected_min = Tue 2026-05-12,
        # db_max = Mon 2026-05-11 (1 day behind expected)
        r = ef.compute_freshness_report(
            today=date(2026, 5, 13),
            db_max_trade_date=date(2026, 5, 11),
        )
        assert r.freshness_status == "provider_lag"
        assert r.warning_message and "provider_lag" in r.warning_message
        assert "1 days behind" in r.warning_message

    def test_stale_status_when_too_many_days_behind(self):
        """≥ stale_after_days behind → stale."""
        # Today = 2026-05-15 (Friday), expected_min = 2026-05-14 (Thursday),
        # db_max = 2026-05-08 (Friday a week ago) → 6 days behind expected
        r = ef.compute_freshness_report(
            today=date(2026, 5, 15),
            db_max_trade_date=date(2026, 5, 8),
            stale_after_days=3,
        )
        assert r.freshness_status == "stale"
        assert r.warning_message and "stale" in r.warning_message

    def test_stale_status_when_db_empty(self):
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=None,
        )
        assert r.freshness_status == "stale"
        assert r.warning_message and "no bars in DB" in r.warning_message

    def test_partial_status(self):
        """Some tickers fresh, some stale → partial."""
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 11),  # overall fresh
            per_ticker_max_trade_date={
                "NVDA": date(2026, 5, 11),  # fresh
                "MU": date(2026, 5, 11),    # fresh
                "AAPL": date(2026, 5, 8),   # stale
                "AMD": date(2026, 5, 8),    # stale
            },
        )
        assert r.freshness_status == "partial"
        assert r.fresh_ticker_count == 2
        assert r.stale_ticker_count == 2
        assert r.bar_less_ticker_count == 0
        assert r.warning_message and "partial" in r.warning_message


class TestBarLessTickers:
    """Mirror-bootstrap tickers have no bars by design — these should
    NOT be counted as stale and SHOULD be counted separately."""

    def test_bar_less_does_not_make_overall_partial(self):
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 11),
            per_ticker_max_trade_date={
                "NVDA": date(2026, 5, 11),
                "MU": date(2026, 5, 11),
                # Bootstrap scaffold-only tickers — no bars by design
                "NOK": None,
                "AAOI": None,
            },
            bar_less_tickers=["NOK", "AAOI"],
        )
        # 2 fresh, 0 stale, 2 bar-less → status should remain fresh
        # because no ticker is "stale" (the bar-less ones are flagged
        # separately, not as stale).
        assert r.freshness_status == "fresh"
        assert r.fresh_ticker_count == 2
        assert r.stale_ticker_count == 0
        assert r.bar_less_ticker_count == 2

    def test_bar_less_count_reflects_per_ticker_input(self):
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 11),
            per_ticker_max_trade_date={f"X{i}": None for i in range(7)},
            bar_less_tickers=[f"X{i}" for i in range(7)],
        )
        assert r.bar_less_ticker_count == 7
        # All tickers are bar-less → no fresh, no stale, status is fresh
        # (overall DB is fresh, no contradicting tickers).
        assert r.fresh_ticker_count == 0
        assert r.stale_ticker_count == 0


class TestStaleAfterDaysBoundary:
    """The provider_lag → stale boundary is exactly stale_after_days."""

    def test_at_boundary_still_provider_lag(self):
        # expected_min = 2026-05-12 (Tue), db_max = 2026-05-09 (Sat though
        # the helper doesn't filter holidays) → 3 days behind. Boundary
        # is days_behind <= stale_after_days (= 3) → provider_lag.
        r = ef.compute_freshness_report(
            today=date(2026, 5, 13),
            db_max_trade_date=date(2026, 5, 9),
            stale_after_days=3,
        )
        assert r.freshness_status == "provider_lag"

    def test_one_past_boundary_is_stale(self):
        # expected_min = 2026-05-12 (Tue), db_max = 2026-05-08 (Fri)
        # 4 days behind > 3 → stale.
        r = ef.compute_freshness_report(
            today=date(2026, 5, 13),
            db_max_trade_date=date(2026, 5, 8),
            stale_after_days=3,
        )
        assert r.freshness_status == "stale"


class TestReportShape:
    def test_to_dict_round_trip(self):
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 11),
        )
        d = r.to_dict()
        assert d["today"] == "2026-05-12"
        assert d["expected_min_trade_date"] == "2026-05-11"
        assert d["latest_trade_date"] == "2026-05-11"
        assert d["freshness_status"] == "fresh"
        assert d["fresh_ticker_count"] == 0
        assert "warning_message" in d
        assert "strict_mode" in d

    def test_render_freshness_block_contains_status_line(self):
        r = ef.compute_freshness_report(
            today=date(2026, 5, 13),
            db_max_trade_date=date(2026, 5, 11),
        )
        out = ef.render_freshness_block(r)
        assert "freshness_status             : provider_lag" in out
        assert "today                        : 2026-05-13" in out
        assert "expected_min_trade_date      : 2026-05-12" in out
        assert "latest_trade_date            : 2026-05-11" in out
        assert "warning" in out

    def test_render_freshness_block_no_warning_when_fresh(self):
        r = ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 11),
        )
        out = ef.render_freshness_block(r)
        assert "freshness_status             : fresh" in out
        # No warning line when status is fresh
        assert "warning                      :" not in out


class TestLoggingBehaviour:
    """Helper logs WARNING when stale/lag, never raises, never exits."""

    def test_stale_emits_warning(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        ef.compute_freshness_report(
            today=date(2026, 5, 15),
            db_max_trade_date=date(2026, 5, 8),
            stale_after_days=3,
        )
        assert any(
            "eod_freshness_check" in r.message and "stale" in r.message
            for r in caplog.records
        )

    def test_fresh_emits_no_warning(self, caplog):
        import logging
        caplog.set_level(logging.WARNING)
        ef.compute_freshness_report(
            today=date(2026, 5, 12),
            db_max_trade_date=date(2026, 5, 11),
        )
        assert not any(
            "eod_freshness_check" in r.message
            for r in caplog.records
        )

    def test_strict_mode_only_surfaces_on_report(self, monkeypatch, caplog):
        """Even in strict mode the helper itself never raises; it just
        marks the report so a caller can choose to exit non-zero."""
        monkeypatch.setenv("EOD_FRESHNESS_STRICT_MODE", "true")
        r = ef.compute_freshness_report(
            today=date(2026, 5, 13),
            db_max_trade_date=date(2026, 5, 11),
        )
        assert r.strict_mode is True
        assert r.freshness_status == "provider_lag"
        # Did NOT raise; sync job decides what to do with strict_mode + status


class TestNoForbiddenSymbols:
    """Source-grep guards on the module."""

    def test_module_is_research_only(self):
        src = _strip(inspect.getsource(ef))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "/equity/orders/limit", "/equity/orders/market",
            "FEATURE_T212_LIVE_SUBMIT", "live_submit",
            "broker_account_snapshot", "broker_position_snapshot",
            "broker_order_snapshot",
            "selenium", "playwright", "puppeteer", "webdriver",
            "BeautifulSoup",
        ):
            assert needle.lower() not in src.lower(), (
                f"eod_freshness must not reference {needle!r}"
            )

    def test_module_no_provider_http_in_pure_path(self):
        """compute_freshness_report MUST be a pure function — no provider
        HTTP. Only query_db_freshness reads from a DB session, and it
        only does SELECTs."""
        src = inspect.getsource(ef.compute_freshness_report)
        for needle in (
            "requests.", "httpx.", "aiohttp.",
            "MassiveAdapter", "FMPAdapter", "T212Adapter",
            "session.add", "session.commit", "INSERT", "UPDATE", "DELETE",
        ):
            assert needle not in src, (
                f"compute_freshness_report must be a pure function — "
                f"found {needle!r}"
            )
