# Architecture

## Overview

The platform follows a 7-layer architecture:

```
+------------------------------------------+
|            API / CLI Layer               |  FastAPI + Typer
+------------------------------------------+
|          Backtest / Strategy Layer        |  Engine, Persistence, Strategy Interfaces
+------------------------------------------+
|           Execution Layer                |  Intents -> Drafts -> Approval -> Submit
+------------------------------------------+
|            Research Layer                 |  PIT Views, Adjusted Prices, Factors, Screeners, Event Studies
+------------------------------------------+
|              DQ Layer                    |  11 Rules, Validation, Issue Tracking
+------------------------------------------+
|          Ingestion Layer                 |  Jobs, Adapters, Normalization
+------------------------------------------+
|            Data Layer                    |  PostgreSQL 16, SQLAlchemy, Alembic (21 tables)
+------------------------------------------+
```

## Data Flow

```
External APIs -> Adapters -> Normalization -> Upsert -> Raw Tables (21 tables)
                                                             |
                                                        DQ Checks -> data_issue
                                                             |
                                                   Research Views (PIT-safe, asof_date required)
                                                             |
                                              +-----------------------------+
                                              |                             |
                                       Backtest Engine              Execution Pipeline
                                       (simulation)                (intent -> draft ->
                                              |                     approval -> broker)
                                       backtest_run +
                                       backtest_trade
```

## Layer Details

### Data Layer (21 Tables)
- **Core**: instrument, instrument_identifier, ticker_history
- **Market Data**: price_bar_raw, corporate_action, earnings_event, exchange_calendar
- **Fundamentals**: filing, financial_period, financial_fact_std
- **Macro**: macro_series, macro_observation (skeleton -- no data loaded)
- **Execution**: order_intent, order_draft
- **Broker**: broker_account_snapshot, broker_position_snapshot, broker_order_snapshot
- **Backtest**: backtest_run, backtest_trade
- **Infrastructure**: source_run, data_issue

### Ingestion Layer
- **Adapters**: SEC EDGAR (production), OpenFIGI (production), Massive/Polygon (skeleton), FMP (skeleton), BEA (skeleton), BLS (skeleton), Treasury (skeleton), Trading 212 (skeleton)
- **Dev loader**: yfinance for prices/splits/dividends/earnings (tagged `source='yfinance_dev'`, NOT production)
- **Source tracking**: Every ingestion run logged in `source_run` with counters and status

### DQ Layer
- 11 rules covering price logic, duplicates, PIT integrity, cross-source divergence, stale data, identifier consistency, and raw/adjusted contamination
- Issues written to `data_issue` table with rule code, severity, and JSONB details
- CLI commands: `run-dq`, `dq-report`, `status`

### Research Layer
- **Factor primitives**: daily_returns, rolling_volatility, cumulative_return, drawdown, relative_strength, momentum, valuation_snapshot, performance_summary
- **Screeners**: by liquidity, returns, fundamentals, composite rank
- **Event studies**: per-instrument and grouped summaries
- **PIT views**: financial data filtered by `reported_at <= asof_date`
- **Adjusted prices**: split-adjusted and total-return-adjusted computed from raw + corporate_action
- **All functions require explicit `asof_date`** to prevent look-ahead bias

### Execution Layer
- **Flow**: Strategy signal -> order_intent -> order_draft -> human approval -> risk check (7 rules) -> broker submit
- **Safety**: Live submission disabled by default (`FEATURE_T212_LIVE_SUBMIT=false`), each draft has `is_live_enabled` flag
- **Lifecycle**: Drafts can be approved, rejected, or expired (stale expiry)
- **Broker**: Trading 212 adapter exists (skeleton, no API key configured)

### Backtest / Strategy Layer
- **Engine**: Bar-by-bar vectorized simulation reading from DB-backed prices
- **Cost model (realistic)**: Five components — commission_per_share, slippage_bps, spread_bps, fx_fee_bps (conditional on `instrument.currency != base_currency`), volume_impact_bps (conditional on participation > threshold). Each component recorded per-trade; aggregated in `metrics.cost_breakdown`. Backward-compatible defaults preserve legacy 5bps-slippage behavior.
- **Strategy Honesty Report** (`POST /backtest/honesty-report`): Runs the same backtest twice (legacy 5bps vs realistic full-friction), returns side-by-side metrics + gap (return_pp, retention_pct, cost_multiplier, annual_cost_drag_bps) + verdict (honest / degraded / illusion). Not persisted — diagnostic only. Used to catch curve-fit strategies before committing to them.
- **Portfolio construction**: Equal weight with max position cap, configurable rebalance frequency
- **Time splits**: Simple split, walk-forward, expanding window
- **Strategy interfaces**: UniverseProvider, SignalProvider, PortfolioConstructor, RiskOverlay (abstract base classes)
- **Concrete strategies**: MomentumSignalProvider, EqualWeightConstructor, MaxPositionRiskOverlay, AllActiveUniverse
- **Persistence**: Results stored in backtest_run and backtest_trade tables

### Watchlist Quant Snapshot (Layer 1 — Research-open)
- **Endpoint**: `GET /watchlist/snapshots?instrument_ids=id1,id2,...`
- Batch returns: 1D/5D/1M price change %, 52-week range position (0%=low, 100%=high), research freshness
- Data sources: `price_bar_raw` (raw close, EOD daily) + `research_note.updated_at`
- Frontend: Dashboard watchlist items show snapshot strip with smart freshness labels (Today / Yesterday / Nd ago / No research)
- Fallback: returns `null` for missing data (e.g., <22 trading days → 1M null; <365 days → 52W null)
- No execution impact, no ranking, no auto-scoring

### API / CLI Layer
- **FastAPI**: Health, instruments, research (14 endpoints), execution (8 endpoints), backtest (5 endpoints), watchlist snapshots
- **Typer CLI**: 13 commands for ingestion, DQ, status, and backtesting

## Key Design Decisions

1. **instrument_id as universal join key**: Tickers change. CIKs are SEC-specific. FIGIs may not exist for all securities. UUID instrument_id is stable across all these changes.

2. **Raw + Adjusted price separation**: `price_bar_raw` stores ONLY unadjusted prices. Adjusted prices are computed views derived from raw + corporate_action. Never mix adjusted and unadjusted in the same table.

3. **PIT enforcement**: `financial_period.reported_at` is the timestamp when data became public. All research queries MUST filter by `reported_at <= asof_date`. All research and strategy functions require an explicit `asof_date` parameter.

4. **Execution isolation**: Strategy code outputs `order_intent`. It NEVER calls broker APIs directly. The flow is: intent -> draft -> human approval -> risk check -> broker submit. Live submission is disabled by default.

5. **Source provenance**: Every fact carries `source`, `ingested_at`, and `raw_payload`. This enables auditing, debugging, and replay. Dev data is clearly tagged `source='yfinance_dev'`.

6. **Backtest purity**: The backtest engine reads only from the database. It does not fetch external data. Strategies use the same research layer functions as live analysis, ensuring consistency.

7. **Strategy abstraction**: Strategy interfaces (UniverseProvider, SignalProvider, PortfolioConstructor, RiskOverlay) separate concerns and can be composed independently. The same interfaces work for backtest and eventual live execution.
