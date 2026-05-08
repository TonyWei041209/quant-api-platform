# Scanner Alpha Lab — D1 Pre-implementation Review

> **Status: pre-implementation review only.** This document does not
> create tables, does not modify code, does not deploy, and does not
> change schedulers. It refines the D0 roadmap into a concrete D1 plan
> and pins the gates that must pass before D1 implementation may begin.
>
> **Hard pre-condition**: D1 cannot start until **Prediction Shadow
> Test #1 evaluation is complete** (tick #6 has fired, eval doc has
> been written, and the deterministic heuristic was not catastrophically
> wrong).

## Contents

1. Recommended D1 minimum scope (tighter than D0)
2. Recommended D1 schema, column-by-column
3. Required indexes
4. Foreign keys + nullability
5. Rollback plan
6. Historical backfill — recommendation
7. Non-interference with the live scanner endpoint
8. Separation between rule-based output and future model output
9. Tests D1 must include
10. D1 acceptance criteria (must all pass before implementation)

---

## 1. Recommended D1 minimum scope

The D0 roadmap §4 listed **6 tables** for the persistence layer. After
re-reading the rest of the roadmap (labels in §5, features in §6,
evaluation in §7) and weighing against the principle that *each phase
should be the smallest reversible change that's still useful*, this
review recommends shrinking D1 from 6 tables to **2 tables**:

| Table | D0 says | This review says | Rationale |
|---|---|---|---|
| `scanner_run` | D1 | **D1** ✓ | Cheap to stand up, immediately useful for run-level audit. |
| `scanner_candidate_snapshot` | D1 | **D1** ✓ | Captures the deterministic output we already produce live. |
| `alpha_feature_snapshot` | D1 | **D3** | Feature definitions need to be frozen first. Defining the column too early risks a wasted migration if `feature_set_version=fs_v1` shifts. |
| `alpha_label_snapshot` | D1 | **D2** | Labels need to be defined and the materializer in place. Defining the column too early risks a wasted migration. |
| `alpha_model_run` | D1 | **D4** | Needs at least one trained model to be meaningful. Empty table noise. |
| `alpha_prediction_shadow` | D1 | **D6** | Needs a model AND a scoring path. Empty table noise. |

The **alpha_prediction_id** FK column on `scanner_candidate_snapshot`
stays in D1 as a **NULLABLE** column, so future alpha tables can attach
without re-migrating the snapshot table. The FK target is left
**unenforced at the DB level in D1** (no `REFERENCES` constraint until
`alpha_prediction_shadow` actually exists in D6) so the column is
effectively "logical pointer, populated later".

**Reasons for the tighter scope**:

- **Minimum-viable D1**. Two tables is the smallest change that is both
  reversible and useful. It lets us start logging the existing
  deterministic scanner output without any model dependencies.
- **Schema noise avoidance**. Empty tables age poorly. Their column
  definitions tend to be guessed-too-early and need migrating later.
- **Reversibility**. Two tables = one migration up, one migration down,
  zero impact on existing tables. We can revert D1 in minutes.
- **Aligns with the "D2 labels → D3 features → D4 model" pipeline**.
  Each of those steps creates the table it actually needs at the
  moment it actually needs it.
- **Doesn't lock us in**. The D0 roadmap's eventual 6-table shape
  remains the target. D1 just delivers the first slice.

If the user prefers the full 6-table D0 plan, that's also defensible —
the cost is mostly schema noise + a slightly larger rollback surface.
This review's recommendation is the conservative path.

---

## 2. Recommended D1 schema (column-by-column)

Same SQLModel + SQLAlchemy patterns the project already uses for
`instrument`, `instrument_identifier`, etc. Postgres flavour (Cloud
SQL); native UUID columns; JSONB for set-typed fields.

### 2.1 `scanner_run`

