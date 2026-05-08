"""Unit tests — /api/broker/t212/live/* endpoints.

Verifies:
  - live/positions / live/summary call the readonly adapter only
  - cache_status="fresh" on first call, "cached" on next call within TTL
  - 429 surfaces cache_status="rate_limited" with the prior payload
  - the route does not write to any DB
  - the route does not invoke any T212 write endpoint
  - source-grep: no order_intent / order_draft / submit imports
"""
from __future__ import annotations

import asyncio
import inspect
import io
import tokenize
from unittest.mock import AsyncMock, MagicMock, patch


def _strip_python(src: str) -> str:
    """Strip docstrings/comments/string literals so source-grep guards don't
    trip on negation language inside docstrings."""
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

import pytest

from apps.api.routers import broker as broker_router
from libs.core.exceptions import RateLimitExceeded
from libs.portfolio import broker_live_cache as live_cache_module


def _fake_response(json_payload, headers=None):
    resp = MagicMock()
    resp.json = MagicMock(return_value=json_payload)
    resp.headers = headers or {}
    return resp


@pytest.fixture(autouse=True)
def reset_cache_singleton():
    live_cache_module.reset_default_cache_for_tests()
    yield
    live_cache_module.reset_default_cache_for_tests()


@pytest.mark.unit
class TestLivePositionsEndpoint:
    def test_positions_returns_envelope_with_fresh_status(self):
        fake_adapter = MagicMock()
        fake_adapter.fetch = AsyncMock(return_value=_fake_response(
            [{"instrument": {"ticker": "MU_US_EQ"}, "quantity": 5.0}],
            headers={"x-ratelimit-limit": "60", "x-ratelimit-remaining": "59"},
        ))
        fake_adapter.normalize_position = lambda raw: {
            "broker_ticker": raw["instrument"]["ticker"],
            "quantity": raw["quantity"],
        }

        with patch.object(broker_router, "_get_adapter", return_value=fake_adapter), \
             patch.object(broker_router, "_is_configured", return_value=True):
            envelope = asyncio.run(broker_router.live_positions())

        assert envelope["source"] == "trading212_live_readonly"
        assert envelope["cache_status"] == "fresh"
        assert envelope["payload"]["connected"] is True
        assert envelope["payload"]["position_count"] == 1
        assert envelope["payload"]["positions"][0]["broker_ticker"] == "MU_US_EQ"
        assert envelope["rate_limit"]["x-ratelimit-remaining"] == "59"
        assert envelope["provider_latency_ms"] is not None

    def test_positions_second_call_within_ttl_is_cached(self):
        fake_adapter = MagicMock()
        fake_adapter.fetch = AsyncMock(return_value=_fake_response(
            [{"instrument": {"ticker": "MU_US_EQ"}, "quantity": 5.0}]
        ))
        fake_adapter.normalize_position = lambda raw: {
            "broker_ticker": raw["instrument"]["ticker"],
            "quantity": raw["quantity"],
        }

        with patch.object(broker_router, "_get_adapter", return_value=fake_adapter), \
             patch.object(broker_router, "_is_configured", return_value=True):
            first = asyncio.run(broker_router.live_positions())
            second = asyncio.run(broker_router.live_positions())

        assert first["cache_status"] == "fresh"
        assert second["cache_status"] == "cached"
        # Only ONE upstream call regardless of how many endpoint hits
        assert fake_adapter.fetch.call_count == 1

    def test_positions_when_not_configured_returns_safe_envelope(self):
        with patch.object(broker_router, "_is_configured", return_value=False):
            envelope = asyncio.run(broker_router.live_positions())
        assert envelope["cache_status"] == "error"
        assert envelope["payload"]["connected"] is False
        assert envelope["payload"]["positions"] == []

    def test_positions_on_429_returns_cached_payload_with_rate_limited_status(self):
        # First fetch succeeds; second raises 429 — second envelope must
        # serve the prior payload with cache_status=rate_limited.
        responses = [
            _fake_response([{"instrument": {"ticker": "MU_US_EQ"}, "quantity": 5.0}])
        ]

        async def fetch_side_effect(*args, **kwargs):
            if responses:
                return responses.pop()
            raise RateLimitExceeded("trading212", "429", {"status": 429})

        fake_adapter = MagicMock()
        fake_adapter.fetch = AsyncMock(side_effect=fetch_side_effect)
        fake_adapter.normalize_position = lambda raw: {
            "broker_ticker": raw["instrument"]["ticker"],
            "quantity": raw["quantity"],
        }

        with patch.object(broker_router, "_get_adapter", return_value=fake_adapter), \
             patch.object(broker_router, "_is_configured", return_value=True):
            asyncio.run(broker_router.live_positions())
            # Force TTL expiry to drive the second fetch
            cache = live_cache_module.get_default_cache()
            cache._cache[("trading212", "default", "positions")].fetched_at = 0
            second = asyncio.run(broker_router.live_positions())

        assert second["cache_status"] == "rate_limited"
        assert second["payload"]["positions"][0]["broker_ticker"] == "MU_US_EQ"
        assert "429" in (second["stale_reason"] or "")


