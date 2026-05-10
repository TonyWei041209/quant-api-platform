"""Overnight Market Brief — service tests.

Hermetic. Stubs out scanner, mirror, mapping plan, news, and earnings
so the brief composition logic is exercised against deterministic
inputs. No real HTTP, no DB writes, no T212.
"""
from __future__ import annotations

import asyncio
import inspect
import io
import tokenize
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest

from libs.market_brief import overnight_brief_service as obs
from libs.market_events import providers as p


@pytest.fixture(autouse=True)
def _reset_caches():
    p.reset_caches_for_tests()
    yield
    p.reset_caches_for_tests()


def _strip(src: str) -> str:
    out = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    return "".join(out)


def _patch_all_inputs(monkeypatch, *, scanner_items=None, mirror_items=None,
                     mapping_items=None):
    """Patch the four read-only data sources the brief composes."""
    from libs.scanner import stock_scanner_service as scanner_mod
    from libs.portfolio import mirror_watchlist_service as mws
    from libs.instruments import mirror_instrument_mapper as mim

    monkeypatch.setattr(p, "_fmp_configured", lambda: True)
    monkeypatch.setattr(p, "_polygon_configured", lambda: True)

    scanner_items = scanner_items or []
    monkeypatch.setattr(
        scanner_mod, "scan_stocks",
        lambda db, **kw: {
            "items": scanner_items,
            "scanned": len(scanner_items),
            "matched": len(scanner_items),
            "as_of": "2026-05-09",
        }
    )

    mirror_items = mirror_items or []
    monkeypatch.setattr(
        mws, "build_mirror_watchlist",
        lambda db, **kwargs: {"items": mirror_items},
    )

    # Mapping plan — return a minimal dataclass-like object
    class _FakePlanItem:
        def __init__(self, ticker, status):
            self.display_ticker = ticker
            self.mapping_status = status

    class _FakePlan:
        def __init__(self, items):
            self.items = items

    async def _fake_plan(db, **kw):
        items = mapping_items or []
        return _FakePlan([_FakePlanItem(t, s) for t, s in items])

    monkeypatch.setattr(mim, "build_mirror_mapping_plan", _fake_plan)


# ---------------------------------------------------------------------------
# Universe composition
# ---------------------------------------------------------------------------


class TestUniverseComposition:
    def test_scanner_only_when_no_mirror(self, monkeypatch):
        _patch_all_inputs(monkeypatch, scanner_items=[
            {"ticker": "NVDA", "instrument_id": "u1",
             "issuer_name": "NVIDIA", "scan_types": ["strong_momentum"],
             "signal_strength": "high", "change_1d_pct": 2.1,
             "explanation": "X", "risk_flags": []},
        ])

        async def empty_news(tickers, fd, td, lim):
            return []

        async def empty_earnings(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_news,
            polygon_news_fetcher=empty_news,
            fmp_per_symbol_fetcher=empty_earnings,
        ))
        assert out["ticker_count"] == 1
        assert out["candidates"][0]["ticker"] == "NVDA"
        assert "SCANNER" in out["candidates"][0]["source_tags"]

    def test_mirror_only_when_no_scanner(self, monkeypatch):
        _patch_all_inputs(monkeypatch, mirror_items=[
            {"display_ticker": "AAOI", "broker_ticker": "AAOI_US_EQ",
             "company_name": None, "instrument_id": None,
             "source_tags": ["WATCHED"], "mapping_status": "unmapped"},
        ])

        async def empty_news(tickers, fd, td, lim):
            return []

        async def empty_earnings(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_news,
            polygon_news_fetcher=empty_news,
            fmp_per_symbol_fetcher=empty_earnings,
        ))
        assert out["ticker_count"] == 1
        cand = out["candidates"][0]
        assert cand["ticker"] == "AAOI"
        assert "WATCHED" in cand["source_tags"]
        assert "UNMAPPED" in cand["source_tags"]

    def test_scanner_and_mirror_merged_with_combined_tags(self, monkeypatch):
        # NVDA appears in BOTH scanner and mirror (held)
        _patch_all_inputs(monkeypatch,
            scanner_items=[
                {"ticker": "NVDA", "instrument_id": "u-nvda",
                 "issuer_name": "NVIDIA", "scan_types": ["strong_momentum"],
                 "signal_strength": "high", "change_1d_pct": 2.1,
                 "explanation": "X", "risk_flags": []},
            ],
            mirror_items=[
                {"display_ticker": "NVDA", "broker_ticker": "NVDA_US_EQ",
                 "company_name": "NVIDIA Corp", "instrument_id": "u-nvda",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
                {"display_ticker": "AAOI", "broker_ticker": None,
                 "company_name": None, "instrument_id": None,
                 "source_tags": ["WATCHED"], "mapping_status": "unmapped"},
            ],
        )

        async def empty_news(tickers, fd, td, lim):
            return []

        async def empty_earnings(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_news,
            polygon_news_fetcher=empty_news,
            fmp_per_symbol_fetcher=empty_earnings,
        ))
        assert out["ticker_count"] == 2
        nvda = next(c for c in out["candidates"] if c["ticker"] == "NVDA")
        # NVDA must have BOTH tags merged
        assert "HELD" in nvda["source_tags"]
        assert "SCANNER" in nvda["source_tags"]
        # No UNMAPPED for mapped NVDA
        assert "UNMAPPED" not in nvda["source_tags"]