```sql
CREATE TABLE IF NOT EXISTS scanner_run (
    run_id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    mode              TEXT         NOT NULL,                     -- enum: manual_research / nightly / scheduled
    triggered_by      VARCHAR(64)  NOT NULL,                     -- cli / api / scheduler
    universe          VARCHAR(64)  NOT NULL,                     -- 'scanner-research' today
    as_of_date        DATE         NOT NULL,                     -- EOD date the run uses
    instrument_count  INTEGER      NOT NULL DEFAULT 0,           -- expected 36 today
    matched_count     INTEGER      NOT NULL DEFAULT 0,           -- candidates that matched ≥ 1 scan_type
    started_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    completed_at      TIMESTAMPTZ  NULL,
    error_summary     TEXT         NULL,                         -- bounded ≤ 512 chars at app layer
    status            TEXT         NOT NULL DEFAULT 'planned',   -- planned / running / completed / failed
    schema_version    SMALLINT     NOT NULL DEFAULT 1,           -- bump on additive change
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**Why these columns and not D0's exact list**:

- Added `matched_count` so a single run-level row tells the story
  ("scanned 36, matched 15") without joining the snapshot table.
- Added `schema_version` so D2/D3/D4 additive changes are explicit and
  auditable. Default `1` matches D1.
- `mode` and `status` are kept as **TEXT not enum** for portability;
  enforcement happens at the Pydantic schema layer (the project
  already uses this pattern in `companion`, `coder_review`, etc.).
- Removed `error_summary` length cap from the column itself; the cap
  lives in the Pydantic schema (truncation at write time).

### 2.2 `scanner_candidate_snapshot`

```sql
CREATE TABLE IF NOT EXISTS scanner_candidate_snapshot (
    snapshot_id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                UUID         NOT NULL REFERENCES scanner_run(run_id) ON DELETE RESTRICT,
    instrument_id         UUID         NOT NULL REFERENCES instrument(instrument_id) ON DELETE RESTRICT,
    -- Deterministic scanner output (mirrors the existing API response):
    signal_strength       VARCHAR(16)  NOT NULL,                     -- 'low' / 'medium' / 'high'
    scan_types            JSONB        NOT NULL DEFAULT '[]'::jsonb, -- list[str], whitelist enforced at app layer
    risk_flags            JSONB        NOT NULL DEFAULT '[]'::jsonb,
    volume_ratio          NUMERIC(10,4) NULL,
    change_1d_pct         NUMERIC(10,4) NULL,
    change_5d_pct         NUMERIC(10,4) NULL,
    change_1m_pct         NUMERIC(10,4) NULL,
    week52_position_pct   NUMERIC(8,4) NULL,
    recommended_next_step VARCHAR(32)  NOT NULL,                     -- whitelist enforced at app layer
    explanation           TEXT         NOT NULL,                     -- BANNED_WORDS-checked at app layer
    -- Forward pointer to alpha layer (logical pointer until D6).
    alpha_prediction_id   UUID         NULL,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**Why these columns**:

- Mirrors `apps/api/toni_api/routers/scanner.py::ScanItem` 1:1, except
  `data_mode` and `as_of` (those live on `scanner_run` to avoid
  duplication: every snapshot in a run shares those values).
- `scan_types` and `risk_flags` are JSONB lists, NOT separate
  many-to-many tables. The whitelist is enforced at the app layer in
  `libs/scanner/stock_scanner_service.py` and the Pydantic schema.
  Adding M2M tables here would be over-engineered for D1.
- `recommended_next_step` is `NOT NULL`. The scanner already always
  produces a value; persisting `NULL` is a code-side bug.
- `alpha_prediction_id` is NULL by default in D1. No `REFERENCES`
  clause until D6 creates the target table. The column documents the
  intent without coupling D1's migration to D6.

---

## 3. Required indexes

| Table | Index | Columns | Purpose |
|---|---|---|---|
| `scanner_run` | PK (auto) | `run_id` | identity |
| `scanner_run` | `idx_scanner_run_started_at` | `started_at DESC` | "most recent runs" listing |
| `scanner_run` | `idx_scanner_run_universe_asof` | `(universe, as_of_date)` | "what did we scan on this day" |
| `scanner_run` | `idx_scanner_run_status` | `(status)` partial WHERE `status IN ('planned','running')` | quick liveness probe |
| `scanner_candidate_snapshot` | PK (auto) | `snapshot_id` | identity |
| `scanner_candidate_snapshot` | `idx_scs_run_id` | `(run_id)` | "all candidates from run X" |
| `scanner_candidate_snapshot` | `idx_scs_instrument_created` | `(instrument_id, created_at DESC)` | "history of this ticker" |
| `scanner_candidate_snapshot` | `idx_scs_alpha_prediction_id` | `(alpha_prediction_id)` partial WHERE NOT NULL | future alpha-layer joins; tiny while empty |

**Index hygiene notes**:

- No GIN index on `scan_types` / `risk_flags` JSONB columns in D1.
  Querying-by-flag is rare in the deterministic phase and the JSONB
  GIN index is meaningfully large (~30% of table size for sparse
  arrays). Add later if the eval / dashboard needs it.
- Partial indexes (`WHERE status IN ('planned','running')` and
  `WHERE alpha_prediction_id IS NOT NULL`) keep the index footprint
  proportional to the *actually-relevant* row count.
- All index creation must use `CREATE INDEX IF NOT EXISTS …
  CONCURRENTLY` in the production migration to avoid table-level
  lock-out (the migration runs against live `instrument` data via the
  FK, but Postgres only checks the FK on inserts not on existing
  rows).

---

## 4. Foreign keys + nullability

| Column | FK target | Nullable | ON DELETE | Reasoning |
|---|---|---|---|---|
| `scanner_candidate_snapshot.run_id` | `scanner_run.run_id` | NOT NULL | RESTRICT | a snapshot without a run is meaningless |
| `scanner_candidate_snapshot.instrument_id` | `instrument.instrument_id` | NOT NULL | RESTRICT | preserve referential integrity with the universe; we never delete instruments |
| `scanner_candidate_snapshot.alpha_prediction_id` | (none in D1) | NULLABLE | n/a | logical pointer; FK constraint added in D6 only after `alpha_prediction_shadow` exists |
| `scanner_run.error_summary` | n/a | NULLABLE | n/a | only set on `failed` runs |
| `scanner_run.completed_at` | n/a | NULLABLE | n/a | NULL until run finishes |
| All numeric `change_*` / `volume_ratio` / `week52_position_pct` | n/a | NULLABLE | n/a | mirrors the existing scanner schema where any field can be `None` if data is partial |

**Why ON DELETE RESTRICT, not CASCADE**:

- Deleting a `scanner_run` should not silently drop 36 candidate rows.
- If a row needs to be removed (e.g., an aborted manual run), the
  app-layer cleanup must explicitly delete the children first. This
  is auditable; a CASCADE is not.

---

## 5. Rollback plan for the migration

D1 is purely **additive**: two new tables, no ALTER on existing tables,
no data migration. The rollback is therefore the simplest possible.

### 5.1 Pre-flight (must all PASS before running the migration)

1. Take a fresh Cloud SQL backup. Capture the `BACKUP_ID`.
2. Run the migration **dry-run** locally against a clone of the
   production schema (Postgres).
3. Run the migration **dry-run + rollback** locally to confirm both
   directions work cleanly on a fresh schema.
4. `pytest tests/unit/test_scanner_run_schema.py` and
   `test_alembic_migration_up_down.py` both pass.
5. `gh repo view --json visibility` confirms repo is **PRIVATE**.
6. `gcloud scheduler jobs describe quant-sync-eod-prices-schedule
   --format="value(state)"` returns `ENABLED` and the next-tick window
   is at least 60 minutes in the future (so the migration completes
   well before the next scheduled tick).

### 5.2 Up migration (Alembic-style)

```python
def upgrade() -> None:
    op.create_table(
        "scanner_run",
        ...
    )
    op.create_table(
        "scanner_candidate_snapshot",
        ...
    )
    op.create_index("idx_scanner_run_started_at", ..., postgresql_concurrently=True)
    op.create_index("idx_scanner_run_universe_asof", ..., postgresql_concurrently=True)
    op.create_index("idx_scanner_run_status_active", ..., postgresql_concurrently=True,
                    postgresql_where=sa.text("status IN ('planned','running')"))
    op.create_index("idx_scs_run_id", ..., postgresql_concurrently=True)
    op.create_index("idx_scs_instrument_created", ..., postgresql_concurrently=True)
    op.create_index("idx_scs_alpha_prediction_id", ..., postgresql_concurrently=True,
                    postgresql_where=sa.text("alpha_prediction_id IS NOT NULL"))
```

### 5.3 Down migration

```python
def downgrade() -> None:
    # Order matters: drop FK-bearing child first.
    op.drop_table("scanner_candidate_snapshot")
    op.drop_table("scanner_run")
```

The down migration is **deterministic and zero-risk** because:

- No existing table is altered, so there's no data to "un-migrate".
- The new tables have no other tables referring to them (the
  `alpha_prediction_id` column is a logical pointer, not an FK).
- Backups remain identical to pre-migration state.

### 5.4 Rollback triggers (when to invoke `downgrade()`)

| Trigger | Action |
|---|---|
| Migration up fails partway | Auto-stop; downgrade is unnecessary because nothing was committed (transactional DDL on Postgres). |
| Production smoke after migration shows scanner endpoint regressed (`scanned ≠ 36` or 5xx) | Roll back via `downgrade()` and revert the deploy that wired the persistence call. |
| Any execution / broker / live-submit value changes during the migration window | Roll back **immediately**, restore from `BACKUP_ID`, escalate. |
| Audit row count for `order_intent` / `order_draft` increases during the migration window | Same as above. |

### 5.5 Recovery time objective (RTO)

- DDL alone: < 5 seconds.
- DDL + smoke + decision to roll back: < 5 minutes.
- DDL + smoke + decision to restore from backup: < 30 minutes.

---

## 6. Historical backfill — recommendation

**Recommendation: do NOT backfill historical scanner runs in D1.**

Rationale:

- We do not have a high-fidelity record of historical scanner outputs.
  The audit log retains *event types and counts*, not the per-ticker
  scan_types / risk_flags / explanations.
- A "synthetic" backfill that re-runs today's deterministic rules
  against historical bars is **not** a record of past scanner state —
  it would be the *current* rules applied to *historical* features.
  Persisting that as if it were historical state is misleading.
- Empty rows accumulate from D2 onwards anyway; missing back-history
  doesn't block the alpha lab pipeline (which uses `price_bar_raw`
  and `instrument_identifier` directly via the feature materializer).

