# Mirror Universe Mapping + Market Events & News Center

Status: implemented (commit pending). No production deploy in this phase.

This doc covers two related capabilities introduced in Phase M:

1. **Auto Instrument Mapping** — turn Trading 212 Mirror tickers (held +
   recently traded + manually watched) into platform instrument rows so
   they can participate in the full research/backtest pipeline.
2. **Market Events & News Center** — a composed read-only feed of
   upcoming earnings + recent news, scoped to the user's Mirror, the
   Scanner Universe, an all-market earnings calendar (paginated), or
   one specific ticker.

---

## 1. Why "Unmapped" exists

Trading 212's positions/orders APIs return broker-side tickers like
`MU_US_EQ`, `NOK_US_EQ`, `RKLB_US_EQ`. The Mirror normalizes these to a
display ticker (`MU`, `NOK`, `RKLB`) and tries to resolve each one to an
internal `instrument_id` via `instrument_identifier(id_type='ticker')`
or `ticker_history.ticker`. The platform's instrument master currently
contains only the 36-ticker Scanner Research Universe (plus the four
protected tickers `NVDA / AAPL / MSFT / SPY`). Anything outside that
list — most of the user's day-trading flow — comes back unresolved.

`Unmapped` is a deliberate label: the Mirror still shows the ticker so
the user can see their full activity, but flags it so the UI knows the
research/backtest pipeline can't follow through to instrument-keyed data.

## 2. Mapping states

| State | Meaning | What the UI shows |
|---|---|---|
| `mapped` | ticker resolves to an existing `instrument_id` | full Research / Backtest paths work |
| `unmapped` | not in the master, no provider lookup attempted (`fetch_profiles=False`) | gray "Unmapped" badge; "Check mapping" button on Dashboard |
| `newly_resolvable` | not in the master, but FMP profile returned enough fields to bootstrap | blue badge; eligible for the future bootstrap CLI |
| `unresolved` | not in the master, FMP returned nothing | amber badge; "provider could not resolve" note |
| `ambiguous` | reserved (multiple plausible provider matches) | treated as `unresolved` in this phase to prevent wrong-issuer rows |

## 3. Tables a future production bootstrap would write

Exactly three tables, mirroring the Scanner Research Universe bootstrap:

- `instrument` — one row per scaffolded ticker
- `instrument_identifier` — `(instrument_id, id_type='ticker', id_value=<TICKER>, source='bootstrap_prod', valid_from=2020-01-01)`
- `ticker_history` — `(instrument_id, ticker, effective_from=2020-01-01, source='bootstrap_prod')`

> **Source-label note (corrected 2026-05-12).** The
> `execute_bootstrap` function reused from the Scanner Research-36
> universe writes a single shared `source='bootstrap_prod'` label.
> Identifying mirror-bootstrap rows therefore requires
> `source='bootstrap_prod' AND id_value/ticker ∈ allowlist`
> (not a dedicated source label, as an earlier draft of this doc
> implied).

Tables NEVER touched by the bootstrap or its planner:

- `price_bar_raw` (handled by `sync_eod_prices_universe`)
- `corporate_action`, `earnings_event`, `financial_*`
- `watchlist_*`
- `broker_*` (held by the `quant-sync-t212` cron)
- `order_intent`, `order_draft`

The actual write path is delegated to
`libs/ingestion/bootstrap_research_universe_prod.py` — same four-flag
handshake, same FMP fallback rules, same per-ticker isolation.

### Future production execution plan (not executed in this phase)

1. Cloud SQL backup
2. Build image pinned to commit
3. Run `python -m apps.cli.main bootstrap-mirror-instruments --dry-run --fetch-profiles` via a one-shot Cloud Run job
4. Inspect plan output; verify `newly_resolvable` count and that protected tickers are excluded
5. Re-run with `--no-dry-run --write --db-target=production --confirm-production-write`
6. Verify counts via `apps.cli.main status`
7. Cleanup transient job
8. Rollback path: row-level DELETE on rows whose `source='bootstrap_prod' AND id_value/ticker ∈ allowlist` — see `docs/mirror-bootstrap-allowlist-report.md §6` for the canonical SQL (allowlist filter is mandatory because the label is shared with the scanner-universe seed)

