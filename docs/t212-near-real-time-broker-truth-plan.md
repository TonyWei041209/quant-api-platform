# Trading 212 Near-Real-Time Broker Truth Plan

Status: implemented (commit pending). Production deploy NOT yet performed.

This document explains how the platform shows Trading 212 holdings as
close to real-time as possible while respecting Trading 212's published
rate limits and preserving every existing safety boundary.

---

## 1. Trading 212 official rate limits

Per Trading 212 API docs, applied per account regardless of API key or
source IP. This document encodes them as the floor for our cache TTLs:

| Endpoint                                  | Limit                          |
| ----------------------------------------- | ------------------------------ |
| `GET /equity/positions`                   | 1 request / 1 second           |
| `GET /equity/account/summary`             | not officially published; we treat as 1 req / 5 seconds |
| `GET /equity/history/orders`              | 6 requests / 1 minute (= 1 / 10s) |

When T212 returns `x-ratelimit-limit`, `x-ratelimit-remaining`, or
`x-ratelimit-reset` headers, the cache captures them and refuses to call
upstream until the reset window passes.

---

## 2. Two parallel surfaces: live read-through vs DB snapshot

| Surface                       | Path                                      | Backed by                        | Refresh cadence              | Used by                                |
| ----------------------------- | ----------------------------------------- | -------------------------------- | ---------------------------- | -------------------------------------- |
| Live read-through (NEW)       | `/api/broker/t212/live/{positions,summary,status}` | T212 readonly via cache          | seconds-grain                | Dashboard live truth UI                |
| DB snapshot (existing)        | `/api/portfolio/summary`                  | `broker_*_snapshot` tables       | hours-grain (cron job)       | Holdings overlay, watchlist, research  |

The two surfaces are intentionally decoupled:

- **Live read-through** never writes to the database.
- **DB snapshot** never calls T212 in-line; it relies on the existing
  `quant-sync-t212` Cloud Run Job + Cloud Scheduler.

This separation is what lets the Dashboard show seconds-grain freshness
without hammering T212 with a write path on every poll.

---

## 3. Why we do NOT write the DB on every live read

1. **Rate limits.** Hitting `/equity/positions` once per second per tab
   would exceed T212's 1 req/sec cap if multiple tabs were open. The
   cache + single-flight collapses N tab polls to 1 upstream fetch.
2. **DB write amplification.** A 3-second poll on 8 hours of trading
   would write ~9,600 broker_position_snapshot rows per day. This is
   expensive, has zero analytical value, and pollutes the audit trail.
3. **Snapshot-set semantics.** The DB layer needs a single coherent
   "this is the held set as of time T" view. Multiple sub-second writes
   make snapshot reasoning harder, not easier.
4. **Failure modes diverge.** Live read can fail without dropping the
   audit trail; the audit trail is what backtests, watchlist overlay,
   and held-instrument lookups depend on.

---

## 4. Frontend polling strategy

`useLiveBrokerTruth` hook drives the Dashboard:

| Endpoint               | Default cadence | Floor enforced by hook | Pause condition       |
| ---------------------- | --------------- | ---------------------- | --------------------- |
| `live/positions`       | 3 s             | 1.5 s                  | `document.hidden`     |
| `live/summary`         | 10 s            | 5 s                    | `document.hidden`     |

Behavior:

- Polling stops the moment the tab is hidden (`pageVisible` flips false).
- The same cadence runs across all tabs — the backend cache absorbs the
  load; only one tab actually pays the upstream call within any TTL
  window.
- The user can press **Refresh broker truth** to force an immediate poll
  attempt; the backend may still serve cached data if within TTL.
- A "fast mode" sub-second polling option is **not exposed** in the
  current UI — it would routinely hit the T212 1/sec floor and add no
  visible benefit. If we expose it later, it must remain ≥ 1.5 s.

---

## 5. Server-side cache strategy (`libs/portfolio/broker_live_cache.py`)

Per (broker, account_id, endpoint) keyed cache. For each key:

