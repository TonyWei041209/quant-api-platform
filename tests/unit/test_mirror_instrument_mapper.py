"""Unit tests — Trading 212 Mirror instrument mapper.

Hermetic: SQL is mocked at the boundary; FMP fetcher is injectable so no
real HTTP traffic happens. The plan path is pure read-only and never
writes the database.
"""
from __future__ import annotations

import asyncio
import inspect
import io
import tokenize
from unittest.mock import MagicMock

import pytest

from libs.instruments import mirror_instrument_mapper as mod
from libs.instruments.mirror_instrument_mapper import (
    PROTECTED_TICKERS,
    build_mirror_mapping_plan,
    filter_for_bootstrap,
    render_mapping_plan_report,
    _profile_to_fields,
)


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


def _build_db_for_mirror(mirror_items, existing_ticker_to_row):
    """Build a MagicMock session that the mapper's two layers will hit:
       1. mirror_watchlist_service.build_mirror_watchlist (uses 5 SQL calls
          internally — see mirror tests; we patch build_mirror_watchlist
          directly instead in tests below to keep this fixture simple)
       2. _lookup_existing_mappings (1 or 2 SELECTs)
    """
    db = MagicMock()
    # Three execute returns are used by _lookup_existing_mappings:
    # - identifier query (returns rows for existing_ticker_to_row keys)
    # - history query (returns nothing extra)
    # build_mirror_watchlist is patched separately; this stub is only used
    # to satisfy the second layer.
    identifier_rows = []
    for tk, row in existing_ticker_to_row.items():
        identifier_rows.append((
            tk,
            row["instrument_id"],
            row["company_name"],
            row["asset_type"],
            row["exchange_primary"],
            row["currency"],
            row["country_code"],
        ))
    db.execute.side_effect = [
        MagicMock(fetchall=MagicMock(return_value=identifier_rows)),
        MagicMock(fetchall=MagicMock(return_value=[])),
    ]
    return db


def _patched_mirror(mocker_target, items):
    """Return a fake mirror payload that mimics build_mirror_watchlist."""
    return {
        "name": "Trading 212 Mirror",
        "items": items,
    }


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestProfileToFields:
    def test_empty_profile_returns_all_none(self):
        assert _profile_to_fields("RKLB", None) == {
            "company_name": None, "exchange_primary": None,
            "currency": None, "country_code": None, "asset_type": None,
        }
        assert _profile_to_fields("RKLB", {}) == {
            "company_name": None, "exchange_primary": None,
            "currency": None, "country_code": None, "asset_type": None,
        }

    def test_full_equity_profile(self):
        raw = {
            "companyName": "Rocket Lab USA, Inc.",
            "exchangeShortName": "NASDAQ",
            "currency": "USD",
            "country": "US",
            "isEtf": False,
        }
        out = _profile_to_fields("RKLB", raw)
        assert out["company_name"] == "Rocket Lab USA, Inc."
        assert out["exchange_primary"] == "NASDAQ"
        assert out["currency"] == "USD"
        assert out["country_code"] == "US"
        assert out["asset_type"] == "EQUITY"

    def test_etf_profile(self):
        raw = {"name": "iShares Russell 2000", "isEtf": True, "currency": "USD"}
        out = _profile_to_fields("IWM", raw)
        assert out["asset_type"] == "ETF"
        assert out["company_name"] == "iShares Russell 2000"