If a backfill IS desired later, do it as a **separate, optional**
one-shot CLI in D2 or later, with:

- Explicit `--backfill --confirm` flags.
- A `backfill=true` column added to `scanner_run` so synthetic rows
  are visibly distinguishable from live ones.
- A rate-limited writer (e.g., commit every 100 rows) to avoid lock
  pressure during business hours.

D1 itself remains pure DDL — no data writes.

---

## 7. Non-interference with the live scanner endpoint

The single most important property of D1 is that the production
scanner API (`GET /api/scanner/stock`) **must continue to behave
exactly as it does today** after the migration lands.

### 7.1 Concrete invariants

- Response schema unchanged. Pydantic `ScanItem` and `ScanResponse`
  are NOT modified in D1. No new fields. `extra="forbid"` stays.
- Response body byte-for-byte equivalent on the same input given the
  same DB state.
- Latency budget: the scanner endpoint already takes ~150–300ms in
  production. Persistence overhead must be < 50ms p95.
- 5xx rate: the persistence layer must NEVER cause a 5xx. Errors are
  logged and swallowed.

### 7.2 Implementation pattern (proposed for D1)

```python
# pseudocode — actual code lands in D1 PR
def scan_stocks(...) -> ScanResponse:
    response = _build_scanner_response(...)  # existing path, unchanged
    try:
        _persist_scanner_run(response)  # NEW in D1, isolated try/except
    except Exception:
        log.warning("scanner.persistence.failed")
        # fall through — DO NOT raise
    return response
```

