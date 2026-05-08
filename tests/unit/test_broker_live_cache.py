"""Unit tests — BrokerLiveCache TTL, single-flight, 429 fallback, rate-limit gate.

Hermetic: no network, no DB. The cache's `fetcher` is a plain async lambda.
"""
from __future__ import annotations

import asyncio
import time

import pytest

from libs.core.exceptions import RateLimitExceeded
from libs.portfolio import broker_live_cache as live_cache_module
from libs.portfolio.broker_live_cache import (
    BrokerLiveCache,
    LiveFetchResult,
    POSITIONS_TTL_FLOOR_SECONDS,
    SUMMARY_TTL_FLOOR_SECONDS,
    ORDERS_TTL_FLOOR_SECONDS,
)


@pytest.mark.unit
def test_ttl_floors_enforced_on_construction():
    """A misconfigured TTL below the floor is silently raised to the floor.

    This defends against accidental sub-second polling that would breach
    T212's 1 req/sec limit on the positions endpoint.
    """
    cache = BrokerLiveCache(
        positions_ttl_seconds=0.1,   # below 1.1s floor
        summary_ttl_seconds=1.0,     # below 5.5s floor
        orders_ttl_seconds=1.0,      # below 60s floor
    )
    assert cache.positions_ttl_seconds == POSITIONS_TTL_FLOOR_SECONDS
    assert cache.summary_ttl_seconds == SUMMARY_TTL_FLOOR_SECONDS
    assert cache.orders_ttl_seconds == ORDERS_TTL_FLOOR_SECONDS


@pytest.mark.unit
def test_first_call_is_fresh_subsequent_within_ttl_is_cached():
    cache = BrokerLiveCache(positions_ttl_seconds=2.0)
    fetch_count = 0

    async def fetcher():
        nonlocal fetch_count
        fetch_count += 1
        return [{"ticker": "MU"}], None

    async def go():
        first = await cache.get_or_fetch("trading212", "default", "positions", fetcher)
        second = await cache.get_or_fetch("trading212", "default", "positions", fetcher)
        return first, second

    first, second = asyncio.run(go())
    assert first.cache_status == "fresh"
    assert second.cache_status == "cached"
    assert fetch_count == 1
    assert first.payload == [{"ticker": "MU"}]
    assert second.payload == [{"ticker": "MU"}]


@pytest.mark.unit
def test_concurrent_calls_coalesce_into_one_upstream_fetch():
    cache = BrokerLiveCache()
    fetch_count = 0

    async def slow_fetcher():
        nonlocal fetch_count
        fetch_count += 1
        await asyncio.sleep(0.05)  # simulate network delay
        return ["ok"], None

    async def go():
        return await asyncio.gather(*[
            cache.get_or_fetch("trading212", "default", "positions", slow_fetcher)
            for _ in range(8)
        ])

    results = asyncio.run(go())
    assert fetch_count == 1, "single-flight must coalesce concurrent fetches"
    assert all(r.payload == ["ok"] for r in results)


@pytest.mark.unit
def test_rate_limit_exceeded_falls_back_to_cached_payload():
    cache = BrokerLiveCache(positions_ttl_seconds=POSITIONS_TTL_FLOOR_SECONDS)

    state = {"first": True}

    async def fetcher():
        if state["first"]:
            state["first"] = False
            return ["good"], None
        raise RateLimitExceeded("trading212", "rate limit", {"status": 429})

    async def go():
        first = await cache.get_or_fetch("trading212", "default", "positions", fetcher)
        # Force TTL expiry to drive the second fetch
        cache._cache[("trading212", "default", "positions")].fetched_at = 0
        second = await cache.get_or_fetch("trading212", "default", "positions", fetcher)
        return first, second

    first, second = asyncio.run(go())
    assert first.cache_status == "fresh"
    assert second.cache_status == "rate_limited"
    assert second.payload == ["good"], "must serve last-good payload on 429"
    assert "429" in (second.stale_reason or "")


@pytest.mark.unit
def test_rate_limit_remaining_zero_blocks_upstream_until_reset():
    cache = BrokerLiveCache()

    async def fetcher():
        return ["v1"], {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(time.time() + 5)}

    async def go():
        first = await cache.get_or_fetch("trading212", "default", "positions", fetcher)
        # Expire the cache; the rate-limit-remaining=0 gate should still
        # prevent another upstream fetch and serve the cached payload.
        cache._cache[("trading212", "default", "positions")].fetched_at = 0
        second = await cache.get_or_fetch("trading212", "default", "positions", fetcher)
        return first, second

    first, second = asyncio.run(go())
    assert first.cache_status == "fresh"
    assert second.cache_status == "rate_limited"
    assert second.payload == ["v1"]


@pytest.mark.unit
def test_x_ratelimit_headers_are_surfaced_to_callers():
    cache = BrokerLiveCache()

    async def fetcher():
        return [], {
            "x-ratelimit-limit": "60",
            "x-ratelimit-remaining": "59",
            "x-ratelimit-reset": "1735689600",
        }

    result = asyncio.run(cache.get_or_fetch("trading212", "default", "positions", fetcher))
    assert result.rate_limit == {
        "x-ratelimit-limit": "60",
        "x-ratelimit-remaining": "59",
        "x-ratelimit-reset": "1735689600",
    }


@pytest.mark.unit
def test_module_singleton_can_be_reset_for_isolation():
    a = live_cache_module.get_default_cache()
    live_cache_module.reset_default_cache_for_tests()
    b = live_cache_module.get_default_cache()
    assert a is not b


@pytest.mark.unit
def test_does_not_import_t212_write_endpoints_or_execution_objects():
    """Source-grep guard: the cache module must not import order_intent
    / order_draft / submit endpoints. Live truth is read-only."""
    import inspect
    import io
    import tokenize

    raw_src = inspect.getsource(live_cache_module)
    out: list[str] = []
    try:
        for tok in tokenize.tokenize(io.BytesIO(raw_src.encode("utf-8")).readline):
            if tok.type in (tokenize.COMMENT, tokenize.STRING, tokenize.ENCODING):
                continue
            out.append(tok.string)
            out.append(" ")
        src = "".join(out)
    except tokenize.TokenizeError:
        src = raw_src

    forbidden = [
        "submit_limit_order",
        "submit_market_order",
        "OrderIntent",
        "OrderDraft",
        "FEATURE_T212_LIVE_SUBMIT",
        "/equity/orders/limit",
        "/equity/orders/market",
    ]
    for needle in forbidden:
        assert needle not in src, f"broker_live_cache.py must not reference {needle}"
