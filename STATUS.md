# Status

## Last Updated: 2026-03-26 (v1.5.0 — Production Release — All Phases Complete)

### Overall Completion: 100% (v1.5.0 Production Release)

The platform has reached its first production release. All phases (1 through 8) are complete. FMP is the production primary source for EOD prices and financials. SEC EDGAR is the truth source for filings and companyfacts. Polygon provides corporate actions. Trading 212 readonly integration is verified. 160 tests passing.

---

### What's Complete

- **Data Layer**: 25-table PostgreSQL schema with UUID PKs and timestamptz. Security Master with identifier and ticker history. Exchange calendar (NYSE/NASDAQ, 2020-2026). Raw unadjusted EOD prices (source-tagged, raw_payload preserved). Corporate actions from Polygon. SEC filings and companyfacts. Source run tracking and data issue persistence.
- **Research Layer**: 9 factor primitives, 4 screeners, earnings event study, PIT-safe financial views, split-adjusted and total-return-adjusted prices. All functions require explicit `asof_date`.
- **Backtest Layer**: Bar-by-bar simulation engine with cost model, portfolio construction, walk-forward/expanding time splits. Persistent runs with metrics, trades, NAV series. Queryable via API.
- **Execution Layer**: Signal → Intent → Draft → Approval → Submit pipeline. 7 risk checks. Approval gate cannot be bypassed. Trading 212 readonly verified. Live submit disabled by default (`FEATURE_T212_LIVE_SUBMIT=false`).
- **Daily Workflow**: Daily Research Home dashboard, watchlist groups, saved presets, research notes, recent activity feed, continue-where-you-left-off flow.
- **Observability**: 11 DQ rules, source run tracking, data issue persistence, CLI status and reporting commands.
- **Frontend**: React 18 + Vite + Tailwind CSS. 7 pages. Bilingual (EN/中文). Dark mode. Responsive layout.
- **API & CLI**: 25+ REST endpoints, 15+ CLI commands, FastAPI with OpenAPI docs.

---

### Data Source Status

| Source | Role | Status |
|--------|------|--------|
| FMP (Financial Modeling Prep) | Primary: EOD prices, financials, profiles | **Production** |
| SEC EDGAR | Truth: filings, companyfacts, PIT validation | **Production** |
| Polygon / Massive | Primary: corporate actions; Secondary: raw price validation | **Production** |
| OpenFIGI | Identifier enrichment (FIGI mapping) | **Production** |
| Trading 212 | Broker: readonly account/positions/orders | **Verified (Basic Auth)** |
| BEA / BLS / Treasury | Macro data skeletons | Phase 2 |

---

### Database Summary (25 Tables)

| Table | Source |
|-------|--------|
| instrument | SEC |
| instrument_identifier | SEC + OpenFIGI |
| ticker_history | SEC |
| exchange_calendar | Internal (NYSE/NASDAQ) |
| price_bar_raw | FMP (production) |
| corporate_action | Polygon (production) |
| earnings_event | FMP (production) |
| filing | SEC EDGAR |
| financial_period | SEC companyfacts |
| financial_fact_std | SEC companyfacts |
| macro_series | Skeleton (Phase 2) |
| macro_observation | Skeleton (Phase 2) |
| source_run | Internal tracking |
| data_issue | DQ engine |
| order_intent | Execution layer |
| order_draft | Execution layer |
| broker_account_snapshot | Trading 212 |
| broker_position_snapshot | Trading 212 |
| broker_order_snapshot | Trading 212 |
| backtest_run | Backtest engine |
| backtest_trade | Backtest engine |
| watchlist_group | Daily research |
| watchlist_item | Daily research |
| saved_preset | Daily research |
| research_note | Daily research |

### Test Suite
- **160 tests passing** (unit, integration, smoke, API, DQ, PIT, backtest, execution)

---

### What Works Without Any External API Keys

1. Full database schema setup and migrations
2. API server and all endpoints
3. Frontend (all 7 pages)
4. Exchange calendar generation (NYSE/NASDAQ, 2020-2026)
5. SEC filings and fundamentals ingestion (no key needed)
6. All 11 DQ rules and reporting
7. All research factor primitives and screeners
8. Full backtest engine with persistence (on existing data)
9. Complete execution pipeline (intent/draft/approval flow)
10. All CLI commands (with graceful degradation)
11. Watchlists, presets, notes, recent activity

### What Requires External API Keys

| Feature | Key Required | Environment Variable |
|---------|-------------|---------------------|
| Production EOD prices | FMP API key | `FMP_API_KEY` |
| Production financials | FMP API key | `FMP_API_KEY` |
| Corporate actions (splits/dividends) | Polygon API key | `MASSIVE_API_KEY` |
| Higher-rate identifier enrichment | OpenFIGI API key | `OPENFIGI_API_KEY` |
| Broker readonly data | Trading 212 API key | `T212_API_KEY` |
| Live order submission | Trading 212 API key + feature flag | `T212_API_KEY` + `FEATURE_T212_LIVE_SUBMIT=true` |
| Macro data (GDP, CPI, employment) | BEA/BLS API keys | `BEA_API_KEY`, `BLS_API_KEY` |