The persistence call:

- Runs **after** the response is built. Caller never waits on it for
  correctness.
- Wraps DB I/O in a single try/except that logs and swallows.
- Uses a **separate session** so a persistence-side rollback can't
  abort the response-side reads.
- Is the only place in the scanner code path that writes to the new
  tables. No other route, no other CLI command writes here in D1.

### 7.3 Failure isolation tests (mandatory in D1)

- DB unreachable during persistence → endpoint still returns 200 with
  the correct response body.
- Foreign-key violation during persistence → same.
- Disk full / WAL pressure simulated → same.

### 7.4 What D1 deliberately does NOT do

- Does NOT change any field in `ScanResponse`.
- Does NOT add a `run_id` field to the response (deferred to a future
  small change after D1 stabilizes).
- Does NOT make the response shape contingent on whether the row was
  persisted successfully.

---

## 8. Storing rule-based scanner output separately from future model output

D0 §4 already calls this out, but the review pins it as a **hard
invariant**:

| Layer | Lives in | D1 owns it? | Touches model output? |
|---|---|---|---|
| Deterministic scanner rules | `libs/scanner/stock_scanner_service.py` (existing) | Read by D1; not modified | Never |
| Persistent record of deterministic output | `scanner_run` + `scanner_candidate_snapshot` (D1) | Yes | Never (the `alpha_prediction_id` is a NULL pointer in D1) |
| Future feature materializer | `libs/alpha_lab/features.py` (D3) | No | Reads `price_bar_raw` only; writes `alpha_feature_snapshot` |
| Future label materializer | `libs/alpha_lab/labels.py` (D2) | No | Same |
| Future model run record | `alpha_model_run` (D4) | No | Read-only with respect to scanner tables |
| Future shadow predictions | `alpha_prediction_shadow` (D6) | No | Writes `alpha_prediction_shadow.alpha_prediction_id`; D7 backfills the FK on `scanner_candidate_snapshot.alpha_prediction_id` |

