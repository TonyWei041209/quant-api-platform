# Architecture

## Overview

The platform follows a 6-layer architecture:

```
┌─────────────────────────────────┐
│         API / CLI Layer         │  FastAPI + Typer
├─────────────────────────────────┤
│        Execution Layer          │  Intents → Drafts → Approval → Submit
├─────────────────────────────────┤
│         Research Layer          │  PIT Views, Adjusted Prices, Event Studies
├─────────────────────────────────┤
│           DQ Layer              │  Rules, Validation, Issue Tracking
├─────────────────────────────────┤
│      Ingestion Layer            │  Jobs, Adapters, Normalization
├─────────────────────────────────┤
│        Data Layer               │  PostgreSQL, SQLAlchemy, Alembic
└─────────────────────────────────┘
```

## Data Flow

```
External APIs → Adapters → Normalization → Upsert → Raw Tables
                                                         ↓
                                                    DQ Checks → data_issue
                                                         ↓
                                              Research Views (PIT-safe)
                                                         ↓
                                              Signal → Intent → Draft → Approval → Broker
```

## Key Design Decisions

1. **instrument_id as universal join key**: Tickers change. CIKs are SEC-specific. FIGIs may not exist for all securities. UUID instrument_id is stable across all these changes.

2. **Raw + Adjusted price separation**: `price_bar_raw` stores ONLY unadjusted prices. Adjusted prices are computed views derived from raw + corporate_action.

3. **PIT enforcement**: `financial_period.reported_at` is the timestamp when data became public. All research queries MUST filter by `reported_at <= asof_time`.

4. **Execution isolation**: Strategy code outputs `order_intent`. It NEVER calls broker APIs directly. The flow is: intent → draft → human approval → risk check → broker submit.

5. **Source provenance**: Every fact carries `source`, `ingested_at`, and `raw_payload`. This enables auditing, debugging, and replay.
