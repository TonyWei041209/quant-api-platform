# Trading 212 DB Sync Frequency — Plan

Status: P7 of overnight authorization. **Documentation only tonight; no scheduler change executed yet.**

## 1. Why the current cadence

`quant-sync-t212-schedule` currently runs `0 8,21 * * 1-5` UTC — twice a weekday (08:00 and 21:00 UTC). When the platform was a strict "research only" workspace this was fine; the DB snapshot was the only T212 truth path.

After T212 Near-Real-Time Broker Truth (commit `62fb0a0`):
- The **live read-through endpoints** (`/api/broker/t212/live/*`) are the seconds-level truth path. Backend cache TTL floors `1.1s / 5.5s / 60s` keep upstream calls inside the per-account 1 req/sec cap.
- The **DB snapshot** is a fallback + audit trail. Twice-daily writes are enough for that role.

After the ghost-holding fix (`sync_session_id` snapshot-set semantics, applied in migration `b8a3f2d91e47`):
- Each cron tick produces a fresh `sync_session_id` so the dashboard query (`get_portfolio_summary`) returns the most-recent snapshot-set, not an accumulation of qty>0 ghosts.
- Increasing cadence does NOT regress the ghost fix; it just narrows the audit-trail freshness window.

## 2. Recommended new cadence

**Option A** (preferred): `*/30 13-22 * * 1-5` — every 30 min during US trading + extended hours window.
- 20 executions / weekday (vs. 2 today).
- Each execution is ~12 s (existing pattern), so total compute ≈ 4 minutes / day.
- T212 `/equity/positions` is 1 req/sec per account; one execution issues a single positions call. Live read-through can absorb concurrent dashboard polls — the cron does NOT compete with it because it runs a different process.

**Option B** (more conservative): `0 8,13-22 * * 1-5` — hourly during the active window plus the 08:00 anchor.
- 11 executions / weekday.
- Recommended **only if** rate-limit headroom is tight (we have not observed that yet).

**Not recommended**: any cadence finer than 30 min. The live endpoint is for that. DB write amplification past 20× per day adds no analytical value.

## 3. Pre-conditions before the cron change

All must hold before flipping:

- [x] `sync_session_id` snapshot-set semantics active (migration `b8a3f2d91e47` applied; verified in Phase M deploy)
- [x] Live broker truth endpoint healthy (verified in `quant-api-00040-c95` post-deploy 401 unauth probe)
- [x] T212 secrets bound to the API service (since revision `quant-api-00037-ggq`)
- [x] Latest `quant-sync-t212` execution PASS (`quant-sync-t212-4krch` 2026-05-08)
- [ ] Operator has reviewed expected daily executions and rate-limit assumptions — pending.

## 4. Expected impact

| Metric | Before | After Option A |
|---|---|---|
| Executions / weekday | 2 | 20 |
| Compute / weekday | ~25 s | ~4 min |
| `broker_position_snapshot` rows / weekday | ~14 (7 positions × 2) | ~140 |
| `broker_order_snapshot` rows / weekday | ~100 | ~1000 (50 cap × 20 ticks) |
| Time-to-stale fallback view | up to ~13 h | up to 30 min |
| Live endpoint role | unchanged | unchanged |
| Ghost-holdings risk | already fixed | already fixed |

The order-table growth is bounded — each tick reads at most 50 most-recent FILLED orders (the existing T212 adapter cap), and `INSERT ON CONFLICT DO NOTHING` deduplicates by `broker_order_id`. So the row-count grows by genuinely-new orders only, not by 1000 / day.

## 5. Rate-limit safety

T212 documented limits (per account, regardless of API key or IP):
- `/equity/positions`: 1 request / 1 s
- `/equity/account/summary`: not officially published; we treat as 1 req / 5 s
- `/equity/history/orders`: 6 requests / 1 minute (= 1 / 10 s)

The cron does NOT compete with the dashboard live cache — they share a per-account quota but the live cache enforces TTL floors that match the per-second limit. Even at 30-min cron + sub-second dashboard polls, total upstream call volume is below the cap.

Fallback: if T212 ever returns 429 to the cron, the existing per-ticker isolation in `sync_trading212_readonly` causes that one execution to log + skip; the next 30-min tick recovers. No ghost rows are introduced because each tick uses its own `sync_session_id`.

## 6. Rollback

Single-command revert:
```bash
gcloud scheduler jobs update http quant-sync-t212-schedule \
  --location=asia-east2 \
  --schedule="0 8,21 * * 1-5"
```
This is reversible at any time without DB consequence — the existing 30-min snapshots remain in place; the next 21:00 UTC tick continues the prior pattern.

## 7. When to execute the change

Tonight: **NO**. The cadence change is reversible but introduces 10× more cron firings; we should observe one normal trading day with the existing P0 timeout hardening in place before adding execution density. Recommended sequence:

1. Tonight: P0 deployed (revision `00040`), P1 deployed (revision `00041`). No scheduler change.
2. Tomorrow: validate Mirror tab loads cleanly with the timeout hardening; observe the 08:00 UTC `quant-sync-t212` tick PASS as usual.
3. Day after: flip the cadence per §2 Option A and document the change in `docs/runbook.md` + a docs commit.

## 8. Strict attestations for this phase

| | Status |
|---|---|
| Scheduler changed tonight | **NO** |
| `quant-sync-t212-schedule` cron | unchanged (`0 8,21 * * 1-5` ENABLED) |
| `quant-sync-eod-prices-schedule` cron | unchanged (`30 21 * * 1-5` ENABLED) |
| Trading 212 write endpoints | NONE |
| Live submit | LOCKED |
| Production DB write from this doc | NONE |
| Code changes from this doc | NONE (pure docs) |