# ---------------------------------------------------------------------------
# build_mirror_mapping_plan
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildPlan:
    def test_mapped_ticker_returns_mapped_status(self, monkeypatch):
        # Mock build_mirror_watchlist to return MU + RKLB
        monkeypatch.setattr(
            mod, "_lookup_existing_mappings",
            lambda db, tickers: {
                "MU": {
                    "instrument_id": "11111111-1111-1111-1111-111111111111",
                    "company_name": "Micron Technology",
                    "asset_type": "EQUITY",
                    "exchange_primary": "NASDAQ",
                    "currency": "USD",
                    "country_code": "US",
                },
            }
        )
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: _patched_mirror(None, [
                {"display_ticker": "MU", "broker_ticker": "MU_US_EQ", "source_tags": ["HELD"]},
                {"display_ticker": "RKLB", "broker_ticker": None, "source_tags": ["WATCHED", "UNMAPPED"]},
            ])
        )

        db = MagicMock()
        plan = asyncio.run(build_mirror_mapping_plan(db, fetch_profiles=False))
        statuses = {it.display_ticker: it.mapping_status for it in plan.items}
        assert statuses["MU"] == "mapped"
        assert statuses["RKLB"] == "unmapped"
        # Mapped item has instrument_id populated
        mu = next(it for it in plan.items if it.display_ticker == "MU")
        assert mu.instrument_id == "11111111-1111-1111-1111-111111111111"
        assert mu.company_name == "Micron Technology"
        # Counts
        assert plan.counts["mapped"] == 1
        assert plan.counts["unmapped"] == 1
        assert plan.counts["total"] == 2

    def test_fetch_profiles_returns_newly_resolvable_with_profile(self, monkeypatch):
        monkeypatch.setattr(mod, "_lookup_existing_mappings", lambda db, t: {})

        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: _patched_mirror(None, [
                {"display_ticker": "RKLB", "broker_ticker": None, "source_tags": ["WATCHED"]},
            ])
        )

        async def fake_profile(symbol):
            return {
                "companyName": "Rocket Lab USA, Inc.",
                "exchangeShortName": "NASDAQ",
                "currency": "USD", "country": "US", "isEtf": False,
            }

        plan = asyncio.run(build_mirror_mapping_plan(
            MagicMock(),
            fetch_profiles=True,
            fmp_profile_fetcher=fake_profile,
        ))
        rklb = next(it for it in plan.items if it.display_ticker == "RKLB")
        assert rklb.mapping_status == "newly_resolvable"
        assert rklb.company_name == "Rocket Lab USA, Inc."
        assert rklb.exchange_primary == "NASDAQ"
        assert rklb.provider_attempted is True
        assert rklb.to_dict()["would_create"] == {
            "instrument": True, "instrument_identifier": True, "ticker_history": True,
        }

    def test_fetch_profiles_returns_unresolved_when_provider_empty(self, monkeypatch):
        monkeypatch.setattr(mod, "_lookup_existing_mappings", lambda db, t: {})
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: _patched_mirror(None, [
                {"display_ticker": "ZZZZ9", "broker_ticker": None, "source_tags": ["WATCHED"]},
            ])
        )

        async def empty_profile(symbol):
            return {}

        plan = asyncio.run(build_mirror_mapping_plan(
            MagicMock(),
            fetch_profiles=True,
            fmp_profile_fetcher=empty_profile,
        ))
        zz = plan.items[0]
        assert zz.mapping_status == "unresolved"
        assert zz.provider_attempted is True
        assert zz.to_dict()["would_create"] == {
            "instrument": False, "instrument_identifier": False, "ticker_history": False,
        }

    def test_provider_exception_returns_unresolved_with_error(self, monkeypatch):
        monkeypatch.setattr(mod, "_lookup_existing_mappings", lambda db, t: {})
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: _patched_mirror(None, [
                {"display_ticker": "OOPS", "broker_ticker": None, "source_tags": ["WATCHED"]},
            ])
        )

        async def boom(symbol):
            raise RuntimeError("simulated FMP error")

        plan = asyncio.run(build_mirror_mapping_plan(
            MagicMock(),
            fetch_profiles=True,
            fmp_profile_fetcher=boom,
        ))
        item = plan.items[0]
        assert item.mapping_status == "unresolved"
        assert item.provider_error is not None
        assert "simulated FMP error" in item.provider_error

    def test_protected_ticker_marked(self, monkeypatch):
        monkeypatch.setattr(mod, "_lookup_existing_mappings", lambda db, t: {})
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: _patched_mirror(None, [
                {"display_ticker": "NVDA", "broker_ticker": "NVDA_US_EQ", "source_tags": ["WATCHED"]},
            ])
        )
        plan = asyncio.run(build_mirror_mapping_plan(MagicMock(), fetch_profiles=False))
        nvda = plan.items[0]
        assert nvda.is_protected is True
        # Even if NVDA were marked newly_resolvable later, filter excludes it
        nvda_status_overridden = nvda.mapping_status  # unmapped (no profile)
        assert plan.counts["protected_excluded"] == 1


