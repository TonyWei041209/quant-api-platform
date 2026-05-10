"""P4 diagnostics polish — rate_limited + empty status classification.

The user's observed bug:
  * FMP returns 429 "Rate limit exceeded" (not 402), which the prior
    handler swallowed as a generic per-ticker error → wrapper reported
    fmp_news=ok with empty data. Confusing UX.
  * "ok with raw=0" should be "empty" so users know the provider
    succeeded but returned nothing.

This module pins:
  * RateLimitExceeded exception → status="rate_limited"
  * "429" / "rate limit" text in error → status="rate_limited"
  * Empty list with no error → status="empty"
  * Merged status logic treats unavailable / rate_limited / empty as
    expected absences (not failures); pairs with ok-data give "ok".
  * Dedup counters are math-consistent (raw, parsed, deduped, dropped).
"""
from __future__ import annotations

import asyncio

import pytest

from libs.core.exceptions import RateLimitExceeded
from libs.market_events import providers as p


@pytest.fixture(autouse=True)
def _reset():
    p.reset_caches_for_tests()
    yield
    p.reset_caches_for_tests()


# ---------------------------------------------------------------------------
# rate_limited classification
# ---------------------------------------------------------------------------


class TestRateLimitedClassification:
    def test_fmp_rate_limited_exception_flips_status(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def boom(tickers, fd, td, lim):
            raise p._ProviderRateLimited("FMP 429 rate-limited")

        result = asyncio.run(p.get_stock_news(
            ["AAOI"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=boom,
        ))
        assert result.status == "rate_limited"
        assert result.data == []

    def test_polygon_rate_limited_exception_flips_status(self, monkeypatch):
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def boom(tickers, fd, td, lim):
            raise p._ProviderRateLimited("Polygon 429")

        result = asyncio.run(p.get_polygon_news(
            ["AAOI"], "2026-05-02", "2026-05-09",
            polygon_news_fetcher=boom,
        ))
        assert result.status == "rate_limited"

    def test_default_fmp_news_429_text_in_generic_exception(self):
        """When the per-ticker call raises a generic exception whose
        string contains '429' or 'rate limit', the fallback regex MUST
        flip to rate_limited (defense-in-depth alongside the typed
        RateLimitExceeded catch)."""
        # Patch FMPAdapter.fetch_json to raise a plain RuntimeError with
        # the rate-limit substring (mimicking a wrapper that lost the
        # typed RateLimitExceeded class).
        from libs.adapters import fmp_adapter as fmp_mod
        orig = fmp_mod.FMPAdapter.fetch_json

        async def boom(self, *a, **k):
            raise RuntimeError("upstream 429 Too Many Requests")

        fmp_mod.FMPAdapter.fetch_json = boom
        try:
            with pytest.raises(p._ProviderRateLimited):
                asyncio.run(p._default_fmp_news(
                    ["AAOI"], "2026-05-02", "2026-05-09", 5,
                ))
        finally:
            fmp_mod.FMPAdapter.fetch_json = orig

    def test_default_fmp_news_typed_RateLimitExceeded_caught(self):
        """The typed RateLimitExceeded raised by BaseAdapter.fetch must
        be caught and converted to _ProviderRateLimited."""
        from libs.adapters import fmp_adapter as fmp_mod
        orig = fmp_mod.FMPAdapter.fetch_json

        async def boom(self, *a, **k):
            raise RateLimitExceeded("fmp", "Rate limit exceeded", {"status": 429})

        fmp_mod.FMPAdapter.fetch_json = boom
        try:
            with pytest.raises(p._ProviderRateLimited):
                asyncio.run(p._default_fmp_news(
                    ["AAOI"], "2026-05-02", "2026-05-09", 5,
                ))
        finally:
            fmp_mod.FMPAdapter.fetch_json = orig


# ---------------------------------------------------------------------------
# empty classification
# ---------------------------------------------------------------------------


class TestEmptyClassification:
    def test_fmp_ok_empty_returns_status_empty(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def returns_empty(tickers, fd, td, lim):
            return []

        result = asyncio.run(p.get_stock_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=returns_empty,
        ))
        assert result.status == "empty", "ok+empty must be reclassified as 'empty'"
        assert result.data == []
        assert "0 items" in (result.note or "")

    def test_polygon_ok_empty_returns_status_empty(self, monkeypatch):
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def returns_empty(tickers, fd, td, lim):
            return []

        result = asyncio.run(p.get_polygon_news(
            ["MU"], "2026-05-02", "2026-05-09",
            polygon_news_fetcher=returns_empty,
        ))
        assert result.status == "empty"

    def test_fmp_with_data_still_ok(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)

        async def fetcher(tickers, fd, td, lim):
            return [{
                "title": "x", "url": "https://e/x", "site": "E",
                "symbol": "MU", "publishedDate": "2026-05-08",
            }]

        result = asyncio.run(p.get_stock_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=fetcher,
        ))
        assert result.status == "ok"


# ---------------------------------------------------------------------------
# Merged status with new vocabulary
# ---------------------------------------------------------------------------


class TestMergedStatusNewVocab:
    def test_fmp_rate_limited_polygon_ok_merged_ok(self, monkeypatch):
        """Rate-limited is an EXPECTED absence not a failure. If Polygon
        returned data, merged_status should be ok (the user got data)."""
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def fmp_429(tickers, fd, td, lim):
            raise p._ProviderRateLimited("FMP 429")

        async def polygon_ok(tickers, fd, td, lim):
            return [{
                "id": "x", "title": "MU news",
                "article_url": "https://e/p", "publisher": {"name": "E"},
                "tickers": ["MU"], "published_utc": "2026-05-08T12:00:00Z",
                "symbol": "MU",
            }]

        merged = asyncio.run(p.get_merged_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=fmp_429,
            polygon_news_fetcher=polygon_ok,
        ))
        assert merged.fmp.status == "rate_limited"
        assert merged.polygon.status == "ok"
        assert merged.merged_status == "ok"
        assert len(merged.merged_items) == 1

    def test_both_rate_limited_merged_rate_limited(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def fmp_429(tickers, fd, td, lim):
            raise p._ProviderRateLimited("FMP 429")

        async def polygon_429(tickers, fd, td, lim):
            raise p._ProviderRateLimited("Polygon 429")

        merged = asyncio.run(p.get_merged_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=fmp_429,
            polygon_news_fetcher=polygon_429,
        ))
        assert merged.merged_status == "rate_limited"

    def test_both_empty_merged_empty(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def empty(tickers, fd, td, lim):
            return []

        merged = asyncio.run(p.get_merged_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=empty,
            polygon_news_fetcher=empty,
        ))
        assert merged.fmp.status == "empty"
        assert merged.polygon.status == "empty"
        assert merged.merged_status == "empty"

    def test_mixed_unavailable_and_rate_limited_no_failure_merged_empty(self, monkeypatch):
        """Mix of expected absences (unavailable + rate_limited) with no
        actual failures and no data → merged_status='empty'."""
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def fmp_unavailable(tickers, fd, td, lim):
            raise p._ProviderUnavailable("FMP plan-blocked")

        async def polygon_429(tickers, fd, td, lim):
            raise p._ProviderRateLimited("Polygon 429")

        merged = asyncio.run(p.get_merged_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=fmp_unavailable,
            polygon_news_fetcher=polygon_429,
        ))
        assert merged.merged_status == "empty"

    def test_one_ok_one_failure_merged_partial(self, monkeypatch):
        """When at least one provider DATA + at least one actual failure
        (timeout/error), merged_status='partial'."""
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def fmp_ok(tickers, fd, td, lim):
            return [{
                "title": "x", "url": "https://e/x", "site": "E",
                "symbol": "MU", "publishedDate": "2026-05-08",
            }]

        async def polygon_err(tickers, fd, td, lim):
            raise RuntimeError("upstream 503 Service Unavailable")

        merged = asyncio.run(p.get_merged_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=fmp_ok,
            polygon_news_fetcher=polygon_err,
        ))
        assert merged.fmp.status == "ok"
        assert merged.polygon.status == "error"
        assert merged.merged_status == "partial"


