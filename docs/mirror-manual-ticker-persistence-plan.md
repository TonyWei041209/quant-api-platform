# Mirror Manual Ticker Persistence — Plan

Status: P8 of overnight authorization. Documentation only tonight; no migration, no schema change.

## 1. Why

Today's `Trading212MirrorCard` stores manually-watched tickers (`RKLB`, `HIMS`, etc.) in **browser localStorage** under `trading212_mirror_manual_tickers`. The backend `/api/watchlists/trading212-mirror` endpoint accepts them as a query parameter and is otherwise stateless. This works on one device but does not sync across the user's browser, phone, or other devices.

## 2. Proposed addition (additive, deferred to later phase)

A single new table:

```sql
CREATE TABLE mirror_manual_ticker (
  user_id        TEXT NOT NULL,
  ticker         TEXT NOT NULL,                 -- normalized display ticker (UPPER)
  broker_ticker  TEXT NULL,                     -- original T212 broker_ticker if known
  instrument_id  UUID NULL REFERENCES instrument(instrument_id),
  added_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  source         TEXT NOT NULL DEFAULT 'user_input',
  PRIMARY KEY (user_id, ticker)
);

CREATE INDEX ix_mirror_manual_ticker_user ON mirror_manual_ticker(user_id);
```

### Why this shape
- `user_id` is the Firebase ID claim (`uid`); we already have it on every authenticated request.
- `(user_id, ticker)` PK keeps the design uniqueness-clean and matches the localStorage de-duplication semantics.
- `instrument_id NULLABLE` because the unmapped case (RKLB before bootstrap) must persist — that's the whole point.
- `source` allows a future second-class write path if we ever surface the column-level history, without breaking the existing column shape.

## 3. New routes (additive, gated)

```
GET    /api/watchlists/trading212-mirror/manual-items
POST   /api/watchlists/trading212-mirror/manual-items   {ticker}
DELETE /api/watchlists/trading212-mirror/manual-items/{ticker}
```

Behavior:
- **Auth required** (existing pattern).
- **Read-only against any T212 endpoint** — the manual table is internal.
- POST sanitizes input (uppercase, strip non-ticker chars, max 20 chars, idempotent on conflict).
- DELETE returns 200 even if the ticker was not present (idempotent).
- All routes operate on `user_id = current_user.uid` only — no cross-user reads.

## 4. Frontend behavior

- Hook reads localStorage AND (if `FEATURE_MIRROR_MANUAL_TICKER_DB=true`) calls the GET route on mount.
- POST/DELETE go to BOTH localStorage AND the API; localStorage acts as cache + offline fallback.
- On conflict (network failure mid-write), localStorage wins for the current session; next mount reconciles.

## 5. Feature flag

`FEATURE_MIRROR_MANUAL_TICKER_DB=false` shipped with the backend so the routes exist but the frontend doesn't call them yet. Migration ships first, then frontend, then flip-on.

## 6. Migration plan (when authorized)

1. Cloud SQL backup.
2. New Alembic revision adding the table + index. ALTER-free (table is brand new).
3. One-shot Cloud Run Job runs `alembic upgrade head`, `max_retries=0`.
4. Verify via read-only Cloud Run job:
   - `mirror_manual_ticker` exists
   - row count = 0 (clean slate)
   - no other table altered
5. Delete transient migration job.
6. Rollback: `alembic downgrade -1` runs `DROP TABLE mirror_manual_ticker`.

## 7. Side-effect attestations

| | This phase (tonight) | When migration executes |
|---|---|---|
| Production DB write | NONE | only `mirror_manual_ticker` table creation |
| Schema change | NONE | additive (new table only) |
| Existing tables altered | NONE | NONE |
| Trading 212 write | NONE | NONE |
| Live submit | LOCKED | LOCKED |
| Order/execution objects | NONE | NONE |
| `.firebase` commit | NO | NO |

## 8. Why not tonight

The existing localStorage-only flow is working. Migration adds a new table — additive and reversible — but introduces:
- A table that needs cross-user-isolation testing
- Auth-scoped query patterns we haven't exercised at the routing layer

P3 (mirror bootstrap) and P6 (alpha D1 migration) already use up the Cloud SQL backup budget tonight. Manual-ticker persistence is genuinely lower-priority because the user has not lost data; the existing flow is just per-device, not catastrophic.

Recommended sequence: ship after P6 alpha D1 migration is verified stable for a few days, then add this as a small additive migration with a similar one-shot job pattern.
