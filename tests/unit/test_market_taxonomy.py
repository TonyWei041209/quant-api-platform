"""P1 — Market taxonomy unit tests.

Hermetic. No DB, no network. Verifies static classification, provider
heuristics, merge semantics, and filter behavior.
"""
from __future__ import annotations

import inspect
import io
import tokenize

import pytest

from libs.scanner import market_taxonomy as tax


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


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_broad_categories_unique(self):
        assert len(set(tax.BROAD_CATEGORIES)) == len(tax.BROAD_CATEGORIES)

    def test_subcategories_unique(self):
        assert len(set(tax.SUBCATEGORIES)) == len(tax.SUBCATEGORIES)

    def test_required_broad_categories_present(self):
        required = {
            "Technology", "Healthcare", "Financials", "Energy", "ETFs",
            "ADRs", "Small Caps", "High Volatility", "Crypto-related",
            "China ADR", "User Custom",
        }
        assert required.issubset(set(tax.BROAD_CATEGORIES))

    def test_required_subcategories_present(self):
        required = {
            "AI Infrastructure", "Semiconductors", "Memory Chips",
            "Data Centers", "Cloud Software", "Space-Rocket",
            "Crypto Miners", "EV", "Biotech", "Fintech",
        }
        assert required.issubset(set(tax.SUBCATEGORIES))


# ---------------------------------------------------------------------------
# Symbol normalization
# ---------------------------------------------------------------------------


class TestNormalizeSymbol:
    @pytest.mark.parametrize("inp,expected", [
        ("MU", "MU"),
        ("MU_US_EQ", "MU"),
        ("NVDA_US_EQ", "NVDA"),
        ("smsn.il", "SMSN.IL"),
        (None, None),
        ("", None),
        ("  rklb  ", "RKLB"),
    ])
    def test_normalize(self, inp, expected):
        assert tax.normalize_symbol(inp) == expected


# ---------------------------------------------------------------------------
# Static classification — required matches
# ---------------------------------------------------------------------------


class TestStaticClassification:
    @pytest.mark.parametrize("ticker,broad,must_have_subs", [
        ("NVDA", "Technology", {"Semiconductors", "AI Infrastructure"}),
        ("AMD",  "Technology", {"Semiconductors", "AI Infrastructure"}),
        ("MU",   "Technology", {"Semiconductors", "Memory Chips"}),
        ("RKLB", "Industrials", {"Space-Rocket"}),
        ("HIMS", "Healthcare", {"Digital Health"}),
        ("IREN", "Industrials", {"Crypto Miners", "Data Centers"}),
        ("SOFI", "Financials", {"Fintech"}),
        ("NOK",  "Communication Services", {"ADRs"}),
        ("SPY",  "ETFs", set()),
        ("IWM",  "ETFs", {"Small Caps"}),
    ])
    def test_known_ticker_classification(self, ticker, broad, must_have_subs):
        entry = tax.classify_by_static_theme(ticker)
        assert entry is not None
        assert entry["broad"] == broad
        if must_have_subs:
            assert must_have_subs.issubset(set(entry["subs"]))

    def test_unknown_ticker_returns_none(self):
        assert tax.classify_by_static_theme("ZZZZ") is None
        assert tax.classify_by_static_theme(None) is None
        assert tax.classify_by_static_theme("") is None


# ---------------------------------------------------------------------------
# Provider profile heuristics
# ---------------------------------------------------------------------------


class TestProviderClassification:
    def test_etf_profile_maps_to_etfs(self):
        out = tax.classify_by_provider_profile({
            "isEtf": True, "sector": "Financial Services",
            "industry": "Asset Management",
        })
        assert out["broad"] == "ETFs"

    def test_semiconductor_industry_assigns_subcategory(self):
        out = tax.classify_by_provider_profile({
            "sector": "Technology", "industry": "Semiconductors",
        })
        assert out["broad"] == "Technology"
        assert "Semiconductors" in out["subs"]

    def test_chinese_adr_layered(self):
        out = tax.classify_by_provider_profile({
            "sector": "Consumer Cyclical", "industry": "Auto Manufacturers",
            "country": "CN",
        })
        assert "China ADR" in out["subs"]

    def test_non_us_adr_layered(self):
        out = tax.classify_by_provider_profile({
            "sector": "Communication Services", "industry": "Telecom Services",
            "country": "FI",
        })
        assert "ADRs" in out["subs"]

    def test_empty_profile_returns_none_broad(self):
        out = tax.classify_by_provider_profile({})
        assert out["broad"] is None
        assert out["subs"] == ()
        out_none = tax.classify_by_provider_profile(None)
        assert out_none["broad"] is None
        assert out_none["subs"] == ()


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


