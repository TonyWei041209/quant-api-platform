"""Unit tests — Trading 212 Mirror Watchlist service.

Verifies:
  - Held + recently-traded + manually-watched are merged into a single
    deduplicated list keyed by display_ticker.
  - broker_ticker is normalized (`MU_US_EQ` -> `MU`) but the original
    string is preserved on the item.
  - Unmapped tickers stay visible and carry an UNMAPPED source tag.
  - The service does not write the database.
  - The service does not import any T212 write endpoint, order_intent,
    order_draft, FEATURE_T212_LIVE_SUBMIT mutation, or scraping/browser
    automation symbols.

Hermetic: SQL boundary is mocked. No DB, no network.
"""
from __future__ import annotations

import inspect
import io
import tokenize
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from libs.portfolio import mirror_watchlist_service as svc
from libs.portfolio.mirror_watchlist_service import (
    build_mirror_watchlist,
    normalize_display_ticker,
    normalize_user_ticker,
)


def _row(*values):
    return values


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
# Pure functions
# ---------------------------------------------------------------------------

class TestNormalization:
    def test_broker_ticker_strips_exchange_and_type_segments(self):
        assert normalize_display_ticker("MU_US_EQ") == "MU"
        assert normalize_display_ticker("NOK_US_EQ") == "NOK"
        assert normalize_display_ticker("VACQ_US_EQ") == "VACQ"

    def test_broker_ticker_lowercase_input_uppercased(self):
        assert normalize_display_ticker("smsnl_eq") == "SMSNL"

    def test_broker_ticker_none_or_empty(self):
        assert normalize_display_ticker(None) is None
        assert normalize_display_ticker("") is None

    def test_user_ticker_strips_garbage(self):
        assert normalize_user_ticker("  rklb  ") == "RKLB"
        assert normalize_user_ticker("CRWV!") == "CRWV"
        assert normalize_user_ticker("HIMS$%") == "HIMS"
        assert normalize_user_ticker("AAA-BBB") == "AAA-BBB"
        assert normalize_user_ticker("") is None
        assert normalize_user_ticker("$$$") is None
        assert normalize_user_ticker(None) is None

    def test_user_ticker_truncates_overly_long(self):
        long_input = "A" * 50
        result = normalize_user_ticker(long_input)
        assert result is not None
        assert len(result) == 20


# ---------------------------------------------------------------------------
# build_mirror_watchlist
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_with_resolver():
    """Resolver: MU and NOK map to instruments; VACQ does NOT."""
    db = MagicMock()
    # The first two SELECTs are the resolver lookups (ticker_history then
    # instrument_identifier). Then _fetch_held does sid lookup + positions.
    # Then _fetch_recently_traded does its query.
    return db


def _resolver_rows():
    """Resolver rows: MU_inst -> 'Micron Tech', NOK_inst -> 'Nokia'."""
    return [
        ("MU", "11111111-1111-1111-1111-111111111111", "Micron Technology"),
        ("NOK", "22222222-2222-2222-2222-222222222222", "Nokia Oyj"),
    ]


def _build_db_for_scenario(*, held_rows, recent_rows, has_session_id=True):
    db = MagicMock()
    sid = "33333333-3333-3333-3333-333333333333"

    # _build_ticker_resolver issues 2 queries (ticker_history + identifier)
    resolver_first_query = MagicMock(fetchall=MagicMock(return_value=_resolver_rows()))
    resolver_second_query = MagicMock(fetchall=MagicMock(return_value=[]))

    # _fetch_held issues 1 sid lookup + 1 positions query
    sid_lookup = MagicMock(fetchone=MagicMock(
        return_value=_row(sid) if has_session_id else None
    ))
    positions_query = MagicMock(fetchall=MagicMock(return_value=held_rows))

    # _fetch_recently_traded issues 1 query
    recent_query = MagicMock(fetchall=MagicMock(return_value=recent_rows))

    db.execute.side_effect = [
        resolver_first_query,
        resolver_second_query,
        sid_lookup,
        positions_query,
        recent_query,
    ]
    return db


