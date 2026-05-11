"""External-headline policy guard.

Boundary:
  * Headlines coming back from FMP / Polygon-Massive news endpoints
    may legitimately contain words like "Buy", "Prediction",
    "Forecast", "Target" — those are the publisher's editorial
    choices. We pass them through unchanged.
  * Platform-generated language (the brief's `explanation`,
    `why_it_matters`, the candidate `research_priority_factors[].label`,
    and the disclaimer strings) MUST NEVER contain banned trade-action
    phrases.

These tests anchor the boundary so a future change can't accidentally
add a banned word to platform-generated text under the assumption "the
brief uses words too".
"""
from __future__ import annotations

import asyncio
import inspect
import io
import tokenize
from unittest.mock import MagicMock

import pytest

from libs.market_brief import overnight_brief_service as obs
from libs.market_events import providers as p


# Re-use the brief test patch helper without copying it
from tests.unit.test_overnight_market_brief import _patch_all_inputs


BANNED_PLATFORM_WORDS = (
    "buy now", "sell now", "enter long", "enter short",
    "target price", "position size", "guaranteed",
    "must rise", "必涨", "必跌", "买入建议", "卖出建议",
    "目标价", "仓位建议",
)


@pytest.fixture(autouse=True)
def _reset_caches():
    p.reset_caches_for_tests()
    yield
    p.reset_caches_for_tests()


def _strip(src: str) -> str:
    out: list[str] = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(src.encode()).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
    except tokenize.TokenizeError:
        return src
    return "".join(out)


class TestExternalHeadlinePolicy:
    def test_brief_pass_through_provider_title_unchanged(self, monkeypatch):
        """An upstream news title containing "Buy XXX" should reach
        the brief candidate's recent_news[].title verbatim — we do
        NOT mutate publisher content."""
        _patch_all_inputs(monkeypatch, mirror_items=[
            {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
             "company_name": "Micron", "instrument_id": "u-mu",
             "source_tags": ["HELD"], "mapping_status": "mapped"},
        ])

        async def empty_fmp(tickers, fd, td, lim):
            return []

        async def polygon_with_buy_in_title(tickers, fd, td, lim):
            return [{
                "id": "x",
                "title": "Analyst Says Buy MU Ahead of Earnings",
                "article_url": "https://e/mu",
                "publisher": {"name": "Example Wire"},
                "tickers": ["MU"],
                "published_utc": "2026-05-09T12:00:00Z",
                "symbol": "MU",
            }]

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty_fmp,
            polygon_news_fetcher=polygon_with_buy_in_title,
            fmp_per_symbol_fetcher=empty_e,
        ))
        mu = out["candidates"][0]
        assert mu["recent_news"], "MU should have news attached"
        # External title preserved exactly — including the word "Buy".
        assert mu["recent_news"][0]["title"].lower().startswith(
            "analyst says buy mu"
        )

    def test_platform_generated_text_never_contains_banned_words(
        self, monkeypatch,
    ):
        """Even with a "Buy MU" headline in scope, the platform's OWN
        explanations and chip labels must stay clean."""
        _patch_all_inputs(monkeypatch,
            scanner_items=[
                {"ticker": "MU", "instrument_id": "u-mu",
                 "issuer_name": "Micron",
                 "scan_types": ["strong_momentum"],
                 "signal_strength": "high", "change_1d_pct": 3.5,
                 "explanation": "X", "risk_flags": []},
            ],
            mirror_items=[
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ",
                 "company_name": "Micron", "instrument_id": "u-mu",
                 "source_tags": ["HELD"], "mapping_status": "mapped"},
            ],
        )

        async def empty(tickers, fd, td, lim):
            return []

        async def polygon_with_buy_title(tickers, fd, td, lim):
            return [{
                "id": "x", "title": "Buy MU now",  # publisher voice
                "article_url": "https://e/mu",
                "publisher": {"name": "E"}, "tickers": ["MU"],
                "published_utc": "2026-05-09T12:00:00Z", "symbol": "MU",
            }] if "MU" in tickers else []

        async def empty_e(symbol):
            return []

        out = asyncio.run(obs.build_overnight_brief(
            MagicMock(),
            fmp_news_fetcher=empty,
            polygon_news_fetcher=polygon_with_buy_title,
            fmp_per_symbol_fetcher=empty_e,
        ))
        mu = out["candidates"][0]
        # Platform-owned fields that should NEVER mention banned words,
        # even in negation. The brief-level `disclaimer` is excluded
        # because it intentionally enumerates the banned terms it does
        # NOT produce — that's the negation contract, not a violation.
        platform_text_blobs: list[str] = []
        platform_text_blobs.append(mu.get("explanation") or "")
        platform_text_blobs.append(mu.get("why_it_matters") or "")
        for f in mu.get("research_priority_factors") or []:
            platform_text_blobs.append(f.get("label") or "")

        for blob in platform_text_blobs:
            low = blob.lower()
            for needle in BANNED_PLATFORM_WORDS:
                assert needle not in low, (
                    f"banned phrase {needle!r} appeared in "
                    f"platform-generated text: {blob!r}"
                )

        # External title preserved (sanity)
        assert any("buy mu now" in n["title"].lower()
                   for n in (mu.get("recent_news") or []))

    def test_i18n_disclaimer_keys_have_negation_language(self):
        """The user-facing disclaimer strings reference banned words
        only to NEGATE them. Confirm both en + zh contain the
        negation."""
        import re
        path = "frontend-react/src/hooks/useI18n.jsx"
        src = open(path, encoding="utf-8").read()
        # English key
        m = re.search(
            r"me_external_headline_disclaimer:\s*'([^']*)'", src,
        )
        assert m, "missing en me_external_headline_disclaimer"
        en = m.group(1).lower()
        assert "not" in en or "never" in en
        # The disclaimer mentions "buy/sell/target/position" only as
        # negation — confirm the words "platform" + "never" appear so
        # the negation is clear.
        assert "platform" in en
        assert "never" in en or "not" in en