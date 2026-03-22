# Project Summary

## quant-api-platform

API-first quantitative stock analysis, research, and controlled execution platform for US equities.

## Current State: Phase 3B Complete

### Platform Capabilities
1. **Data Layer**: 19-table PostgreSQL schema, SEC/OpenFIGI/yfinance integration, exchange calendar
2. **Research Layer**: Factor primitives, stock screeners, PIT-safe financial views, event studies
3. **Execution Layer**: Intent→draft→approval→submit pipeline, 7 risk checks, T212 adapter (read-only)
4. **Backtest Layer**: Vectorized engine, cost model, portfolio construction, walk-forward splits
5. **DQ Layer**: 10 rules, automated issue tracking
6. **Observability**: CLI status/report commands, structured logging, source run tracking

### Key Metrics
- 93 tests passing (34 unit + 5 smoke + 54 integration)
- 4 real instruments with complete data (AAPL, MSFT, NVDA, SPY)
- 10 DQ rules, 0 unresolved issues
- 12+ research API endpoints
- Live order submission disabled by default (FEATURE_T212_LIVE_SUBMIT=false)