@pytest.mark.unit
class TestMirrorComposition:
    def test_held_only_with_resolved_instruments(self):
        snap_at = datetime(2026, 5, 8, 19, 53, tzinfo=timezone.utc)
        held = [
            _row("MU_US_EQ",
                 "11111111-1111-1111-1111-111111111111",
                 5.22, 733.10, 3826.6, 532.0, snap_at),
            _row("NOK_US_EQ",
                 "22222222-2222-2222-2222-222222222222",
                 109.50, 12.83, 1404.7, 53.0, snap_at),
        ]
        db = _build_db_for_scenario(held_rows=held, recent_rows=[])
        result = build_mirror_watchlist(db, manual_tickers=None)

        tickers = [it["display_ticker"] for it in result["items"]]
        assert tickers == ["MU", "NOK"]
        for item in result["items"]:
            assert item["is_currently_held"] is True
            assert "HELD" in item["source_tags"]
            assert item["mapping_status"] == "mapped"
            assert item["instrument_id"] is not None

    def test_recently_traded_unmapped_ticker_visible_with_unmapped_tag(self):
        # VACQ_US_EQ is in recent orders but NOT in the resolver
        snap_at = datetime(2026, 5, 8, 14, 30, tzinfo=timezone.utc)
        held = []
        recent = [
            _row("VACQ_US_EQ", snap_at, snap_at),
        ]
        db = _build_db_for_scenario(held_rows=held, recent_rows=recent)
        result = build_mirror_watchlist(db)

        items = result["items"]
        assert len(items) == 1
        item = items[0]
        assert item["display_ticker"] == "VACQ"
        assert item["broker_ticker"] == "VACQ_US_EQ"
        assert item["is_recently_traded"] is True
        assert item["instrument_id"] is None
        assert item["mapping_status"] == "unresolved"
        assert "RECENTLY_TRADED" in item["source_tags"]
        assert "UNMAPPED" in item["source_tags"]

    def test_dedup_held_and_recent_same_ticker(self):
        # MU appears in BOTH held and recently traded — must dedupe.
        snap_at = datetime(2026, 5, 8, 19, 53, tzinfo=timezone.utc)
        held = [
            _row("MU_US_EQ",
                 "11111111-1111-1111-1111-111111111111",
                 5.22, 733.10, 3826.6, 532.0, snap_at),
        ]
        recent = [
            _row("MU_US_EQ", snap_at, snap_at),
        ]
        db = _build_db_for_scenario(held_rows=held, recent_rows=recent)
        result = build_mirror_watchlist(db)

        mu_items = [it for it in result["items"] if it["display_ticker"] == "MU"]
        assert len(mu_items) == 1, "duplicate display_ticker must be merged"
        item = mu_items[0]
        assert item["is_currently_held"] is True
        assert item["is_recently_traded"] is True
        assert "HELD" in item["source_tags"]
        assert "RECENTLY_TRADED" in item["source_tags"]
        # Held wins for the live_* fields
        assert item["live_quantity"] == 5.22

    def test_user_watched_dedup_with_held(self):
        # User adds "MU" manually; MU is already held. Both tags must show.
        snap_at = datetime(2026, 5, 8, 19, 53, tzinfo=timezone.utc)
        held = [
            _row("MU_US_EQ",
                 "11111111-1111-1111-1111-111111111111",
                 5.22, 733.10, 3826.6, 532.0, snap_at),
        ]
        db = _build_db_for_scenario(held_rows=held, recent_rows=[])
        result = build_mirror_watchlist(db, manual_tickers=["MU", "RKLB"])

        items = result["items"]
        # MU merged; RKLB added (unresolved)
        by_ticker = {it["display_ticker"]: it for it in items}
        assert "MU" in by_ticker
        assert "RKLB" in by_ticker
        mu = by_ticker["MU"]
        assert mu["is_currently_held"] is True
        assert mu["is_user_watched"] is True
        assert "HELD" in mu["source_tags"]
        assert "WATCHED" in mu["source_tags"]
        rklb = by_ticker["RKLB"]
        assert rklb["is_user_watched"] is True
        assert "WATCHED" in rklb["source_tags"]
        assert "UNMAPPED" in rklb["source_tags"]
        assert rklb["mapping_status"] == "unresolved"

    def test_held_sorted_before_recent_before_watched(self):
        snap_at = datetime(2026, 5, 8, 19, 53, tzinfo=timezone.utc)
        held = [
            _row("MU_US_EQ",
                 "11111111-1111-1111-1111-111111111111",
                 5.22, 733.10, 3826.6, 532.0, snap_at),
        ]
        recent = [
            _row("VACQ_US_EQ", snap_at, snap_at),
        ]
        db = _build_db_for_scenario(held_rows=held, recent_rows=recent)
        result = build_mirror_watchlist(db, manual_tickers=["RKLB"])

        order = [it["display_ticker"] for it in result["items"]]
        assert order == ["MU", "VACQ", "RKLB"]

    def test_response_shape_contract(self):
        db = _build_db_for_scenario(held_rows=[], recent_rows=[])
        result = build_mirror_watchlist(db)

        assert result["name"] == "Trading 212 Mirror"
        assert result["source"] == "trading212_mirror"
        assert result["official_watchlist_api_available"] is False
        assert "Trading 212 does not expose" in result["explanation"]
        assert isinstance(result["counts"], dict)
        for k in ("held", "recently_traded", "user_watched", "total", "unmapped"):
            assert k in result["counts"]
        assert isinstance(result["items"], list)
        assert isinstance(result["generated_at"], str)

    def test_legacy_fallback_when_no_session_id_yet(self):
        """When no row has sync_session_id (pre-deploy state), the held
        fetch must use the legacy DISTINCT-ON path so the mirror still
        renders during a rollout window."""
        snap_at = datetime(2026, 4, 1, 8, 0, tzinfo=timezone.utc)
        held = [
            _row("MU_US_EQ",
                 "11111111-1111-1111-1111-111111111111",
                 5.0, 700.0, 3500.0, 100.0, snap_at),
        ]
        db = _build_db_for_scenario(held_rows=held, recent_rows=[], has_session_id=False)
        result = build_mirror_watchlist(db)
        assert result["counts"]["held"] == 1
        assert result["items"][0]["display_ticker"] == "MU"

    def test_recent_orders_can_be_disabled(self):
        snap_at = datetime(2026, 5, 8, 19, 53, tzinfo=timezone.utc)
        held = [
            _row("MU_US_EQ",
                 "11111111-1111-1111-1111-111111111111",
                 5.22, 733.10, 3826.6, 532.0, snap_at),
        ]
        # When include_recent_orders=False, _fetch_recently_traded must NOT
        # be called. We stub only 4 SQL calls (resolver x2 + sid + held).
        db = MagicMock()
        db.execute.side_effect = [
            MagicMock(fetchall=MagicMock(return_value=_resolver_rows())),
            MagicMock(fetchall=MagicMock(return_value=[])),
            MagicMock(fetchone=MagicMock(return_value=_row("33333333-3333-3333-3333-333333333333"))),
            MagicMock(fetchall=MagicMock(return_value=held)),
        ]
        result = build_mirror_watchlist(db, include_recent_orders=False)
        assert db.execute.call_count == 4, (
            "include_recent_orders=False must skip the broker_order_snapshot query"
        )
        assert result["counts"]["recently_traded"] == 0