class TestMerge:
    def test_static_wins_broad_when_both_present(self):
        s = {"broad": "Technology", "subs": ("Semiconductors",)}
        p = {"broad": "Industrials", "subs": ("AI Infrastructure",)}
        out = tax.merge_taxonomy_tags(s, p)
        assert out.broad == "Technology"
        assert out.source == "merged"
        assert "Semiconductors" in out.subs
        assert "AI Infrastructure" in out.subs

    def test_provider_only_path(self):
        out = tax.merge_taxonomy_tags(None, {"broad": "Healthcare", "subs": ("Biotech",)})
        assert out.broad == "Healthcare"
        assert out.source == "provider"

    def test_static_only_path(self):
        out = tax.merge_taxonomy_tags({"broad": "Energy", "subs": ()}, None)
        assert out.broad == "Energy"
        assert out.source == "static"

    def test_unknown_path(self):
        out = tax.merge_taxonomy_tags(None, None)
        assert out.broad is None
        assert out.subs == ()
        assert out.source == "unknown"

    def test_dedup_subs(self):
        s = {"broad": "Technology", "subs": ("Semiconductors", "AI Infrastructure")}
        p = {"broad": "Technology", "subs": ("Semiconductors", "Data Centers")}
        out = tax.merge_taxonomy_tags(s, p)
        assert out.subs.count("Semiconductors") == 1


# ---------------------------------------------------------------------------
# Filter
# ---------------------------------------------------------------------------


class TestFilter:
    def _items(self):
        return [
            {"t": "NVDA", "taxonomy_tags": {"broad": "Technology",
                                            "subs": ["Semiconductors", "AI Infrastructure"]}},
            {"t": "JPM",  "taxonomy_tags": {"broad": "Financials",
                                            "subs": ["Banks"]}},
            {"t": "RKLB", "taxonomy_tags": {"broad": "Industrials",
                                            "subs": ["Space-Rocket"]}},
            {"t": "SPY",  "taxonomy_tags": {"broad": "ETFs", "subs": []}},
        ]

    def test_filter_by_broad(self):
        out = tax.filter_universe_by_categories(self._items(), broad_categories=["Technology"])
        assert [it["t"] for it in out] == ["NVDA"]

    def test_filter_by_sub(self):
        out = tax.filter_universe_by_categories(self._items(), subcategories=["Banks"])
        assert [it["t"] for it in out] == ["JPM"]

    def test_filter_by_both(self):
        out = tax.filter_universe_by_categories(self._items(),
                                                broad_categories=["Technology"],
                                                subcategories=["Semiconductors"])
        assert [it["t"] for it in out] == ["NVDA"]

    def test_no_filter_returns_all(self):
        out = tax.filter_universe_by_categories(self._items())
        assert len(out) == 4

    def test_filter_no_match_returns_empty(self):
        out = tax.filter_universe_by_categories(self._items(),
                                                broad_categories=["User Custom"])
        assert out == []


# ---------------------------------------------------------------------------
# Source-grep guards
# ---------------------------------------------------------------------------


class TestNoForbiddenSymbolsP1:
    def test_taxonomy_module_safety(self):
        src = _strip_python(inspect.getsource(tax))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "/equity/orders/limit", "/equity/orders/market",
            "session.add", "session.commit",
            "selenium", "playwright", "puppeteer", "webdriver",
            "buy now", "sell now", "target price", "position sizing",
        ):
            assert needle.lower() not in src.lower(), (
                f"market_taxonomy.py must not contain {needle!r}"
            )

    def test_router_module_safety(self):
        from apps.api.routers import scanner_taxonomy as router_mod
        src = _strip_python(inspect.getsource(router_mod))
        for needle in (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "session.add", "session.commit",
            "buy now", "sell now", "target price", "position sizing",
        ):
            assert needle.lower() not in src.lower(), (
                f"scanner_taxonomy router must not contain {needle!r}"
            )
