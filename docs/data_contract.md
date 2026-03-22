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
- Split-adjusted: computed from raw + corporate_action splits
- Total-return-adjusted: further adjusted for dividends
- NEVER mix adjusted and unadjusted in the same table/view
- NEVER overwrite raw prices with adjusted values

### 4. PIT (Point-in-Time) rules
- `financial_period.reported_at` = when data became publicly available
- Research queries MUST filter: `reported_at <= asof_time`
- NEVER return future-knowledge data in research views
- Macro data uses `realtime_start`/`realtime_end` for vintage tracking

### 5. Corporate action timing
- Effective date for price adjustment = `ex_date`, NOT `pay_date`
- Split adjustment: `factor = split_to / split_from`
- Dividend adjustment: `factor = (P_prev - D) / P_prev`

### 6. FMP data handling
- FMP provides split-adjusted AND unadjusted data — they MUST be tracked separately
- Use explicit parameters, never trust defaults

### 7. Massive/Polygon data handling
- `adjusted` parameter MUST be explicitly set to `false` for raw prices
- NEVER rely on default adjustment behavior

### 8. Time zones
- ALL timestamps stored as UTC `timestamptz`
- Display layer may convert to exchange timezone
- Database storage is ALWAYS UTC

### 9. Vendor convenience fields
- NEVER treat vendor-provided "convenience" fields as auditable truth
- Always trace back to primary source data
- Cross-reference multiple sources when possible

### 10. Idempotent upserts
- All ingestion uses `ON CONFLICT DO NOTHING` or `ON CONFLICT DO UPDATE`
- Re-running an ingestion job MUST NOT create duplicates
