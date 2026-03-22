"""Trading 212 adapter — read-only account/position/order sync + demo skeleton.

Phase 1 boundary:
- Read-only: account summary, positions, historical orders
- order_intent / order_draft model support
- Demo skeleton with submit method that is DISABLED by default
- Live submit raises LiveSubmitDisabledError unless FEATURE_T212_LIVE_SUBMIT=true
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from libs.adapters.base import BaseAdapter
from libs.core.config import get_settings
from libs.core.exceptions import LiveSubmitDisabledError
from libs.core.logging import get_logger
from libs.core.rate_limit import RateLimiter

logger = get_logger(__name__)


@dataclass
class Trading212Adapter(BaseAdapter):
    _rate_limit: RateLimiter = field(default_factory=lambda: RateLimiter(max_requests=1, period_seconds=1.0))
    use_demo: bool = True

    @property
    def name(self) -> str:
        return "trading212"

    @property
    def auth_mode(self) -> str:
        return "api_key"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        settings = get_settings()
        return {
            "Authorization": settings.t212_api_key,
            "Content-Type": "application/json",
        }

    def _base_url(self) -> str:
        settings = get_settings()
        return settings.t212_demo_base_url if self.use_demo else settings.t212_live_base_url

    # ---- Read-only endpoints ----

    async def get_account_cash(self) -> dict:
        """Fetch account cash balance."""
        return await self.fetch_json("/equity/account/cash")

    async def get_account_info(self) -> dict:
        """Fetch account metadata."""
        return await self.fetch_json("/equity/account/info")

    async def get_positions(self) -> list[dict]:
        """Fetch open positions."""
        data = await self.fetch_json("/equity/portfolio")
        return data if isinstance(data, list) else []

    async def get_orders(self) -> list[dict]:
        """Fetch historical orders."""
        data = await self.fetch_json("/equity/history/orders")
        return data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    async def get_instruments(self) -> list[dict]:
        """Fetch tradeable instruments metadata."""
        data = await self.fetch_json("/equity/metadata/instruments")
        return data if isinstance(data, list) else []

    async def get_exchanges(self) -> list[dict]:
        """Fetch exchange metadata."""
        data = await self.fetch_json("/equity/metadata/exchanges")
        return data if isinstance(data, list) else []

    # ---- Order submission (Phase 1: skeleton) ----

    async def submit_limit_order(
        self,
        ticker: str,
        qty: float,
        limit_price: float,
        time_validity: str = "DAY",
    ) -> dict:
        """Submit a limit order. DISABLED by default for live accounts.

        This method exists for interface completeness but will raise
        LiveSubmitDisabledError unless the FEATURE_T212_LIVE_SUBMIT
        feature flag is explicitly enabled.
        """
        settings = get_settings()
        if not self.use_demo and not settings.feature_t212_live_submit:
            raise LiveSubmitDisabledError()

        logger.warning(
            "trading212.submit_order",
            ticker=ticker,
            qty=qty,
            limit_price=limit_price,
            is_demo=self.use_demo,
        )
        payload = {
            "ticker": ticker,
            "quantity": qty,
            "limitPrice": limit_price,
            "timeValidity": time_validity,
        }
        resp = await self.fetch("POST", "/equity/orders/limit", json=payload)
        return resp.json()

    async def submit_market_order(self, ticker: str, qty: float) -> dict:
        """Submit a market order. Same restrictions as limit_order."""
        settings = get_settings()
        if not self.use_demo and not settings.feature_t212_live_submit:
            raise LiveSubmitDisabledError()

        logger.warning("trading212.submit_market_order", ticker=ticker, qty=qty, is_demo=self.use_demo)
        payload = {"ticker": ticker, "quantity": qty}
        resp = await self.fetch("POST", "/equity/orders/market", json=payload)
        return resp.json()

    # ---- Normalize ----

    def normalize(self, raw: Any) -> Any:
        return raw

    def normalize_position(self, raw: dict) -> dict:
        """Normalize position data."""
        return {
            "broker_ticker": raw.get("ticker"),
            "quantity": raw.get("quantity", 0),
            "avg_cost": raw.get("averagePrice"),
            "current_price": raw.get("currentPrice"),
            "market_value": raw.get("currentPrice", 0) * raw.get("quantity", 0) if raw.get("currentPrice") and raw.get("quantity") else None,
            "pnl": raw.get("ppl"),
        }

    def normalize_order(self, raw: dict) -> dict:
        """Normalize historical order data."""
        return {
            "broker_order_id": str(raw.get("id", "")),
            "broker_ticker": raw.get("ticker"),
            "side": "buy" if raw.get("type", "").lower().startswith("buy") else "sell",
            "order_type": raw.get("type", "unknown"),
            "qty": raw.get("filledQuantity", raw.get("quantity", 0)),
            "filled_qty": raw.get("filledQuantity"),
            "avg_fill_price": raw.get("fillPrice"),
            "status": raw.get("status", "unknown"),
        }
