# Data Contract

## Iron Rules

### 1. Ticker is NOT a join key
- `instrument_id` (UUID) is the ONLY valid join key across all tables
- Tickers change, merge, split. instrument_id is permanent.

### 2. Raw payload preservation
- ALL ingested data MUST retain `raw_payload` (JSONB) with the original API response
- ALL ingested data MUST retain `source` (which adapter/API)
- ALL ingested data MUST retain `ingested_at` (timestamptz)

### 3. Price layer separation
- `price_bar_raw`: ONLY raw unadjusted prices from source
- Split-adjusted: computed from raw + corporate_action splits (via `get_split_adjusted_prices`)
- Total-return-adjusted: further adjusted for dividends (via `get_total_return_adjusted_prices`)
- NEVER mix adjusted and unadjusted in the same table/view
- NEVER overwrite raw prices with adjusted values

#### Verified Example: NVDA 10:1 Split (June 10, 2024)
```
Pre-split raw close: ~$1200 (June 7)
Post-split raw close: ~$121 (June 10)
adj_factor for pre-split bars: 10.0
Split-adjusted pre-split close: ~$120 (continuous with post-split)
```

### 4. PIT (Point-in-Time) rules
- `financial_period.reported_at` = when data became publicly available
- Research queries MUST filter: `reported_at <= asof_date`
- NEVER return future-knowledge data in research views
- SEC companyfacts uses `filed` date as reported_at
- All research and factor functions require an explicit `asof_date` parameter -- there is no default that uses "today"

### 5. Corporate action timing
- Effective date for price adjustment = `ex_date`, NOT `pay_date`
- Split adjustment: `factor = split_to / split_from`
- Dividend adjustment: `factor = (P_prev - D) / P_prev`

### 6. asof_date enforcement
- Every research function, factor computation, screener, and event study requires an explicit `asof_date` parameter
- This prevents look-ahead bias in both research and backtesting
- Strategy interfaces (UniverseProvider, SignalProvider) also require `asof_date`
- There is no implicit "use today's date" default -- callers must be explicit

### 7. FMP data handling
- FMP provides split-adjusted AND unadjusted data -- they MUST be tracked separately
- Use explicit parameters, never trust defaults
- Note: FMP adapter is currently a skeleton (no API key configured)

### 8. Massive/Polygon data handling
- `adjusted` parameter MUST be explicitly set to `false` for raw prices
- NEVER rely on default adjustment behavior
- Note: Massive/Polygon adapter is currently a skeleton (no API key configured)

### 9. Time zones
- ALL timestamps stored as UTC `timestamptz`
- Display layer may convert to exchange timezone
- Database storage is ALWAYS UTC

### 10. Dev data source tagging
- Dev-only data loaded via yfinance is tagged `source='yfinance_dev'`
- Production sources use their own source tags (e.g., `sec`, `massive`, `fmp`)
- Source provenance enables easy identification and replacement
- **Current state**: prices, corporate actions, and earnings are ALL yfinance_dev. This is a known blocker requiring Massive/Polygon and FMP API keys to resolve.

### 11. Idempotent upserts
- All ingestion uses `ON CONFLICT DO NOTHING` or `ON CONFLICT DO UPDATE`
- Re-running an ingestion job MUST NOT create duplicates

### 12. Backtest data integrity
- Backtest engine reads only from the database (no external fetches during simulation)
- Backtest results (runs and trades) are persisted to `backtest_run` and `backtest_trade` tables
- NAV series stored as JSONB on the run record
- All trades carry instrument_id, date, side, quantity, price, and cost breakdown