# ---------------------------------------------------------------------------
# Taxonomy + mapping enrichment
# ---------------------------------------------------------------------------


class TestEnrichment:
    def test_taxonomy_attached_for_known_ticker(self, monkeypatch):
        _patch_all_inputs(monkeypatch, mirror_items=[
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "company_name": "Micron", "instrument_id": "u-mu",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def empty_news(tickers, fd, td, lim):
            return []

        async def empty_earnings(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_news,
            polygon_news_fetcher=empty_news,
            fmp_per_symbol_fetcher=empty_earnings,
        ))
        cand = out["candidates"][0]
        # MU is in the static taxonomy map → should have broad + subs
        assert cand["taxonomy"]["broad"] == "Technology"
        assert "Memory Chips" in cand["taxonomy"]["subs"]

    def test_newly_resolvable_status_flows_through(self, monkeypatch):
        _patch_all_inputs(monkeypatch,
            mirror_items=[
                {"display_ticker": "RKLB", "broker_ticker": None,
                 "company_name": None, "instrument_id": None,
                 "source_tags": ["WATCHED"], "mapping_status": "unmapped"},
            ],
            mapping_items=[("RKLB", "newly_resolvable")],
        )

        async def empty_news(tickers, fd, td, lim):
            return []

        async def empty_earnings(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_news,
            polygon_news_fetcher=empty_news,
            fmp_per_symbol_fetcher=empty_earnings,
        ))
        rklb = out["candidates"][0]
        assert rklb["mapping_status"] == "newly_resolvable"
        assert "UNMAPPED" in rklb["source_tags"]
        # Unmapped section should include RKLB at the top (newly_resolvable
        # first per the sort order in the service)
        unmapped_first = out["unmapped_candidates"][0]
        assert unmapped_first["ticker"] == "RKLB"


# ---------------------------------------------------------------------------
# News + earnings fan-out
# ---------------------------------------------------------------------------


class TestFanOut:
    def test_news_attached_to_top_n_only(self, monkeypatch):
        # 8 mirror tickers; news_top_n=3 → only top 3 should get news
        scanner_items = [
            {"ticker": f"X{i}", "instrument_id": f"u{i}", "issuer_name": f"X{i} Inc",
             "scan_types": ["strong_momentum"], "signal_strength": "high",
             "change_1d_pct": float(i), "explanation": "X", "risk_flags": []}
            for i in range(8)
        ]
        _patch_all_inputs(monkeypatch, scanner_items=scanner_items)

        called_tickers = []

        async def fmp_news(tickers, fd, td, lim):
            called_tickers.extend(tickers)
            return []

        async def polygon_news(tickers, fd, td, lim):
            return [{
                "id": f"id_{tickers[0]}", "title": f"{tickers[0]} news",
                "article_url": f"https://e/{tickers[0]}",
                "publisher": {"name": "E"}, "tickers": [tickers[0]],
                "published_utc": "2026-05-08T12:00:00Z", "symbol": tickers[0],
            }] if tickers else []

        async def empty_earnings(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            news_top_n=3,
            fmp_news_fetcher=fmp_news,
            polygon_news_fetcher=polygon_news,
            fmp_per_symbol_fetcher=empty_earnings,
        ))
        # Exactly 3 tickers fanned out for news
        assert len(set(called_tickers)) == 3
        assert out["universe_scope"]["news_fanout_top_n"] == 3

    def test_earnings_attached_when_present(self, monkeypatch):
        _patch_all_inputs(monkeypatch, mirror_items=[
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "company_name": "Micron", "instrument_id": "u",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def empty_news(tickers, fd, td, lim):
            return []

        async def per_sym(symbol):
            today = date.today()
            return [{
                "date": (today + timedelta(days=3)).isoformat(),
                "symbol": symbol, "epsEstimated": 1.5,
            }]

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_news,
            polygon_news_fetcher=empty_news,
            fmp_per_symbol_fetcher=per_sym,
        ))
        mu = out["candidates"][0]
        assert len(mu["upcoming_earnings"]) == 1
        # earnings_nearby_candidates section populated
        assert any(c["ticker"] == "MU" for c in out["earnings_nearby_candidates"])