# ---------------------------------------------------------------------------
# Math consistency of dedup counters
# ---------------------------------------------------------------------------


class TestDedupMathConsistency:
    def test_pre_dedup_minus_dropped_equals_deduped(self, monkeypatch):
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        # 3 from FMP, 3 from Polygon, 2 are cross-provider duplicates
        async def fmp_news(tickers, fd, td, lim):
            return [
                {"title": "Article A", "url": "https://a.com/1",
                 "site": "A", "symbol": "MU", "publishedDate": "2026-05-08T12:00:00Z"},
                {"title": "Article B", "url": "https://b.com/1",
                 "site": "B", "symbol": "MU", "publishedDate": "2026-05-07T12:00:00Z"},
                {"title": "Article C only on FMP", "url": "https://c.com/1",
                 "site": "C", "symbol": "MU", "publishedDate": "2026-05-06T12:00:00Z"},
            ]

        async def polygon_news(tickers, fd, td, lim):
            return [
                # Same as Article A (URL match)
                {"id": "p1", "title": "Article A",
                 "article_url": "https://a.com/1",
                 "publisher": {"name": "A"}, "tickers": ["MU"],
                 "published_utc": "2026-05-08T12:00:00Z", "symbol": "MU"},
                # Same as Article B but different URL (title match)
                {"id": "p2", "title": "Article B",
                 "article_url": "https://different.com/path",
                 "publisher": {"name": "Diff"}, "tickers": ["MU"],
                 "published_utc": "2026-05-07T12:00:00Z", "symbol": "MU"},
                # Brand new
                {"id": "p3", "title": "Article D only on Polygon",
                 "article_url": "https://d.com/1",
                 "publisher": {"name": "D"}, "tickers": ["MU"],
                 "published_utc": "2026-05-05T12:00:00Z", "symbol": "MU"},
            ]

        merged = asyncio.run(p.get_merged_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=fmp_news,
            polygon_news_fetcher=polygon_news,
        ))
        d = merged.diagnostics
        raw_total = d["fmp"]["raw_count"] + d["polygon"]["raw_count"]
        parsed_total = d["fmp"]["parsed_count"] + d["polygon"]["parsed_count"]
        pre_dedup = d["merged"]["pre_dedup_count"]
        deduped = d["merged"]["deduped_count"]
        dropped = d["merged"]["dropped_duplicates"]

        # Hard math invariants:
        assert raw_total == 6
        assert parsed_total == pre_dedup, "parsed_total must equal pre_dedup_count"
        assert pre_dedup == 6
        assert pre_dedup - dropped == deduped, "pre_dedup - dropped must equal deduped"
        assert deduped == 4  # A, B, C, D after dropping the 2 dupes
        assert dropped == 2

    def test_dropped_never_exceeds_pre_dedup(self, monkeypatch):
        """Property: dropped <= pre_dedup must always hold."""
        monkeypatch.setattr(p, "_fmp_configured", lambda: True)
        monkeypatch.setattr(p, "_polygon_configured", lambda: True)

        async def fmp_news(tickers, fd, td, lim):
            return [{"title": "x", "url": "https://e/1", "site": "E",
                     "symbol": "MU", "publishedDate": "2026-05-08T12:00:00Z"}]

        async def polygon_news(tickers, fd, td, lim):
            return [{
                "id": "p", "title": "x", "article_url": "https://e/1",
                "publisher": {"name": "E"}, "tickers": ["MU"],
                "published_utc": "2026-05-08T12:00:00Z", "symbol": "MU",
            }]

        merged = asyncio.run(p.get_merged_news(
            ["MU"], "2026-05-02", "2026-05-09",
            fmp_news_fetcher=fmp_news,
            polygon_news_fetcher=polygon_news,
        ))
        d = merged.diagnostics
        assert d["merged"]["dropped_duplicates"] <= d["merged"]["pre_dedup_count"]
        assert d["merged"]["deduped_count"] <= d["merged"]["pre_dedup_count"]


# ---------------------------------------------------------------------------
# Source-grep guard for changed file
# ---------------------------------------------------------------------------


class TestNoForbiddenSymbolsP4Polish:
    def test_providers_no_forbidden(self):
        import inspect
        import io
        import tokenize
        src = inspect.getsource(p)
        out = []
        try:
            for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
                if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                    continue
                out.append(tok.string)
                out.append(" ")
        except tokenize.TokenizeError:
            out = [src]
        stripped = "".join(out)
        for needle in ("submit_limit_order", "submit_market_order",
                       "OrderIntent", "OrderDraft", "order_intent", "order_draft",
                       "/equity/orders/limit", "/equity/orders/market",
                       "selenium", "playwright", "puppeteer", "webdriver"):
            assert needle.lower() not in stripped.lower()
