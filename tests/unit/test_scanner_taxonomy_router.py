"""Bounded all-market scan planning — router tests.

Anchors the contract:
  * /api/scanner/taxonomy/categories returns broad + sub list
  * /api/scanner/provider-capabilities flags the readiness of
    the all-market scan (boolean, never a buy/sell instruction)
  * /api/scanner/all-market/preview ALWAYS sets
    requires_overnight_job=true so the UI is forced to gate
    behind a Cloud Run Job — no unbounded interactive scan
  * /api/scanner/all-market/preview ALWAYS clamps to
    ALL_MARKET_PREVIEW_CEILING (1000)
  * Language policy contains no banned trade-action phrases
"""
from __future__ import annotations

import inspect

from fastapi.testclient import TestClient

from apps.api.routers import scanner_taxonomy
from apps.api.routers.scanner_taxonomy import (
    ALL_MARKET_PREVIEW_CEILING,
    ALL_MARKET_PREVIEW_DEFAULT,
)

# Build a minimal app that mounts ONLY this router with NO auth, so the
# test can exercise the response shape without needing a Firebase token.
from fastapi import FastAPI

app = FastAPI()
app.include_router(scanner_taxonomy.router, prefix="/scanner")
client = TestClient(app)


BANNED_PHRASES = (
    "buy now", "sell now", "enter long", "enter short",
    "target price", "position size", "guaranteed",
    "必涨", "必跌", "买入建议", "卖出建议", "目标价",
)


class TestCategoriesEndpoint:
    def test_returns_broad_and_subcategories(self):
        r = client.get("/scanner/taxonomy/categories")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["broad_categories"], list)
        assert isinstance(body["subcategories"], list)
        # Expect the well-known broad anchors. The taxonomy uses
        # GICS-style "Consumer Discretionary" / "Consumer Staples"
        # rather than a single "Consumer".
        broad = set(body["broad_categories"])
        for required in ("Technology", "Healthcare", "Financials",
                         "Industrials"):
            assert required in broad, (
                f"missing core broad category {required!r}; "
                f"got {sorted(broad)}"
            )
        # At least one Consumer flavour must be present.
        assert any(b.startswith("Consumer") for b in broad), (
            f"no Consumer* broad in {sorted(broad)}"
        )

    def test_language_policy_clean(self):
        r = client.get("/scanner/taxonomy/categories")
        text = (r.json().get("language_policy") or "").lower()
        for needle in BANNED_PHRASES:
            assert needle not in text


class TestProviderCapabilities:
    def test_returns_boolean_flags_only(self):
        r = client.get("/scanner/provider-capabilities")
        assert r.status_code == 200
        body = r.json()
        # The flag must exist; its value depends on FMP secret
        # configuration (true in production, false in test env).
        assert "all_market_scan_ready" in body
        assert isinstance(body["all_market_scan_ready"], bool)


class TestAllMarketPreviewBounded:
    def test_defaults_are_research_only_with_job_gate(self):
        r = client.get("/scanner/all-market/preview")
        assert r.status_code == 200
        body = r.json()
        # Mandatory gating fields:
        assert body["requires_overnight_job"] is True
        assert body["job_required"] is True  # legacy alias
        # Bounded planning fields:
        assert body["max_symbols"] == ALL_MARKET_PREVIEW_CEILING
        assert body["limit"] == ALL_MARKET_PREVIEW_DEFAULT
        assert isinstance(body["estimated_symbol_count"], int)
        assert isinstance(body["provider_call_estimate"], int)
        # estimated_symbol_count should never exceed max_symbols by
        # contract; preview_count is the truncated render-list.
        assert body["preview_count"] <= body["limit"]
        # Language policy clean
        text = (body.get("language_policy") or "").lower()
        for needle in BANNED_PHRASES:
            assert needle not in text

    def test_limit_clamped_to_ceiling(self):
        r = client.get(
            f"/scanner/all-market/preview?limit={ALL_MARKET_PREVIEW_CEILING + 5000}"
        )
        # FastAPI Query(le=...) clamps via 422 not silent truncation:
        # confirm a request OVER the ceiling is refused (UI should
        # know to gate the request).
        assert r.status_code == 422

    def test_filter_by_broad_returns_subset(self):
        # Tech is well-populated in the static theme map.
        r_all = client.get("/scanner/all-market/preview")
        r_tech = client.get(
            "/scanner/all-market/preview?broad=Technology"
        )
        assert r_all.status_code == 200
        assert r_tech.status_code == 200
        assert (r_tech.json()["estimated_symbol_count"]
                <= r_all.json()["estimated_symbol_count"])
        # All returned items in the Tech response must carry the
        # Technology broad tag in their taxonomy.
        for it in r_tech.json()["items"]:
            assert (it["taxonomy_tags"]["broad"] == "Technology"
                    or "Technology" in (it["taxonomy_tags"]["subs"] or []))

    def test_filter_by_subcategory_returns_subset(self):
        # Pick a sub that's known to exist
        r = client.get(
            "/scanner/all-market/preview?sub=Semiconductors"
        )
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["items"], list)
        # Every returned item should carry the Semiconductors sub
        for it in body["items"]:
            assert "Semiconductors" in (it["taxonomy_tags"]["subs"] or [])

    def test_response_never_contains_banned_phrases(self):
        # Sweep across multiple broad categories — the most common
        # source of accidental banned wording.
        for broad in ("Technology", "Healthcare", "Financials",
                      "Consumer Discretionary", "Industrials"):
            r = client.get(f"/scanner/all-market/preview?broad={broad}")
            assert r.status_code == 200
            body = r.json()
            blob = (
                str(body.get("language_policy", "")) + " " +
                str(body.get("source", ""))
            ).lower()
            for needle in BANNED_PHRASES:
                assert needle not in blob, (
                    f"banned phrase {needle!r} appeared for "
                    f"broad={broad!r} in language_policy/source"
                )

    def test_no_provider_http_in_preview_path(self):
        """The preview endpoint reads only the static theme map and
        must never make a network call. Inspect the source to confirm
        no provider import / HTTP client usage in the handler body."""
        src = inspect.getsource(scanner_taxonomy.all_market_preview)
        for needle in ("requests.", "httpx.", "aiohttp.",
                       "FMPAdapter", "PolygonAdapter", "T212Adapter",
                       "submit_order", "OrderIntent", "OrderDraft"):
            assert needle not in src, (
                f"forbidden token {needle!r} in all_market_preview body"
            )