# ---------------------------------------------------------------------------
# Research priority bucket
# ---------------------------------------------------------------------------


class TestResearchPriority:
    def test_held_plus_news_plus_scanner_is_highest(self, monkeypatch):
        _patch_all_inputs(monkeypatch,
            scanner_items=[
                {"ticker": "NVDA", "instrument_id": "u-nvda",
                 "issuer_name": "NVIDIA", "scan_types": ["strong_momentum"],
                 "signal_strength": "high", "change_1d_pct": 5.0,
                 "explanation": "X", "risk_flags": []},
            ],
            mirror_items=[
                {"display_ticker": "NVDA", "broker_ticker": "NVDA_US_EQ",
                 "company_name": "NVIDIA Corp", "instrument_id": "u-nvda",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        async def empty_news(tickers, fd, td, lim):
            return []

        async def polygon_news(tickers, fd, td, lim):
            return [{
                "id": "x", "title": "NVDA news",
                "article_url": "https://e/nvda",
                "publisher": {"name": "E"}, "tickers": ["NVDA"],
                "published_utc": "2026-05-08T12:00:00Z", "symbol": "NVDA",
            }] if "NVDA" in tickers else []

        async def empty_earnings(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_news,
            polygon_news_fetcher=polygon_news,
            fmp_per_symbol_fetcher=empty_earnings,
        ))
        nvda = out["candidates"][0]
        assert nvda["research_priority"] == obs.PRIORITY_HIGHEST

    def test_unmapped_only_is_lowest(self, monkeypatch):
        _patch_all_inputs(monkeypatch, mirror_items=[
            {"display_ticker": "ZZZZ", "broker_ticker": None,
             "company_name": None, "instrument_id": None,
             "source_tags": ["WATCHED"], "mapping_status": "unmapped"},
        ])

        async def empty(tickers, fd, td, lim):
            return []

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty, polygon_news_fetcher=empty,
            fmp_per_symbol_fetcher=empty_e,
        ))
        # Watched-only (no scanner, no news, no earnings) → lowest
        assert out["candidates"][0]["research_priority"] == obs.PRIORITY_LOWEST


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_required_top_level_keys(self, monkeypatch):
        _patch_all_inputs(monkeypatch)

        async def empty(tickers, fd, td, lim):
            return []

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty, polygon_news_fetcher=empty,
            fmp_per_symbol_fetcher=empty_e,
        ))
        for k in ("generated_at", "universe_scope", "ticker_count",
                  "candidates", "top_price_anomaly_candidates",
                  "top_news_linked_candidates", "earnings_nearby_candidates",
                  "unmapped_candidates", "categories_summary",
                  "provider_diagnostics", "side_effects", "disclaimer"):
            assert k in out, f"missing key {k!r}"
        # side_effects attestations
        se = out["side_effects"]
        assert se["db_writes"] == "NONE"
        assert se["broker_writes"] == "NONE"
        assert se["execution_objects"] == "NONE"
        assert "FEATURE_T212_LIVE_SUBMIT=false" in se["live_submit"]
        assert se["scheduler_changes"] == "NONE"


# ---------------------------------------------------------------------------
# Source-grep guards
# ---------------------------------------------------------------------------


class TestNoForbiddenSymbols:
    def test_service_no_forbidden(self):
        src = _strip(inspect.getsource(obs))
        for needle in ("submit_limit_order", "submit_market_order", "submit_order",
                       "OrderIntent", "OrderDraft", "order_intent", "order_draft",
                       "/equity/orders/limit", "/equity/orders/market",
                       "session.add", "session.commit",
                       "selenium", "playwright", "puppeteer", "webdriver",
                       "BeautifulSoup", "bs4"):
            assert needle.lower() not in src.lower(), (
                f"overnight_brief_service must not contain {needle!r}"
            )

    def test_router_no_forbidden(self):
        from apps.api.routers import market_brief as router_mod
        src = _strip(inspect.getsource(router_mod))
        for needle in ("submit_limit_order", "submit_market_order", "submit_order",
                       "OrderIntent", "OrderDraft", "order_intent", "order_draft",
                       "session.add", "session.commit",
                       "selenium", "playwright", "puppeteer"):
            assert needle.lower() not in src.lower()

    def test_no_banned_trading_phrases(self):
        src = _strip(inspect.getsource(obs))
        for phrase in ("buy now", "sell now", "enter long", "enter short",
                       "target price", "position siz", "guaranteed",
                       "必涨", "必跌", "买入建议", "卖出建议", "目标价",
                       "仓位建议", "建仓"):
            assert phrase.lower() not in src.lower(), (
                f"overnight_brief_service must not contain banned phrase {phrase!r}"
            )
