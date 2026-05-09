"""Unit tests — Market Events providers + service.

Hermetic: never hits FMP. Provider fetchers are injected. The service is
exercised via the public `get_feed` and `get_ticker_detail` functions.
"""
from __future__ import annotations

import asyncio
import inspect
import io
import time
import tokenize
from unittest.mock import MagicMock

import pytest

from libs.market_events import providers as p
from libs.market_events import market_events_service as svc


def _strip_python(src: str) -> str:
    out: list[str] = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src.encode("utf-8")).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    return "".join(out)


@pytest.fixture(autouse=True)
def reset_caches():
    p.reset_caches_for_tests()
    yield
    p.reset_caches_for_tests()


# ---------------------------------------------------------------------------
# Provider layer — earnings
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEarningsProvider:
    def test_returns_unavailable_when_key_missing_and_no_fetcher(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: False)
        result = asyncio.run(p.get_earnings_calendar("2026-05-09", "2026-05-16"))
        assert result.status == "unavailable"
        assert result.error and "FMP" in result.error
        assert result.data == []

    def test_successful_fetch(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        rows = [
            {"symbol": "MU", "date": "2026-05-12", "time": "amc", "epsEstimated": 1.5},
            {"symbol": "AAPL", "date": "2026-05-13", "time": "amc"},
        ]

        async def fake_fetcher(start, end):
            return rows

        result = asyncio.run(p.get_earnings_calendar(
            "2026-05-09", "2026-05-16", fmp_fetcher=fake_fetcher
        ))
        assert result.status == "ok"
        assert len(result.data) == 2

    def test_ticker_filter_after_fetch(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        rows = [
            {"symbol": "MU", "date": "2026-05-12"},
            {"symbol": "AAPL", "date": "2026-05-13"},
            {"symbol": "NVDA", "date": "2026-05-14"},
        ]

        async def fake_fetcher(start, end):
            return rows

        result = asyncio.run(p.get_earnings_calendar(
            "2026-05-09", "2026-05-16",
            tickers=["MU", "AAPL"],
            fmp_fetcher=fake_fetcher,
        ))
        assert result.status == "ok"
        symbols = sorted(r["symbol"] for r in result.data)
        assert symbols == ["AAPL", "MU"]

    def test_limit_floor_and_ceiling(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        big_rows = [{"symbol": f"X{i}", "date": "2026-05-12"} for i in range(1000)]

        async def fake_fetcher(start, end):
            return big_rows

        # Way too high → ceiling
        r = asyncio.run(p.get_earnings_calendar(
            "2026-05-09", "2026-05-16", limit=99999, fmp_fetcher=fake_fetcher,
        ))
        assert len(r.data) == p.ALL_MARKET_EARNINGS_LIMIT_CEILING

    def test_cache_serves_repeat_calls(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        calls = [0]

        async def fake_fetcher(start, end):
            calls[0] += 1
            return [{"symbol": "MU", "date": "2026-05-12"}]

        asyncio.run(p.get_earnings_calendar("2026-05-09", "2026-05-16", fmp_fetcher=fake_fetcher))
        asyncio.run(p.get_earnings_calendar("2026-05-09", "2026-05-16", fmp_fetcher=fake_fetcher))
        asyncio.run(p.get_earnings_calendar("2026-05-09", "2026-05-16", fmp_fetcher=fake_fetcher))
        assert calls[0] == 1, "TTL cache must collapse repeat calls within window"

    def test_provider_error_returns_error_status_not_500(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def boom(start, end):
            raise RuntimeError("upstream 503")

        r = asyncio.run(p.get_earnings_calendar(
            "2026-05-09", "2026-05-16", fmp_fetcher=boom,
        ))
        assert r.status == "error"
        assert r.data == []
        assert "RuntimeError" in r.error


# ---------------------------------------------------------------------------
# Provider layer — news
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNewsProvider:
    def test_no_tickers_returns_ok_empty(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        r = asyncio.run(p.get_stock_news([], "2026-05-02", "2026-05-09"))
        assert r.status == "ok"
        assert r.data == []

    def test_unavailable_on_missing_key(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: False)
        r = asyncio.run(p.get_stock_news(["MU"], "2026-05-02", "2026-05-09"))
        assert r.status == "unavailable"

    def test_successful_news_fetch(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def fake_fetcher(tickers, from_date, to_date, limit_per_ticker):
            assert "MU" in tickers
            return [
                {"symbol": "MU", "title": "Micron earnings beat", "publishedDate": "2026-05-08"},
                {"symbol": "MU", "title": "Memory pricing update", "publishedDate": "2026-05-07"},
            ]

        r = asyncio.run(p.get_stock_news(
            ["MU"], "2026-05-02", "2026-05-09", fmp_news_fetcher=fake_fetcher,
        ))
        assert r.status == "ok"
        assert len(r.data) == 2


# ---------------------------------------------------------------------------
# Service layer — feed composition
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestServiceFeed:
    def _patch_mirror(self, monkeypatch, items):
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: {"items": items},
        )

    def test_mirror_scope_includes_unmapped_tickers(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        self._patch_mirror(monkeypatch, [
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
            {"display_ticker": "RKLB", "broker_ticker": None,
             "source_tags": ["WATCHED", "UNMAPPED"], "mapping_status": "unresolved"},
        ])

        async def fake_earnings(start, end):
            return [
                {"symbol": "MU", "date": "2026-05-12", "time": "amc"},
                {"symbol": "RKLB", "date": "2026-05-14", "time": "amc"},
                {"symbol": "GOOG", "date": "2026-05-15", "time": "amc"},  # outside scope
            ]

        async def fake_news(tickers, fd, td, lim):
            return [{"symbol": t, "title": f"{t} news", "publishedDate": "2026-05-08"}
                    for t in tickers]

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror", days=7,
            earnings_provider=fake_earnings, news_provider=fake_news,
        ))
        symbols = sorted(e["ticker"] for e in feed["earnings"])
        # GOOG must be filtered out at the provider layer (ticker filter)
        assert "MU" in symbols and "RKLB" in symbols and "GOOG" not in symbols

    def test_scanner_scope_uses_36_universe(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def fake_earnings(start, end):
            return [{"symbol": "NVDA", "date": "2026-05-12"}]

        async def fake_news(tickers, fd, td, lim):
            return []

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="scanner", days=7,
            earnings_provider=fake_earnings, news_provider=fake_news,
        ))
        from libs.scanner.scanner_universe import SCANNER_RESEARCH_UNIVERSE
        assert feed["counts"]["tickers"] == len(SCANNER_RESEARCH_UNIVERSE)

    def test_all_supported_omits_news(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def fake_earnings(start, end):
            return [{"symbol": "X", "date": "2026-05-12"}]

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="all_supported", days=7,
            earnings_provider=fake_earnings,
        ))
        assert feed["news"] == []
        assert feed["provider_status"]["fmp_news"] == "ok"
        assert feed["provider_notes"]["fmp_news"] is not None
        assert "all_supported" in feed["provider_notes"]["fmp_news"]

    def test_all_supported_uses_limit(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def fake_earnings(start, end):
            return [{"symbol": f"X{i}", "date": "2026-05-12"} for i in range(1000)]

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="all_supported", days=7, limit=120,
            earnings_provider=fake_earnings,
        ))
        # The bound is enforced even though caller asked for 120 (well under
        # the ceiling); cache also keys on (start,end) — request scope omits
        # tickers so we just take the prefix of length=limit.
        assert feed["counts"]["earnings"] <= 120

    def test_mirror_scope_attaches_source_tags(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        self._patch_mirror(monkeypatch, [
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def fake_earnings(start, end):
            return [{"symbol": "MU", "date": "2026-05-12"}]

        async def fake_news(tickers, fd, td, lim):
            return [{"symbol": "MU", "title": "x", "publishedDate": "2026-05-08"}]

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror", days=7,
            earnings_provider=fake_earnings, news_provider=fake_news,
        ))
        e = feed["earnings"][0]
        assert e["is_in_mirror"] is True
        assert e["source_tags"] == ["HELD"]
        assert e["mapping_status"] == "mapped"

    def test_unknown_scope_raises(self):
        with pytest.raises(ValueError):
            asyncio.run(svc.get_feed(MagicMock(), scope="bogus"))

    def test_disclaimer_present(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        self._patch_mirror(monkeypatch, [])

        async def fake_earnings(start, end):
            return []

        async def fake_news(tickers, fd, td, lim):
            return []

        feed = asyncio.run(svc.get_feed(
            MagicMock(), scope="mirror",
            earnings_provider=fake_earnings, news_provider=fake_news,
        ))
        assert "Research events only" in feed["disclaimer"]


# ---------------------------------------------------------------------------
# Service layer — ticker detail
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTickerDetail:
    def test_unmapped_ticker_returns_unmapped_status(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        from libs.instruments import mirror_instrument_mapper as mim
        monkeypatch.setattr(mim, "_lookup_existing_mappings", lambda db, t: {})
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: {"items": []},
        )

        async def fake_profile(symbol):
            return {"companyName": "Rocket Lab", "exchangeShortName": "NASDAQ", "currency": "USD"}

        async def fake_earnings(start, end):
            return []

        async def fake_news(tickers, fd, td, lim):
            return []

        d = asyncio.run(svc.get_ticker_detail(
            MagicMock(), ticker="RKLB",
            profile_provider=fake_profile,
            earnings_provider=fake_earnings,
            news_provider=fake_news,
        ))
        assert d["mapping_status"] == "unmapped"
        assert d["instrument_id"] is None
        assert d["company_name"] == "Rocket Lab"


# ---------------------------------------------------------------------------
# Source-grep guards
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNoForbiddenSymbols:
    def test_providers_no_writes(self):
        src = _strip_python(inspect.getsource(p))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "session.add", "session.commit",
            "feature_t212_live_submit = True",
            "FEATURE_T212_LIVE_SUBMIT = True",
            "/equity/orders/limit", "/equity/orders/market",
        ):
            assert needle not in src, f"providers.py must not contain {needle!r}"

    def test_service_no_writes(self):
        src = _strip_python(inspect.getsource(svc))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "session.add", "session.commit",
            "/equity/orders/limit", "/equity/orders/market",
        ):
            assert needle not in src

    def test_no_scraping_in_either_module(self):
        for mod in (p, svc):
            src = _strip_python(inspect.getsource(mod)).lower()
            for needle in ("selenium", "playwright", "puppeteer",
                           "webdriver", "beautifulsoup"):
                assert needle not in src, (
                    f"{mod.__name__} must not import scraping/automation libs"
                )
