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


# ---------------------------------------------------------------------------
# P7 — Research priority factor explanations
# ---------------------------------------------------------------------------


class TestResearchPriorityFactors:
    """The to_dict() output now includes a structured
    ``research_priority_factors`` chip list and a ``why_it_matters``
    one-liner. Both are deterministic and strictly research-only."""

    def test_held_plus_news_plus_scanner_factor_set(self, monkeypatch):
        _patch_all_inputs(monkeypatch,
            scanner_items=[
                {"ticker": "NVDA", "instrument_id": "u",
                 "issuer_name": "NVIDIA",
                 "scan_types": ["strong_momentum"],
                 "signal_strength": "high", "change_1d_pct": 3.0,
                 "explanation": "X", "risk_flags": []},
            ],
            mirror_items=[
                {"display_ticker": "NVDA", "broker_ticker": "NVDA_US_EQ",
                 "company_name": "NVIDIA Corp", "instrument_id": "u",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        async def empty(tickers, fd, td, lim):
            return []

        async def polygon_news(tickers, fd, td, lim):
            return [{
                "id": "x", "title": "NVDA news",
                "article_url": "https://e/nvda",
                "publisher": {"name": "E"}, "tickers": ["NVDA"],
                "published_utc": "2026-05-09T12:00:00Z", "symbol": "NVDA",
            }] if "NVDA" in tickers else []

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty,
            polygon_news_fetcher=polygon_news,
            fmp_per_symbol_fetcher=empty_e,
        ))
        nvda = out["candidates"][0]
        ids = {f["id"] for f in nvda["research_priority_factors"]}
        assert "held" in ids
        assert "scanner" in ids
        assert "news" in ids
        # No banned trade/target/position language anywhere
        for f in nvda["research_priority_factors"]:
            for needle in ("buy", "sell", "target", "position",
                           "long", "short"):
                assert needle not in f["label"].lower()
        assert "Highest research priority" in nvda["why_it_matters"]
        assert "Independent validation required" in nvda["why_it_matters"]

    def test_watched_only_lowest_with_factor(self, monkeypatch):
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
        zzzz = out["candidates"][0]
        ids = {f["id"] for f in zzzz["research_priority_factors"]}
        assert "watched" in ids
        assert "unmapped" in ids
        assert zzzz["research_priority"] == obs.PRIORITY_LOWEST
        assert "Lowest" in zzzz["why_it_matters"]

    def test_factor_chips_strict_research_only(self, monkeypatch):
        """Sanity check: across 3 candidates spanning held / scanner /
        watched / unmapped / earnings the chip labels must never
        contain banned trading words."""
        _patch_all_inputs(monkeypatch,
            scanner_items=[
                {"ticker": "NVDA", "instrument_id": "u-nvda",
                 "issuer_name": "NVIDIA",
                 "scan_types": ["strong_momentum"],
                 "signal_strength": "high", "change_1d_pct": 3.0,
                 "explanation": "X", "risk_flags": ["high_vol"]},
            ],
            mirror_items=[
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
                 "company_name": "Micron", "instrument_id": "u-mu",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
                {"display_ticker": "AAOI", "broker_ticker": None,
                 "company_name": None, "instrument_id": None,
                 "source_tags": ["WATCHED"],
                 "mapping_status": "unmapped"},
            ],
            mapping_items=[("AAOI", "newly_resolvable")],
        )

        async def empty(tickers, fd, td, lim):
            return []

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty, polygon_news_fetcher=empty,
            fmp_per_symbol_fetcher=empty_e,
        ))
        banned = ("buy", "sell", "target", "position size",
                  "long ", "short ", "目标", "仓位", "建议")
        for cand in out["candidates"]:
            for f in cand["research_priority_factors"]:
                low = f["label"].lower()
                for needle in banned:
                    assert needle not in low, (
                        f"banned needle {needle!r} in factor "
                        f"{f['id']!r} for {cand['ticker']!r}"
                    )
            wm = cand["why_it_matters"].lower()
            for needle in banned:
                assert needle not in wm, (
                    f"banned needle {needle!r} in why_it_matters "
                    f"for {cand['ticker']!r}"
                )


# ---------------------------------------------------------------------------
# P2.1 — Rate-limit hardening + cache fallback diagnostics
# ---------------------------------------------------------------------------


