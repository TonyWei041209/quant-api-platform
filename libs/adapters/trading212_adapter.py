"""Trading 212 adapter — read-only account/position/order sync + controlled submit.

Uses HTTP Basic Authentication (base64(API_KEY:API_SECRET)) per T212 v0 API docs.
Only for Invest and Stocks ISA account types.

Boundary:
- Read-only: account summary, positions, historical orders, instruments, exchanges
- Controlled submit: disabled by default via FEATURE_T212_LIVE_SUBMIT=false
- Live submit raises LiveSubmitDisabledError unless explicitly enabled
"""
from __future__ import annotations

import base64
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
    use_demo: bool = False  # default to live since user has live key

    @property
    def name(self) -> str:
        return "trading212"

    @property
    def auth_mode(self) -> str:
        return "basic"

    def rate_limiter(self) -> RateLimiter:
        return self._rate_limit

    def _build_headers(self) -> dict[str, str]:
        settings = get_settings()
        creds = f"{settings.t212_api_key}:{settings.t212_api_secret}"
        encoded = base64.b64encode(creds.encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }

    def _base_url(self) -> str:
        settings = get_settings()
        return settings.t212_demo_base_url if self.use_demo else settings.t212_live_base_url

    # ---- Read-only endpoints ----

    async def get_account_summary(self) -> dict:
        """Fetch account summary (id, currency, totalValue, cash, investments)."""
        return await self.fetch_json("/equity/account/summary")

    async def get_positions(self) -> list[dict]:
        """Fetch open positions."""
        data = await self.fetch_json("/equity/positions")
        return data if isinstance(data, list) else []

    async def get_orders(self, limit: int = 50) -> list[dict]:
        """Fetch historical orders with pagination."""
        data = await self.fetch_json("/equity/history/orders", params={"limit": limit})
        return data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    async def get_instruments(self) -> list[dict]:
        """Fetch tradeable instruments metadata."""
        data = await self.fetch_json("/equity/metadata/instruments")
        return data if isinstance(data, list) else []

    async def get_exchanges(self) -> list[dict]:
        """Fetch exchange metadata."""
        data = await self.fetch_json("/equity/metadata/exchanges")
        return data if isinstance(data, list) else []

    async def get_dividends(self, limit: int = 50) -> list[dict]:
        """Fetch dividend history."""
        data = await self.fetch_json("/equity/history/dividends", params={"limit": limit})
        return data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []

    async def get_transactions(self, limit: int = 50) -> list[dict]:
        """Fetch transaction history."""
        data = await self.fetch_json("/equity/history/transactions", params={"limit": limit})
        return data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []

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
        """Normalize position from T212 v0 API response format.

        Real response has nested {instrument: {ticker, name, isin, currency}, walletImpact: {...}}.
        """
        inst = raw.get("instrument", {})
        wallet = raw.get("walletImpact", {})
        return {
            "broker_ticker": inst.get("ticker"),
            "instrument_name": inst.get("name"),
            "isin": inst.get("isin"),
            "instrument_currency": inst.get("currency"),
            "account_currency": wallet.get("currency"),
            "quantity": raw.get("quantity", 0),
            "quantity_available": raw.get("quantityAvailableForTrading", 0),
            "avg_cost": raw.get("averagePricePaid"),
            "current_price": raw.get("currentPrice"),
            "total_cost": wallet.get("totalCost"),
            "current_value": wallet.get("currentValue"),
            "pnl": wallet.get("unrealizedProfitLoss"),
            "fx_impact": wallet.get("fxImpact"),
            "created_at": raw.get("createdAt"),
        }

    def normalize_order(self, raw: dict) -> dict:
        """Normalize historical order from T212 v0 API response format.

        Real response is {order: {...}, fill: {...}} nested structure.
        """
        order = raw.get("order", raw)
        fill = raw.get("fill", {})
        inst = order.get("instrument", {})
        wallet = fill.get("walletImpact", {})
        return {
            "broker_order_id": str(order.get("id", "")),
            "broker_ticker": inst.get("ticker") or order.get("ticker"),
            "instrument_name": inst.get("name"),
            "isin": inst.get("isin"),
            "side": order.get("side", "BUY").lower(),
            "order_type": order.get("type", "unknown"),
            "strategy": order.get("strategy"),
            "qty": abs(fill.get("quantity", order.get("filledQuantity", order.get("quantity", 0)) or 0)),
            "filled_qty": fill.get("quantity"),
            "fill_price": fill.get("price"),
            "net_value": wallet.get("netValue"),
            "realized_pnl": wallet.get("realisedProfitLoss"),
            "fx_rate": wallet.get("fxRate"),
            "status": order.get("status", "unknown"),
            "created_at": order.get("createdAt"),
            "filled_at": fill.get("filledAt"),
            "account_currency": wallet.get("currency") or order.get("currency"),
        }
