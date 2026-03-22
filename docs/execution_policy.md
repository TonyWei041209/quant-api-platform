# Execution Policy

## Phase 1 Boundary

### What IS implemented:
- Order intent creation (research layer output)
- Order draft generation (from intent)
- Human approval workflow
- Basic risk checks
- Broker router skeleton (Trading 212)
- Demo adapter skeleton

### What is NOT implemented:
- Automatic live order submission
- Real-time position management
- Automatic rebalancing
- Stop-loss automation

## Execution Flow

```
Strategy Signal
    ↓
order_intent (created by research/strategy code)
    ↓
order_draft (generated, NOT submitted)
    ↓
Human Approval (draft.approved_at must be set)
    ↓
Risk Checks (pre-submit validation)
    ↓
Broker Submit (ONLY via broker_router)
```

## Critical Rules

1. **Strategy code MUST NOT call broker APIs directly** — all order submission goes through intent → draft → approval → submit pipeline

2. **Live submit is disabled by default** — `FEATURE_T212_LIVE_SUBMIT=false` in environment. The `submit_limit_order` and `submit_market_order` methods raise `LiveSubmitDisabledError` for live accounts unless this flag is true.

3. **All drafts require human approval** — `order_draft.approved_at` must be non-null and `status` must be "approved" before submission

4. **Demo before live** — Always test with demo adapter first. Demo orders go to Trading 212 demo environment.

5. **is_live_enabled flag** — Each draft has an `is_live_enabled` boolean. Default is `false`. Even if the feature flag allows live submit, the draft itself must have this flag set.

## Why no auto-live in Phase 1?
- Trading 212 API has idempotency concerns
- Trading 212 ToS prohibits algorithmic trading
- Risk management framework is not mature enough
- Proper position sizing algorithms not implemented
- No execution quality monitoring yet