1. **TTL window** — within the window, return the cached payload with
   `cache_status="cached"`.
2. **Single-flight coalescing** — concurrent requests share one
   in-flight fetch task; only ONE upstream HTTP call goes out per fetch
   window even under heavy concurrency.
3. **Rate-limit gate** — if the last response showed `remaining=0` and
   `reset` is in the future, the cache refuses to call upstream and
   returns the cached payload with `cache_status="rate_limited"`.
4. **429 fallback** — if upstream returns 429 (RateLimitExceeded), the
   cache returns the last-good cached payload with
   `cache_status="rate_limited"` and `stale_reason="upstream returned 429"`.
5. **Generic error fallback** — on any other upstream error, fall back
   to the cached payload with `cache_status="cached"` (or `"error"` if
   no cache exists yet) and a structured `stale_reason`.

TTL floors (cannot be configured below):

| Endpoint  | Default | Floor  | Driving rate limit                       |
| --------- | ------- | ------ | ---------------------------------------- |
| positions | 2.0 s   | 1.1 s  | T212 positions: 1 req/s                  |
| summary   | 10.0 s  | 5.5 s  | conservative; no published limit         |
| orders    | 60.0 s  | 60.0 s | T212 orders history: 6 req/min = 1/10s   |

The constructor silently raises any sub-floor TTL to the floor — defends
against accidental misconfiguration that would breach T212 limits.

---

## 6. Ghost-holding fix (snapshot-set semantics)

### Why ghost holdings happened

Trading 212's `GET /equity/positions` returns ONLY currently-held
positions. When the user closes a position, T212 simply omits it on the
next call — there is no "qty=0" event.

The existing sync writes one `broker_position_snapshot` row per held
position per run. The original portfolio query

```sql
SELECT DISTINCT ON (broker_ticker) ... FROM broker_position_snapshot
WHERE broker = 'trading212' AND quantity > 0
ORDER BY broker_ticker, snapshot_at DESC
```

returns the latest qty>0 row PER ticker that has ever appeared with
qty>0. If a ticker was held during sync N and closed before sync N+1,
its row from sync N still has qty>0, so the dashboard kept showing it.

### Fix

Every `BrokerPositionSnapshot` row written by a single
`sync_trading212_readonly` call shares one `sync_session_id` UUID
(stamped at the start of the function). The new query:

1. Look up the most recent non-null `sync_session_id` for the broker.
2. If found → return only positions whose `sync_session_id` matches.
3. Else → fall back to the legacy DISTINCT-ON path so dashboards never
   go blank during the rollout window (pre-migration / pre-deploy data
   still has NULL `sync_session_id`).

A closed-out ticker is simply not present in the newest sync run, so it
naturally drops out of the dashboard view as soon as the next sync runs
— no zero-row marker, no DELETE, no special case.

The same session-set semantics also apply to `is_instrument_held()` and
`get_watchlist_holdings_overlay()` so research-page and watchlist
overlays stay consistent with the dashboard.

---

## 7. Fallback behavior summary

| Scenario                                         | Dashboard behavior                                                |
| ------------------------------------------------ | ----------------------------------------------------------------- |
| Live endpoint succeeds                           | Badge `LIVE`, positions from live endpoint, "X seconds ago"       |
| Live endpoint cache-hit                          | Badge `CACHED`, positions from cache, "X seconds ago"             |
| Live endpoint rate-limited (429 / remaining=0)   | Badge `CACHED`, last-good payload, `stale_reason` populated       |
| Live endpoint network error                      | Badge `STALE`, falls back to `/portfolio/summary` (DB)            |
| Live endpoint not configured (`T212_API_KEY` absent) | Badge `DB SNAPSHOT`, falls back to `/portfolio/summary`         |

Both surfaces show their own freshness:

- "Live Trading 212 truth: X seconds ago"  → from `live_fetched_at`.
- "Last DB snapshot: X hours ago"          → from `as_of` of `/portfolio/summary`.

---

## 8. Manual refresh behavior

The "Refresh broker truth" button on the Dashboard:

- Calls only the readonly live endpoints.
- Does NOT trigger the scheduled `quant-sync-t212` Cloud Run Job.
- Does NOT write to the DB.
- Does NOT create execution objects.
- May still serve cached data if the backend cache TTL is not yet
  expired — that's by design (the floor protects the upstream rate
  limit). The user can keep clicking, but the behavior degrades
  gracefully.

A "Manual readonly DB sync" button is **deferred to a later phase** —
once the ghost-holding fix is verified in production over several
syncs, we can safely add an authenticated user-triggered sync.

---

## 9. Strict guardrails (unchanged by this plan)

- `FEATURE_T212_LIVE_SUBMIT = false` (production env var).
- No T212 write endpoint is called by any module touched in this
  change. Static guard tests in `tests/unit/test_no_trading_writes.py`
  pin this.
- No `OrderIntent` / `OrderDraft` is created by the live endpoints, the
  cache, or the sync function.
- No production DB write outside `broker_*_snapshot` and `source_run`.
- No scheduler change in this phase (the existing `quant-sync-t212-schedule`
  cron of `0 8,21 * * 1-5` UTC is preserved).
- No Cloud Run Job created or modified for this change. Production
  deploy of the new image is required before the feature works in
  production, but that deploy is intentionally NOT performed by this
  change set; it requires explicit operator authorization following
  the existing deploy playbook.

---

## 10. Future phases

These were considered but deliberately deferred to keep this change
small and reversible:

1. **Manual readonly DB sync button** — once the ghost-holding fix has
   been observed across several `quant-sync-t212` runs in production
   without regression, expose a UI button that triggers a one-off
   readonly sync.

2. **Scheduler frequency increase** — bump `quant-sync-t212-schedule`
   from twice-daily to roughly every 30 minutes during market hours.
   This MUST come AFTER the ghost-holding fix has been verified;
   otherwise more frequent writes just multiply the ghost rows in the
   pre-fix code path. Recommended cadence:
   `*/30 14-21 * * 1-5` UTC (every 30 min during US trading hours).

3. **Broker health endpoint** — `/api/broker/t212/health` returning
   `{last_sync_at, sync_age_seconds, scheduler_enabled, account_id,
   db_position_count, live_position_count}` to drive an alerting view
   and to power the live-vs-DB diff card.

4. **Order-history live read-through** — currently the live endpoints
   skip orders. A `live/orders` endpoint with a 60s+ TTL is feasible
   given T212's 6 req/min limit on history.

---

## 11. Acceptance for Phase 1 of this plan

- [x] `sync_session_id UUID` nullable column added to
      `broker_position_snapshot` via Alembic migration with two indexes.
- [x] `sync_trading212_readonly` mints one UUID per run and stamps every
      position row.
- [x] `get_portfolio_summary`, `is_instrument_held`,
      `get_watchlist_holdings_overlay` use snapshot-set semantics with
      legacy fallback.
- [x] `BrokerLiveCache` with TTL floors, single-flight, 429 fallback,
      and `x-ratelimit-*` header awareness.
- [x] `/api/broker/t212/live/{positions,summary,status}` endpoints with
      a JSON envelope including `cache_status`, `live_fetched_at`,
      `provider_latency_ms`, `rate_limit`, and `stale_reason`.
- [x] Dashboard shows `LIVE / CACHED / STALE / DB SNAPSHOT` badge plus
      both freshness timestamps and a Refresh-broker-truth button.
- [x] Polling pauses when the tab is hidden.
- [x] All new tests pass; source-grep guards prevent any path from new
      modules to T212 write endpoints or execution objects.
- [ ] (Operator) Production deploy of the new image.
- [ ] (Operator) After deploy, exactly one readonly sync is needed to
      create the first non-null `sync_session_id`. The existing cron at
      08:00 / 21:00 UTC will produce this naturally; no manual run is
      required, but if desired, a single execution of
      `gcloud run jobs execute quant-sync-t212 --region asia-east2` is
      the documented manual path.