**Hard invariants pinned by tests in D1**:

1. `scanner_candidate_snapshot.signal_strength` MUST come from
   `libs.scanner.stock_scanner_service._signal_strength` and nowhere
   else. No model, no LLM, no trained classifier influences this
   column.
2. `scanner_candidate_snapshot.scan_types`, `risk_flags`,
   `recommended_next_step`, and `explanation` MUST come from the same
   deterministic service.
3. The persistence path MUST NOT import from `libs/alpha_lab/`. (Only
   D6+ writes `alpha_prediction_id`, and that write happens via a
   separate post-write update or via the alpha-side service after a
   prediction is recorded.)
4. The persistence path MUST NOT call any model inference path
   (Polygon / FMP adapters are fine; LLM / scikit-learn is not).

These invariants are pinned by source-grep tests modelled on the
existing `tests/unit/test_stock_scanner.py::TestExplanationGuardrail`.

---

## 9. Tests D1 must include

Naming follows the project's existing `tests/unit/` convention.

| Test file | What it pins |
|---|---|
| `test_scanner_run_schema.py` | Tables + columns + indexes exist after migration. Column types match the spec in §2. |
| `test_scanner_run_persistence.py` | Insert + read works; FK constraints fire on bad `run_id` / `instrument_id`. ON DELETE RESTRICT actually restricts. |
| `test_scanner_candidate_snapshot_persistence.py` | Same, but for the snapshot table. |
| `test_scanner_endpoint_unchanged.py` | `GET /api/scanner/stock` returns identical bytes for identical input pre- and post-migration. Pydantic schema strictness still rejects extra fields. |
| `test_scanner_logging_failure_isolation.py` | DB unreachable / FK violation / generic Exception during persistence does NOT cause a 5xx. Endpoint still returns 200 with the correct body. |
| `test_scanner_logging_no_extra_writes.py` | Exactly two new tables grow during a run (`scanner_run` +1 row, `scanner_candidate_snapshot` +N rows). No other table changes. Specifically: `order_intent`, `order_draft`, `broker_*` row counts unchanged. |
| `test_scanner_persistence_source_guards.py` | Source-level grep that the persistence module does NOT import from `libs/alpha_lab/`, does NOT import openai / anthropic / torch, does NOT call `subprocess` / `os.system`. |
| `test_alembic_migration_up_down.py` | Up migration creates the two tables; down migration drops them; the cycle is idempotent on a fresh DB. |
| `test_scanner_run_audit_payload.py` | New audit event types (`SCANNER_RUN_LOGGED` if added) carry counts / IDs only — never per-candidate explanation text or scan_types content. |

**Test count expectations**: ~30 new unit tests, all hermetic (no
real Cloud Run, no real DB beyond a `pytest tmp_path` SQLite). Full
suite must remain green with at least the same pass count as before
D1 lands (currently 244 unit tests; D1 should add ~30 → ~274).

---

## 10. D1 acceptance criteria (must all PASS before implementation)