## 4. Provider choices

**Primary: FMP (Financial Modeling Prep)** — already configured
(`FMP_API_KEY` bound to the `quant-api` Cloud Run service revision
`quant-api-00038-ppm`). Used for:

- `/stable/profile` — company profile (already used by the existing
  scanner bootstrap; reused here for unmapped-ticker resolution)
- `/stable/earning-calendar` — earnings calendar
- `/stable/news/stock` — per-ticker news (paid-tier on some FMP plans;
  the provider layer detects 404 / "subscription" hints and returns
  `provider_status="unavailable"` rather than throwing 500)

**Optional secondary: Massive (Polygon)** — has no news/earnings
methods today (`get_eod_bars` / `get_splits` / `get_dividends` only).
Not used for events/news in this phase; left as a future addition if
Polygon access changes.

**No new paid providers added.** No scraping. No browser automation.
No private/unofficial endpoints. No login credential storage.

## 5. Cache TTLs (in-memory, per-process)

| Endpoint | TTL | Reason |
|---|---|---|
| earnings calendar | 6 hours | calendar updates daily on FMP, 6h is fresh enough for the Dashboard |
| stock news | 15 min | conservative; news refresh rarely needs sub-15m granularity |
| company profile | 24 hours | profile is near-static; one provider call per ticker per day |

The cache uses single-flight: concurrent fetches for the same key share
one in-flight task so multiple dashboard tabs / page renders never
multiply provider calls.

Cache invalidation is process-restart-only in this phase (no admin
endpoint). Acceptable because revisions are immutable in Cloud Run and
each deploy starts fresh.

## 6. API scopes

| Scope | Tickers | Earnings call | News call |
|---|---|---|---|
| `mirror` | held + recently traded + manually watched | filter to mirror tickers | per-ticker |
| `scanner` | `SCANNER_RESEARCH_UNIVERSE` (36) | filter to scanner tickers | per-ticker |
| `all_supported` | none — provider-wide | unfiltered, capped by `limit` | **explicitly omitted** |
| `ticker` | one ticker (required query param) | filter to one ticker | per-ticker |

`all_supported` deliberately omits news to respect provider quotas and
avoid an unbounded news blast. The UI displays a clear note explaining
this is intentional.

`limit` is bounded between 50 and 500 for the all-market earnings
endpoint. Per-ticker news is capped at 25 per ticker.

## 7. API surface

All endpoints require auth and are read-only:

- `GET /api/instruments/mirror-mapping/plan?fetch_profiles=false&include_recent_orders=true&lookback_days=7&manual=A,B,C`
- `GET /api/market-events/feed?scope=mirror&days=7&limit=100&limit_per_ticker=5`
- `GET /api/market-events/earnings?scope=mirror&days=7&limit=100`
- `GET /api/market-events/news?scope=mirror&days=7&limit_per_ticker=5`
- `GET /api/market-events/ticker/{ticker}?days=30`

Unauth → 401, never 500. Provider unavailable → 200 with
`provider_status="unavailable"` and empty data, never 500.

## 8. Research-only guardrails

- `extra="forbid"` is not used on these response models because the
  legacy daily.py / portfolio.py routers also use plain `dict` returns;
  matching that convention keeps the codebase coherent. The
  source-grep tests instead pin the absence of trading-action language.
- `disclaimer` field on every events response: *"Research events only.
  Earnings and news are informational and require independent
  validation."*
- No `buy_signal` / `sell_signal` / `target_price` / `position_size` /
  `entry` / `urgency` / `action` / `certainty` fields anywhere in
  request or response models.
- Pinned by `tests/unit/test_no_trading_writes.py` (extended) and
  `tests/unit/test_mirror_instrument_mapper.py` /
  `tests/unit/test_market_events.py` source-grep guards.

## 9. CLI