# ---------------------------------------------------------------------------
# Source-grep guards
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestNoForbiddenSymbols:
    """Pin: the new module must not write the DB, must not call any T212
    write endpoint, must not touch order_intent / order_draft / submit
    objects, must not mutate the live-submit feature flag, must not contain
    scraping/browser-automation hints."""

    def test_mirror_service_no_db_writes(self):
        src = _strip_python(inspect.getsource(svc))
        for needle in ("session.add", "session.commit", "session.delete",
                       ".add(", ".commit()", ".flush()", "INSERT INTO",
                       "UPDATE ", "DELETE FROM"):
            assert needle not in src, f"mirror_watchlist_service must not contain {needle!r}"

    def test_mirror_service_no_t212_write_or_execution_objects(self):
        src = _strip_python(inspect.getsource(svc))
        forbidden = (
            "submit_limit_order", "submit_market_order", "submit_order",
            "/equity/orders/limit", "/equity/orders/market",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "feature_t212_live_submit = True",
            "FEATURE_T212_LIVE_SUBMIT = True",
        )
        for needle in forbidden:
            assert needle not in src, f"mirror_watchlist_service must not contain {needle!r}"

    def test_mirror_service_no_scraping_or_browser_automation(self):
        src = _strip_python(inspect.getsource(svc))
        forbidden = (
            "selenium", "playwright", "puppeteer", "webdriver",
            "BeautifulSoup", "headless", "chromium",
        )
        for needle in forbidden:
            assert needle.lower() not in src.lower(), (
                f"mirror_watchlist_service must not import scraping/automation lib {needle}"
            )

    def test_mirror_router_no_forbidden_symbols(self):
        from apps.api.routers import mirror_watchlist as router_mod
        src = _strip_python(inspect.getsource(router_mod))
        forbidden = (
            "submit_limit_order", "submit_market_order", "submit_order",
            "OrderIntent", "OrderDraft", "order_intent", "order_draft",
            "session.add", "session.commit", "session.delete",
            "selenium", "playwright", "puppeteer",
            "feature_t212_live_submit = True",
            "FEATURE_T212_LIVE_SUBMIT = True",
        )
        for needle in forbidden:
            assert needle not in src, f"mirror_watchlist router must not contain {needle!r}"
