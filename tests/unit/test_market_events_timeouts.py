"""P0 Market Events timeout hardening tests.

Hermetic: never hits FMP. Provider fetchers are injected via the
public ``fmp_fetcher`` / ``fmp_news_fetcher`` / ``fmp_profile_fetcher``
parameters. Each test exercises one of the spec's hardening rules.
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from libs.market_events import providers as p
from libs.market_events import market_events_service as svc


@pytest.fixture(autouse=True)
def _reset_caches():
    p.reset_caches_for_tests()
    yield
    p.reset_caches_for_tests()


# ---------------------------------------------------------------------------
# Section-level isolation
# ---------------------------------------------------------------------------


class TestSectionIsolation:
    def _patch_mirror(self, monkeypatch, items):
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: {"items": items},
        )

    def test_news_timeout_returns_200_with_earnings(self, monkeypatch):
        """News timeout must not hide a successful earnings fetch."""
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        self._patch_mirror(monkeypatch, [
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def fast_earnings(start, end):
            return [{"symbol": "MU", "date": "2026-05-12"}]

        async def slow_news(tickers, fd, td, lim):
            await asyncio.sleep(20.0)  # would exceed the section budget
            return []

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror", days=7,
            earnings_provider=fast_earnings, news_provider=slow_news,
        ))
        # Earnings still returned. News marked timeout. Top-level still 200.
        assert feed["counts"]["earnings"] == 1
        assert feed["provider_status"]["fmp_earnings"] == "ok"
        assert feed["provider_status"]["fmp_news"] == "timeout"
        assert feed["any_section_partial"] is True

    def test_earnings_ok_news_error_still_returns_earnings(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        self._patch_mirror(monkeypatch, [
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def ok_earnings(start, end):
            return [{"symbol": "MU", "date": "2026-05-12"}]

        async def boom_news(tickers, fd, td, lim):
            raise RuntimeError("upstream 500")

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror",
            earnings_provider=ok_earnings, news_provider=boom_news,
        ))
        assert feed["counts"]["earnings"] == 1
        assert feed["provider_status"]["fmp_news"] == "error"
        assert feed["any_section_partial"] is True

    def test_earnings_error_news_ok_still_returns_news(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        self._patch_mirror(monkeypatch, [
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def boom_earnings(start, end):
            raise RuntimeError("upstream 500")

        async def ok_news(tickers, fd, td, lim):
            return [{"symbol": "MU", "title": "x", "publishedDate": "2026-05-08"}]

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror",
            earnings_provider=boom_earnings, news_provider=ok_news,
        ))
        assert feed["counts"]["news"] == 1
        assert feed["provider_status"]["fmp_earnings"] == "error"
        assert feed["any_section_partial"] is True

    def test_both_sections_ok_partial_flag_false(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        self._patch_mirror(monkeypatch, [
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def ok_earnings(start, end):
            return [{"symbol": "MU", "date": "2026-05-12"}]

        async def ok_news(tickers, fd, td, lim):
            return [{"symbol": "MU", "title": "x", "publishedDate": "2026-05-08"}]

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror",
            earnings_provider=ok_earnings, news_provider=ok_news,
        ))
        assert feed["any_section_partial"] is False


# ---------------------------------------------------------------------------
# News top-N bound
# ---------------------------------------------------------------------------


class TestNewsTopN:
    def _patch_mirror(self, monkeypatch, items):
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: {"items": items},
        )

    def test_mirror_news_capped_at_top_n_default(self, monkeypatch):
        """A 22-ticker mirror must not trigger 22 news calls — only top 5."""
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        items = [
            {"display_ticker": f"X{i}", "broker_ticker": f"X{i}_US_EQ",
             "source_tags": ["WATCHED"], "mapping_status": "unresolved"}
            for i in range(22)
        ]
        self._patch_mirror(monkeypatch, items)

        captured_news_tickers = []

        async def ok_earnings(start, end):
            return []

        async def capture_news(tickers, fd, td, lim):
            captured_news_tickers.extend(tickers)
            return []

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror",
            earnings_provider=ok_earnings, news_provider=capture_news,
        ))
        assert len(captured_news_tickers) == svc.NEWS_TOP_N_DEFAULT
        assert feed["counts"]["news_tickers_used"] == svc.NEWS_TOP_N_DEFAULT

    def test_news_top_n_param_respected_with_ceiling(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        items = [
            {"display_ticker": f"X{i}", "broker_ticker": f"X{i}_US_EQ",
             "source_tags": ["WATCHED"], "mapping_status": "unresolved"}
            for i in range(80)
        ]
        self._patch_mirror(monkeypatch, items)

        captured = []

        async def ok_earnings(start, end):
            return []

        async def capture_news(tickers, fd, td, lim):
            captured.extend(tickers)
            return []

        # Caller asks for far more than the ceiling
        asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror", news_top_n=99999,
            earnings_provider=ok_earnings, news_provider=capture_news,
        ))
        assert len(captured) == svc.NEWS_TOP_N_CEILING


# ---------------------------------------------------------------------------
# Provider-level wait_for + stale-on-fail
# ---------------------------------------------------------------------------


class TestProviderTimeoutAndStaleCache:
    def test_earnings_provider_timeout_returns_status_timeout(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def slow(start, end):
            await asyncio.sleep(20.0)
            return []

        result = asyncio.run(p.get_earnings_calendar(
            "2026-05-09", "2026-05-16", fmp_fetcher=slow,
        ))
        assert result.status == "timeout"
        assert "timeout" in (result.error or "").lower()

    def test_earnings_stale_cache_served_when_refresh_fails(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def good(start, end):
            return [{"symbol": "MU", "date": "2026-05-12"}]

        async def boom(start, end):
            raise RuntimeError("simulated")

        # First call seeds cache
        first = asyncio.run(p.get_earnings_calendar(
            "2026-05-09", "2026-05-16", fmp_fetcher=good,
        ))
        assert first.status == "ok"

        # Force expiry so the next call goes through fetch
        key = "earnings::2026-05-09::2026-05-16"
        p._earnings_cache._entries[key].fetched_at = 0

        # Second call fails → must serve stale cache, not empty error
        second = asyncio.run(p.get_earnings_calendar(
            "2026-05-09", "2026-05-16", fmp_fetcher=boom,
        ))
        assert second.status == "cached"
        assert second.data == [{"symbol": "MU", "date": "2026-05-12"}]
        assert "refresh failed" in (second.note or "")

    def test_news_stale_cache_served_when_refresh_fails(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def good(tickers, fd, td, lim):
            return [{"symbol": "MU", "title": "x", "publishedDate": "2026-05-08"}]

        async def boom(tickers, fd, td, lim):
            raise RuntimeError("simulated")

        first = asyncio.run(p.get_stock_news(
            ["MU"], "2026-05-02", "2026-05-09", fmp_news_fetcher=good,
        ))
        assert first.status == "ok"

        key = "news::2026-05-02::2026-05-09::MU::5"
        p._news_cache._entries[key].fetched_at = 0

        second = asyncio.run(p.get_stock_news(
            ["MU"], "2026-05-02", "2026-05-09", fmp_news_fetcher=boom,
        ))
        assert second.status == "cached"
        assert second.data == [{"symbol": "MU", "title": "x", "publishedDate": "2026-05-08"}]


# ---------------------------------------------------------------------------
# No DB / no T212 / no execution / no scraping (pinned)
# ---------------------------------------------------------------------------


class TestNoForbiddenSymbolsP0:
    """P0 changes must not introduce any DB write, T212 write, or
    execution-object reference. The full source-grep tests in
    test_no_trading_writes.py + test_market_events.py already cover the
    base modules; these are the diff-pin versions."""

    def test_providers_module_no_db_writes(self):
        import inspect
        import io
        import tokenize
        src = inspect.getsource(p)
        out = []
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
        stripped = "".join(out)
        for needle in ("session.add", "session.commit", "INSERT INTO",
                       "submit_limit_order", "submit_market_order",
                       "OrderIntent", "OrderDraft",
                       "/equity/orders/limit", "/equity/orders/market",
                       "selenium", "playwright", "puppeteer", "webdriver"):
            assert needle not in stripped, f"providers must not contain {needle!r}"

    def test_service_module_no_db_writes(self):
        import inspect
        import io
        import tokenize
        src = inspect.getsource(svc)
        out = []
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
        stripped = "".join(out)
        for needle in ("session.add", "session.commit",
                       "submit_limit_order", "submit_market_order",
                       "OrderIntent", "OrderDraft",
                       "/equity/orders/limit", "/equity/orders/market",
                       "selenium", "playwright", "puppeteer", "webdriver"):
            assert needle not in stripped, f"service must not contain {needle!r}"