class TestRateLimitHardening:
    """The brief must not collapse to an empty payload when one or both
    news providers return rate_limited. It must:

      * keep scanner / mirror / taxonomy / unmapped sections populated
      * surface a structured news_section_state ("rate_limited_cached"
        when a cache fallback is available, "rate_limited_no_cache"
        otherwise)
      * report effective_news_top_n + requested_news_top_n
      * report cached_news_age_seconds when cache fallback was used
      * report skipped_due_to_rate_limit when no cache available
      * never silently show pre_dedup=0 / deduped=0 with no context
    """

    def test_default_news_top_n_is_5(self):
        # Module-level default is the source of truth for the route.
        assert obs.DEFAULT_NEWS_TOP_N == 5

    def test_default_route_query_uses_5(self):
        from apps.api.routers import market_brief as route_mod
        # Inspect the FastAPI signature default for news_top_n
        sig = inspect.signature(route_mod.overnight_preview)
        param = sig.parameters["news_top_n"]
        # FastAPI Query() wraps the default — pull .default
        default_val = getattr(param.default, "default", param.default)
        assert default_val == 5

    def test_max_news_top_n_interactive_constant(self):
        assert obs.MAX_NEWS_TOP_N_INTERACTIVE == 25

    def test_effective_news_top_n_clamps_high_request(self, monkeypatch):
        scanner_items = [
            {"ticker": f"X{i}", "instrument_id": f"u{i}",
             "issuer_name": f"X{i} Inc",
             "scan_types": ["strong_momentum"], "signal_strength": "high",
             "change_1d_pct": 1.0, "explanation": "x", "risk_flags": []}
            for i in range(40)
        ]
        _patch_all_inputs(monkeypatch, scanner_items=scanner_items)

        async def empty(tickers, fd, td, lim):
            return []

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            news_top_n=999,  # over the cap
            fmp_news_fetcher=empty,
            polygon_news_fetcher=empty,
            fmp_per_symbol_fetcher=empty_e,
        ))
        eff = out["provider_diagnostics"]["news"]["effective_news_top_n"]
        req = out["provider_diagnostics"]["news"]["requested_news_top_n"]
        assert eff == obs.MAX_NEWS_TOP_N_INTERACTIVE
        assert req == 999
        # universe_scope mirrors it
        assert out["universe_scope"]["effective_news_top_n"] == eff
        assert out["universe_scope"]["requested_news_top_n"] == 999

    def test_provider_rate_limited_does_not_blank_brief(self, monkeypatch):
        _patch_all_inputs(monkeypatch,
            scanner_items=[
                {"ticker": "AAOI", "instrument_id": "u-aaoi",
                 "issuer_name": "AAOI", "scan_types": ["strong_momentum"],
                 "signal_strength": "high", "change_1d_pct": 3.5,
                 "explanation": "X", "risk_flags": []},
            ],
            mirror_items=[
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
                 "company_name": "Micron", "instrument_id": "u-mu",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        async def fmp_rl(tickers, fd, td, lim):
            raise p._ProviderRateLimited("HTTP 429: rate limit exceeded")

        async def polygon_rl(tickers, fd, td, lim):
            raise p._ProviderRateLimited("HTTP 429")

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=fmp_rl,
            polygon_news_fetcher=polygon_rl,
            fmp_per_symbol_fetcher=empty_e,
        ))
        # Brief is NOT blanked — scanner + mirror still present
        assert out["ticker_count"] == 2
        tickers = {c["ticker"] for c in out["candidates"]}
        assert "AAOI" in tickers
        assert "MU" in tickers
        # Categories summary still computed
        assert isinstance(out["categories_summary"], list)
        # News section state explicitly rate_limited_no_cache (no cache yet)
        nd = out["provider_diagnostics"]["news"]
        assert nd["section_state"] == "rate_limited_no_cache"
        # Requested tickers reported
        assert set(nd["requested_news_tickers"]).issubset({"AAOI", "MU"})
        assert len(nd["requested_news_tickers"]) >= 1
        # Skipped == requested when no cache
        assert (
            set(nd["skipped_due_to_rate_limit"])
            == set(nd["requested_news_tickers"])
        )
        # Provider statuses both rate_limited
        assert nd["fmp"]["status"] == "rate_limited"
        assert nd["polygon"]["status"] == "rate_limited"
        # Cache age None — no cache hit
        assert nd["cached_news_age_seconds"] is None
        # used_cached_news_count is zero
        assert nd["used_cached_news_count"] == 0

    def test_cached_news_fallback_used_when_provider_rate_limits(self, monkeypatch):
        """When provider was warm, then a subsequent rate-limit error
        should serve stale cache as status='cached'. The brief should
        report news_section_state='rate_limited_cached' with non-zero
        cached_news_age_seconds and non-zero used_cached_news_count."""
        _patch_all_inputs(monkeypatch,
            mirror_items=[
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
                 "company_name": "Micron", "instrument_id": "u-mu",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        # First request — Polygon returns 1 item (FMP empty).
        warm_call_count = {"n": 0}

        async def empty_fmp(tickers, fd, td, lim):
            return []

        async def warm_polygon(tickers, fd, td, lim):
            warm_call_count["n"] += 1
            return [{
                "id": "x", "title": "MU news cached",
                "article_url": "https://e/mu",
                "publisher": {"name": "E"},
                "tickers": ["MU"], "published_utc": "2026-05-08T12:00:00Z",
                "symbol": "MU",
            }]

        async def empty_e(symbol):
            return []

        out_warm = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_fmp,
            polygon_news_fetcher=warm_polygon,
            fmp_per_symbol_fetcher=empty_e,
        ))
        # Warm path has fresh ok status
        assert out_warm["provider_diagnostics"]["news"]["polygon"]["status"] in ("ok",)
        assert warm_call_count["n"] == 1

        # Force the polygon cache to expire so the next call invokes the
        # fetcher again — but the prior _CacheEntry is still kept in
        # ._entries for peek_entry() to surface as stale-on-refresh-fail.
        for entry in p._polygon_news_cache._entries.values():
            # Backdate fetched_at well past the TTL so peek() returns
            # None and a refresh is attempted on the next call.
            entry.fetched_at = entry.fetched_at - 10000.0

        # Second request — Polygon now raises rate-limit.
        async def rl_polygon(tickers, fd, td, lim):
            raise p._ProviderRateLimited("HTTP 429")

        out_rl = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_fmp,
            polygon_news_fetcher=rl_polygon,
            fmp_per_symbol_fetcher=empty_e,
        ))
        nd = out_rl["provider_diagnostics"]["news"]
        # Cache fallback served the prior payload as status=cached
        assert nd["polygon"]["status"] == "cached"
        # Section state reports rate_limited_cached
        assert nd["section_state"] == "rate_limited_cached"
        # cached_news_age_seconds reports a positive number (or 0+)
        assert nd["cached_news_age_seconds"] is not None
        assert nd["cached_news_age_seconds"] >= 0
        # used_cached_news_count > 0 (the warm payload)
        assert nd["used_cached_news_count"] >= 1
        # Brief still has populated sections — not blanked
        assert out_rl["ticker_count"] == 1
        # MU has its news attached from cache
        mu = next(c for c in out_rl["candidates"] if c["ticker"] == "MU")
        assert mu["recent_news"] and len(mu["recent_news"]) >= 1

    def test_partial_rate_limit_keeps_other_provider_data(self, monkeypatch):
        """Only one provider rate-limited, the other returns data.
        The brief should reflect partial / ok with skipped tickers
        empty (we got data from the alive provider)."""
        _patch_all_inputs(monkeypatch,
            mirror_items=[
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
                 "company_name": "Micron", "instrument_id": "u-mu",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        async def fmp_rl(tickers, fd, td, lim):
            raise p._ProviderRateLimited("HTTP 429")

        async def polygon_ok(tickers, fd, td, lim):
            return [{
                "id": "x", "title": "MU news live",
                "article_url": "https://e/mu", "publisher": {"name": "E"},
                "tickers": ["MU"], "published_utc": "2026-05-08T12:00:00Z",
                "symbol": "MU",
            }]

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=fmp_rl,
            polygon_news_fetcher=polygon_ok,
            fmp_per_symbol_fetcher=empty_e,
        ))
        nd = out["provider_diagnostics"]["news"]
        # FMP rate_limited, Polygon ok — section state should NOT be
        # rate_limited_no_cache because data is present.
        assert nd["fmp"]["status"] == "rate_limited"
        assert nd["polygon"]["status"] == "ok"
        # We got data → state is rate_limited_cached when one is RL +
        # we have data, OR mirrors merged_status otherwise.
        assert nd["section_state"] in ("rate_limited_cached", "ok", "partial")
        # MU got news
        mu = next(c for c in out["candidates"] if c["ticker"] == "MU")
        assert mu["recent_news"]

    def test_diagnostics_math_remains_consistent(self, monkeypatch):
        """When data flows through, raw / parsed / deduped / dropped
        must be self-consistent: parsed = raw - skipped, and merged
        deduped + dropped = pre_dedup (sum of provider parsed counts)."""
        _patch_all_inputs(monkeypatch,
            mirror_items=[
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
                 "company_name": "Micron", "instrument_id": "u-mu",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        async def fmp_two(tickers, fd, td, lim):
            return [{
                "title": "MU FMP a", "publishedDate": "2026-05-08T11:00:00Z",
                "url": "https://e/mu-a", "site": "E",
                "symbol": "MU", "id": "mu_a",
            }, {
                "title": "MU FMP b", "publishedDate": "2026-05-08T12:00:00Z",
                "url": "https://e/mu-b", "site": "E",
                "symbol": "MU", "id": "mu_b",
            }]

        async def polygon_dup(tickers, fd, td, lim):
            return [{
                "id": "p_a", "title": "MU FMP a",  # same title as fmp_a → dedup
                "article_url": "https://e/mu-a", "publisher": {"name": "E"},
                "tickers": ["MU"], "published_utc": "2026-05-08T11:00:00Z",
                "symbol": "MU",
            }]

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=fmp_two,
            polygon_news_fetcher=polygon_dup,
            fmp_per_symbol_fetcher=empty_e,
        ))
        nd = out["provider_diagnostics"]["news"]
        fmp_d = nd["fmp"]
        poly_d = nd["polygon"]
        merged = nd["merged"]
        # parsed = raw - skipped (per provider)
        assert fmp_d["parsed_count"] == fmp_d["raw_count"] - fmp_d["skipped_count"]
        assert poly_d["parsed_count"] == poly_d["raw_count"] - poly_d["skipped_count"]
        # pre_dedup is sum of parsed per provider
        assert merged["pre_dedup_count"] == (
            fmp_d["parsed_count"] + poly_d["parsed_count"]
        )
        # deduped + dropped = pre_dedup
        assert (merged["deduped_count"] + merged["dropped_duplicates"]
                == merged["pre_dedup_count"])
        # Section state reflects ok (no rate-limit)
        assert nd["section_state"] in ("ok", "cached")

    def test_no_news_tickers_yields_empty_state(self, monkeypatch):
        """If the universe is empty (no scanner, no mirror), news
        section state should be 'empty' and skipped_due_to_rate_limit
        should be empty (nothing was requested)."""
        _patch_all_inputs(monkeypatch)  # no scanner, no mirror

        async def empty(tickers, fd, td, lim):
            return []

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty, polygon_news_fetcher=empty,
            fmp_per_symbol_fetcher=empty_e,
        ))
        nd = out["provider_diagnostics"]["news"]
        assert nd["section_state"] == "empty"
        assert nd["requested_news_tickers"] == []
        assert nd["skipped_due_to_rate_limit"] == []
        assert nd["used_cached_news_count"] == 0
        assert nd["cached_news_age_seconds"] is None

    def test_rate_limited_note_in_per_provider_diag_when_no_cache(
        self, monkeypatch
    ):
        """When the only source returns rate_limited and nothing was
        cached, the per-provider FMP/Polygon status carries
        'rate_limited' (not 'cached')."""
        _patch_all_inputs(monkeypatch,
            mirror_items=[
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
                 "company_name": "Micron", "instrument_id": "u-mu",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        async def rl(tickers, fd, td, lim):
            raise p._ProviderRateLimited("HTTP 429")

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=rl, polygon_news_fetcher=rl,
            fmp_per_symbol_fetcher=empty_e,
        ))
        nd = out["provider_diagnostics"]["news"]
        assert nd["fmp"]["status"] == "rate_limited"
        assert nd["polygon"]["status"] == "rate_limited"
        # merged status mirrors rate_limited
        assert nd["merged"]["status"] == "rate_limited"
        # Brief-level state surfaces the no_cache variant
        assert nd["section_state"] == "rate_limited_no_cache"