```bash
# Plan only (default; no provider HTTP calls)
python -m apps.cli.main bootstrap-mirror-instruments --dry-run

# Plan with FMP profile preview (read-only, one HTTP call per unmapped ticker)
python -m apps.cli.main bootstrap-mirror-instruments --dry-run --fetch-profiles

# Local DB write (refuses unless DATABASE_URL points at localhost)
python -m apps.cli.main bootstrap-mirror-instruments \
    --no-dry-run --write --db-target=local

# Production write (the four-flag handshake; refuses without
# DB_TARGET_OVERRIDE=production OR a Cloud SQL URL)
python -m apps.cli.main bootstrap-mirror-instruments \
    --no-dry-run --write \
    --db-target=production \
    --confirm-production-write
```

## 10. Frontend

- New top-level page `Market Events` in the sidebar between Scanner and
  Research. Tabs: **Mirror / Scanner Universe / All Market Earnings /
  Ticker Search**. Click any earnings or news row → ticker detail
  drawer with mapping status, profile, upcoming earnings, recent news.
- Dashboard "Upcoming Events" card is now clickable → navigates to the
  Market Events page.
- Dashboard Trading 212 Mirror card: each unmapped item shows a
  **"Check mapping"** button that opens a drawer calling
  `/api/instruments/mirror-mapping/plan?fetch_profiles=true&manual=<TICKER>`
  and renders the mapping plan + provider profile preview.
  The drawer never writes the database.
- All UI strings are bilingual (English + Simplified Chinese). The
  required Chinese disclaimer copy lives in `useI18n.jsx`:
  - `me_disclaimer`: `仅供研究参考。财报与新闻不构成买卖建议，需独立验证。`
  - `me_unmapped_explanation`: `未映射表示该标的尚未进入平台证券主数据，暂时无法完整联动研究/回测。`
  - mirror explanation: `Trading 212 官方 API 不提供 App 内关注列表，本镜像由持仓、近期交易与手动关注组成。` (already in the existing mirror card copy from the previous phase)

## 11. Known limitations

- Trading 212's public API has no app-watchlist endpoint, so the
  Mirror is composed (held + recent + manual) — not a byte-for-byte
  copy of the user's in-app watchlist. Phase M does not change this.
- Manual watched tickers persist only in browser localStorage on the
  device that added them. Cross-device sync requires an additive table
  (`mirror_manual_ticker`) which is intentionally NOT added in this
  phase.
- All-market news is intentionally not exposed — only earnings.
- FMP earnings/news coverage varies by exchange and instrument type
  (GDR / ADR / ETF). The provider layer reports `partial` /
  `unavailable` rather than crashing when coverage is incomplete.
- Earnings dates can move; the response is a snapshot of FMP's current
  calendar, not a guarantee. The disclaimer makes this explicit.
- The mapping plan is a snapshot; downstream production bootstrap
  re-fetches the FMP profile and re-validates protected tickers, so
  the plan output is never trusted as a security boundary.

## 12. Side-effect attestations

| | This phase |
|---|---|
| Production DB writes | **NONE** (mapping plan + market events are read-only; bootstrap CLI was implemented but not executed) |
| Production migration | **NONE** (no schema change; manual tickers continue to live in localStorage) |
| Manual sync | **NONE** (`quant-sync-t212` not invoked) |
| Scheduler change | **NONE** |
| T212 write endpoint | **NEVER** (no module references `submit_*_order` or `/equity/orders/*`) |
| Broker write | **NONE** (mirror service / mapper / events service all read-only) |
| Live submit change | **NONE** (`FEATURE_T212_LIVE_SUBMIT=false` preserved) |
| Order/execution objects | **NONE** (`order_intent` / `order_draft` not referenced in new modules) |
| Scraping / browser automation | **NONE** (no selenium/playwright/puppeteer/webdriver) |
| `.firebase/` commit | **NONE** (cache file remains unstaged) |
| Production deploy | **NONE** (commit landed locally; backend revision unchanged at `quant-api-00038-ppm`) |