| # | Criterion | How to verify |
|---|---|---|
| 1 | Phase C is **stable** | Already PASS — `docs/scanner-research-universe-production-plan.md` "Phase C2 — STABLE" section + commit `8a92149`. |
| 2 | Prediction Shadow Test #1 has a written **eval report** | Must exist as `docs/scanner-prediction-shadow-test-1-eval.md` and cite commit `7ff4d83` for pre-registration provenance. |
| 3 | Eval shows the deterministic heuristic was not catastrophically wrong | Concrete numerical bar: in-universe `direction_accuracy ≥ 0.30` (not `≤ 0.10`). The eval bar is intentionally permissive — D1 is persistence, not a model — but a 0% direction hit would suggest the rules need fixing before logging them at scale. |
| 4 | Explicit user sign-off in chat | Recorded in this conversation thread; D1 implementation may not start otherwise. |
| 5 | Production state unchanged from current | scheduler ENABLED, jobs `{quant-sync-t212, quant-sync-eod-prices}`, FEATURE_T212_LIVE_SUBMIT=false, `quant-api-00035-kpz`. |
| 6 | Backup of production Cloud SQL taken < 30 minutes before migration | New backup ID captured in commit message. |
| 7 | Migration up + down both pass on a local clone | `pytest test_alembic_migration_up_down.py` green. |
| 8 | Source-guard tests pin the absence of forbidden imports | Listed in §9. |
| 9 | Endpoint smoke pre- and post-migration | scanner returns `scanned=36` and 200 in both states. |
| 10 | Audit row count delta = 0 for execution / broker tables | Verified via a read-only one-shot status job before commit, again after. |

A failure on ANY criterion → D1 implementation does not start. The
eval report (criterion #2) is the most likely gating item right now —
it depends on tick #6 firing (scheduled `2026-05-08T21:30Z`) and the
operator (or a future eval helper) running the comparison.

---

## 11. Open questions parked for D1+ (not blocking this review)

1. **Should the persistence call be sync or async?** Today's scanner
   endpoint is sync. The simplest D1 is sync-after-response (proposed
   in §7.2). Background-task offloading is a future polish.
2. **Should `scanner_run` carry `request_origin` (e.g., the IP / auth
   subject)?** Not in D1 — privacy implications need a separate
   review. The Pydantic schema doesn't expose this anyway.
3. **Do we need a `WHERE` index on `(as_of_date, status)` for daily
   "did today's scanner run already complete?" queries?** Probably
   yes once the nightly D7+ scheduler exists. For D1 manual runs the
   `idx_scanner_run_universe_asof` index is sufficient.
4. **JSONB vs TEXT for `scan_types` / `risk_flags`?** Postgres-only
   features (JSONB) tie us to Postgres. SQLite is used in tests but
   we already use JSONB-style columns elsewhere via SQLModel's `JSON`
   column type which transparently maps SQLite→JSON1 and Postgres→JSONB.
   Stick with the existing pattern.
5. **Should `scanner_candidate_snapshot` be partitioned by month?**
   At 36 instruments × 1 daily run × 252 trading days/year = ~9k rows
   per year. Partitioning is overkill until we cross 1M rows. Defer.

---

## 12. Side-effect attestations (this pre-implementation review)

| Item | Status |
|---|---|
| DB writes performed by this round | **NONE** |
| DB schema changes | **NONE** (this is a review, not the migration) |
| Code changes | **NONE** |
| Model training | **NONE** |
| Production redeploy | **NONE** (`quant-api-00035-kpz` unchanged) |
| Cloud Run jobs created | **NONE** |
| Cloud Scheduler changes | **NONE** (`quant-sync-eod-prices-schedule` remains `ENABLED`) |
| Manual sync invocation | **NONE** (tick #6 will fire on its own at 2026-05-08T21:30Z) |
| Edits to `docs/scanner-prediction-shadow-test.md` | **NONE** (pre-registration left untouched) |
| Tick #6 evaluation run early | **NO** (deferred until after tick #6 completes) |
| Broker writes / execution objects | **NONE** |
| Live submit changes | **NONE** (`FEATURE_T212_LIVE_SUBMIT=false` unchanged) |
| `.firebase` cache committed | **NO** |

---

## 13. Suggested next steps

1. **Wait** for tick #6 (2026-05-08T21:30Z, ~ scheduled) to fire on
   its own. Do not run early.
2. After tick #6 completes (~21:38Z), run the eval per the
   `docs/scanner-prediction-shadow-test.md` §6 plan and write
   `docs/scanner-prediction-shadow-test-1-eval.md`. **Separate
   sign-off** — eval is its own commit.
3. Read this pre-implementation review against the eval outcome.
4. If the eval clears the bar in §10 #3, request explicit D1
   implementation sign-off in chat.
5. D1 implementation is then a single, reviewed PR that lands the
   migration + the persistence call + the test suite from §9.

Until step 4, this document remains the authoritative pre-implementation
plan. If the eval surprises (e.g., direction_accuracy = 0.0 across the
sample), revisit §1 and §10 — the gating bar may need to be updated
*before* D1 starts.