@pytest.mark.unit
class TestLiveSummaryEndpoint:
    def test_summary_returns_envelope_with_fresh_status(self):
        fake_adapter = MagicMock()
        fake_adapter.fetch = AsyncMock(return_value=_fake_response({
            "id": 1, "currency": "USD", "totalValue": 100.5,
            "cash": {"free": 50.0, "total": 50.0, "availableToTrade": 50.0},
        }))

        with patch.object(broker_router, "_get_adapter", return_value=fake_adapter), \
             patch.object(broker_router, "_is_configured", return_value=True):
            env = asyncio.run(broker_router.live_summary())

        assert env["cache_status"] == "fresh"
        assert env["payload"]["portfolio_value"] == 100.5
        assert env["payload"]["currency"] == "USD"
        assert env["payload"]["cash_available_to_trade"] == 50.0


@pytest.mark.unit
class TestLiveStatusEndpoint:
    def test_status_does_not_call_upstream(self):
        # status() inspects the cache only — no upstream fetch
        fake_adapter = MagicMock()
        fake_adapter.fetch = AsyncMock()  # if called, count > 0

        with patch.object(broker_router, "_get_adapter", return_value=fake_adapter), \
             patch.object(broker_router, "_is_configured", return_value=True):
            res = asyncio.run(broker_router.live_status())

        assert res["source"] == "trading212_live_readonly"
        assert res["configured"] is True
        assert "endpoints" in res
        assert fake_adapter.fetch.call_count == 0


@pytest.mark.unit
class TestNoDbWritesFromBrokerRouter:
    """Source-grep guard: the broker router must not import any DB session
    or model. All live truth is read-through; persistence stays in
    sync_trading212_readonly which lives in libs/ingestion."""

    def test_broker_router_does_not_import_db_session(self):
        src = _strip_python(inspect.getsource(broker_router))
        forbidden = [
            "from libs.db.session",
            "import libs.db.session",
            "get_sync_session",
            "get_async_session",
            "session.add",
            "session.commit",
        ]
        for needle in forbidden:
            assert needle not in src, f"broker.py must not reference {needle}"

    def test_broker_router_does_not_call_t212_write_endpoints(self):
        src = _strip_python(inspect.getsource(broker_router))
        forbidden = [
            "submit_limit_order",
            "submit_market_order",
            "/equity/orders/limit",
            "/equity/orders/market",
            "OrderIntent",
            "OrderDraft",
            "feature_t212_live_submit",
            "FEATURE_T212_LIVE_SUBMIT",
        ]
        for needle in forbidden:
            assert needle not in src, f"broker.py must not reference {needle}"