@pytest.mark.unit
class TestFilterForBootstrap:
    def test_only_newly_resolvable_non_protected_pass(self, monkeypatch):
        # Simulate plan with mixed statuses
        plan = mod.MirrorMappingPlan(
            generated_at=mod.utc_now(),
            source="trading212_mirror",
            dry_run=True,
            fetch_profiles=True,
            items=[
                mod.MirrorMappingItem(
                    display_ticker="RKLB", broker_ticker=None,
                    mapping_status="newly_resolvable",
                    instrument_id=None, company_name="Rocket Lab",
                    asset_type="EQUITY", exchange_primary="NASDAQ",
                    currency="USD", country_code="US",
                    provider_profile={}, provider_attempted=True,
                    provider_error=None, is_protected=False,
                    source_tags=("WATCHED",),
                ),
                mod.MirrorMappingItem(
                    display_ticker="NVDA", broker_ticker="NVDA_US_EQ",
                    mapping_status="newly_resolvable",
                    instrument_id=None, company_name="NVIDIA",
                    asset_type="EQUITY", exchange_primary="NASDAQ",
                    currency="USD", country_code="US",
                    provider_profile={}, provider_attempted=True,
                    provider_error=None, is_protected=True,
                    source_tags=("WATCHED",),
                ),
                mod.MirrorMappingItem(
                    display_ticker="MU", broker_ticker="MU_US_EQ",
                    mapping_status="mapped",
                    instrument_id="...", company_name="Micron",
                    asset_type="EQUITY", exchange_primary="NASDAQ",
                    currency="USD", country_code="US",
                    provider_profile=None, provider_attempted=False,
                    provider_error=None, is_protected=False,
                    source_tags=("HELD",),
                ),
                mod.MirrorMappingItem(
                    display_ticker="OOPS", broker_ticker=None,
                    mapping_status="unresolved",
                    instrument_id=None, company_name=None,
                    asset_type=None, exchange_primary=None,
                    currency=None, country_code=None,
                    provider_profile=None, provider_attempted=True,
                    provider_error="x", is_protected=False,
                    source_tags=("WATCHED",),
                ),
            ],
        )
        eligible = filter_for_bootstrap(plan)
        # Only RKLB qualifies — NVDA excluded for protected, MU excluded
        # because already mapped, OOPS excluded for unresolved.
        assert eligible == ("RKLB",)


# ---------------------------------------------------------------------------
# Plan output is read-only
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPlanIsReadOnly:
    def test_plan_to_dict_attests_no_writes(self, monkeypatch):
        monkeypatch.setattr(mod, "_lookup_existing_mappings", lambda db, t: {})
        from libs.portfolio import mirror_watchlist_service as mws
        monkeypatch.setattr(
            mws, "build_mirror_watchlist",
            lambda db, **kwargs: _patched_mirror(None, [])
        )
        plan = asyncio.run(build_mirror_mapping_plan(MagicMock(), fetch_profiles=False))
        d = plan.to_dict()
        assert d["dry_run"] is True
        side = d["side_effects"]
        assert side["db_writes"] == "NONE"
        assert side["broker_writes"] == "NONE"
        assert side["execution_objects"] == "NONE"
        assert "FEATURE_T212_LIVE_SUBMIT=false" in side["live_submit"]


# ---------------------------------------------------------------------------
# Source-grep guards
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNoForbiddenSymbols:
    def test_module_no_t212_writes_or_execution_objects(self):
        src = _strip_python(inspect.getsource(mod))
        forbidden = (
            "submit_limit_order", "submit_market_order", "submit_order",
            "/equity/orders/limit", "/equity/orders/market",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "feature_t212_live_submit = True",
            "FEATURE_T212_LIVE_SUBMIT = True",
        )
        for needle in forbidden:
            assert needle not in src, f"mirror_instrument_mapper must not contain {needle!r}"

    def test_module_no_scraping(self):
        src = _strip_python(inspect.getsource(mod)).lower()
        for needle in ("selenium", "playwright", "puppeteer", "webdriver", "beautifulsoup"):
            assert needle not in src, f"must not import {needle}"

    def test_module_does_not_write_db_directly(self):
        src = _strip_python(inspect.getsource(mod))
        for needle in ("session.add", "session.commit", "session.delete",
                       "INSERT INTO", "UPDATE ", "DELETE FROM"):
            assert needle not in src, (
                f"mirror_instrument_mapper must not contain {needle!r} — "
                "the write path is delegated to bootstrap_research_universe_prod."
            )
