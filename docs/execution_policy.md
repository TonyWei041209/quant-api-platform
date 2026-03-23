# Execution Policy

## Current State (v1)

### What IS implemented:
- Order intent creation (from strategy or manual)
- Order draft generation (from intent, with broker/order type/qty/price)
- Human approval workflow (approve or reject)
- 7 pre-submit risk checks
- Draft expiry for stale pending orders
- Structured audit logging on all execution actions
- Broker router with Trading 212 adapter (skeleton -- no API key configured)
- API endpoints for full lifecycle management

### What is NOT implemented:
- Automatic live order submission (disabled by design)
- Real-time position management
- Automatic rebalancing
- Stop-loss automation
- Multi-broker routing
- Execution quality monitoring

## Execution Flow

```
Strategy Signal / Manual Input
    |
    v
order_intent (created via API or strategy code)
    |
    v
order_draft (generated from intent, with broker, order type, qty, price)
    |
    v
Human Approval (draft.approved_at must be set, status = "approved")
    |
    v
Risk Checks (7 pre-submit validations -- all must pass)
    |
    v
Broker Submit (ONLY via broker_router, ONLY if live enabled)
```

## Risk Checks (7 Rules)

All checks run BEFORE order submission. Any single failure blocks the submit.

| Rule | Check | Blocks If |
|------|-------|-----------|
| positive_qty | Quantity must be > 0 | qty <= 0 |
| limit_price_required | Limit orders need limit_price, stop orders need stop_price | Missing price on limit/stop order |
| max_position_size | Single order qty <= 10,000 (configurable) | qty > max |
| max_notional | Order value <= $1,000,000 (configurable) | notional > max |
| duplicate_order | No other pending/approved/submitted draft for same intent | Duplicate found |
| stale_intent | Intent must be < 24 hours old (configurable) | Intent too old |
| trading_day | Today must be a trading day per exchange_calendar | Market closed |

## Safety Controls

1. **Strategy code MUST NOT call broker APIs directly** -- all order submission goes through the intent -> draft -> approval -> submit pipeline.

2. **Live submit is disabled by default** -- `FEATURE_T212_LIVE_SUBMIT=false` in environment. The `submit_limit_order` and `submit_market_order` methods raise `LiveSubmitDisabledError` for live accounts unless this flag is true.

3. **All drafts require human approval** -- `order_draft.approved_at` must be non-null and `status` must be "approved" before submission.

4. **Dual flag system** -- Even if the feature flag allows live submit, each draft has its own `is_live_enabled` boolean (default `false`). Both must be true for live submission.

5. **Stale expiry** -- Pending drafts older than 48 hours can be expired via API or CLI to prevent accumulation of forgotten orders.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/execution/intents` | List intents (filter by status) |
| POST | `/execution/intents` | Create new intent |
| GET | `/execution/drafts` | List drafts (filter by status) |
| POST | `/execution/drafts/from-intent/{id}` | Create draft from intent |
| POST | `/execution/drafts/{id}/approve` | Approve a draft |
| POST | `/execution/drafts/{id}/reject` | Reject a draft |
| GET | `/execution/drafts/{id}/risk-check` | Run risk checks (dry run, no submit) |
| POST | `/execution/drafts/expire-stale` | Expire stale pending drafts |

## Why No Auto-Live in v1

- Trading 212 API has idempotency concerns
- Trading 212 ToS prohibits algorithmic trading
- Risk management framework is not mature enough
- Proper position sizing algorithms not implemented
- No execution quality monitoring yet
- No Trading 212 API key currently configured
- Comprehensive safeguards needed before any live trading
