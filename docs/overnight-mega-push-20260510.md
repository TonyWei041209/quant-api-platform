# Overnight Mega Push — 2026-05-10 Run Log

**Operator:** automated agent (Claude)
**Branch:** `master`
**Starting commit:** `a91acd6` (`ci: convert "Deploy to GCP" workflow into hermetic CI-only`)
**Cloud Run revision (start):** `quant-api-00047-5nz`
**FEATURE_T212_LIVE_SUBMIT:** `false` (verified)
**Scope:** research-only platform expansion. No broker writes, no live submit, no order creation.

---

## Phase 0 — Baseline & safety (DONE)

| Check | Result |
|---|---|
| `git status -sb` | `master...origin/master` (only `.firebase/hosting.*.cache` modified locally; will NOT be committed) |
| `gh run list --workflow CI` | latest = `25617265474` success (1m47s) |
| `/api/health` | `{"status":"ok","service":"quant-api-platform","version":"0.1.0"}` |
| Cloud Run `quant-api` Ready | `True`, revision `quant-api-00047-5nz` |
| `FEATURE_T212_LIVE_SUBMIT` env | `false` ✓ |
| Schedulers (`asia-east2`) | `quant-sync-eod-prices-schedule` (ENABLED), `quant-sync-t212-schedule` (ENABLED) — pre-existing, not being modified by this run |
| Cloud Run jobs (`asia-east2`) | `quant-sync-eod-prices`, `quant-sync-t212` — pre-existing, not being modified |
| Repo visibility | `PUBLIC` (flagged for separate review; this run does not change visibility) |

---

## Per-phase progress

### Phase 5 — Overnight CLI + Cloud Run Job + Scheduler (DONE, scheduler PAUSED)

* Commit: `224e437` `feat: add generate-market-brief CLI for overnight job`
* New CLI: `python -m apps.cli.main generate-market-brief`
  with `--mode`, `--days`, `--scanner-limit`, `--news-top-n`,
  `--news-limit-per-ticker`, `--write-snapshot`, `--db-target`.
* Cloud Run revision rebuilt with CLI: `quant-api-00050-m57`
  image `sha256:36925339f6ea...`. Sync-job aligned to same digest.
* Cloud Run Job `quant-market-brief-overnight` created in
  asia-east2 with:
  - image: `sha256:36925339f6ea...`
  - command: `python -m apps.cli.main generate-market-brief
    --mode=overnight --write-snapshot --db-target=production
    --days=7 --scanner-limit=50 --news-top-n=5
    --news-limit-per-ticker=3`
  - cloudsql-instances: `secret-medium-491502-n8:asia-east2:quant-api-db`
  - env: `APP_ENV=production`, `FEATURE_T212_LIVE_SUBMIT=false`,
    `FEATURE_RESEARCH_SNAPSHOT_WRITE=true`, `PYTHONPATH=/app`
  - secrets: `DATABASE_URL_OVERRIDE`, `FMP_API_KEY`, `MASSIVE_API_KEY`
  - max_retries=0, task_timeout=300s
* Manual one-shot validation execution (`quant-market-brief-overnight-6mn56`):
  exit 0; structured stdout shows
  `status=ok ticker_count=24 scanner_matched=14
   scanner_scanned=36 mirror_ticker_count=14
   news_section_state=rate_limited_cached
   side_effects.db_writes=NONE side_effects.live_submit=LOCKED`
  followed by `status=snapshot_done ok=True rows_written=25
  run_id=3685a390-ce5f-4204-908f-4a89ec6f869a`. The brief now has a
  real first row in `market_brief_run` / 24 rows in
  `market_brief_candidate_snapshot`.
* Cloud Scheduler `quant-market-brief-overnight-schedule` created
  with cron `30 6 * * 1-5` UTC, pointing at the new Job. Initial
  state: created ENABLED by default (gcloud limitation), then
  immediately **PAUSED** per policy. Final state verified: `PAUSED`.
  To enable in future, run:

  ```bash
  gcloud scheduler jobs resume quant-market-brief-overnight-schedule \
    --location=asia-east2
  ```
* Tests: 6 new typer cases + prior = **495 unit tests pass**.
* Side-effect attestations:
  - The Job's snapshot write went only to `market_brief_run` +
    `market_brief_candidate_snapshot`; row counts in any
    broker/order/instrument/watchlist/execution table NOT changed.
  - No T212 endpoint called; no order_intent / order_draft created;
    `FEATURE_T212_LIVE_SUBMIT=false` preserved.
  - Scheduler is currently `PAUSED` — will not auto-fire.

### Phase 4 — Brief history endpoints + UI (DONE)

* Commit: `a2f4805` `feat: add overnight brief history surface (read-only)`
* New endpoints (auth-protected): `GET /api/market-brief/latest`,
  `GET /api/market-brief/history?limit=10`,
  `GET /api/market-brief/{run_id}`. Anonymous probe returns HTTP 401
  (verified) — auth integration unchanged.
* New service: `libs/research_snapshot/brief_history_service.py`
  (read-only; never writes the DB; never calls a provider; never
  touches broker/order/live submit).
* Frontend additions on Market Events page: "Show latest saved"
  button, "Show history" toggle, history list (run_id, generated_at,
  source, ticker_count, news_section_state), "from history" badge.
  i18n keys added in en + zh.
* Tests: 10 new history-service cases (list / latest / by-id / empty
  / filter / hydration / invalid uuid). Backend total: **489 unit
  tests pass**. Frontend Vite build clean (bundle
  `index-NJodvwMq.js`).
* Cloud Run revision: `quant-api-00049-l67` (image
  `sha256:d49a8a88746b...`). Sync-job aligned to same digest.
* Frontend deployed via `firebase deploy --only hosting`.

### Phase 3 — Research snapshot persistence (DONE)

* Commit: `1565cac` `feat: persist research scanner and market brief snapshots`
* New tables (additive migration `c1d4e7f8a902`):
  `scanner_run`, `scanner_candidate_snapshot`, `market_brief_run`,
  `market_brief_candidate_snapshot`
* Pre-migration Cloud SQL backup: id `1778380636459` SUCCESSFUL
  (description `pre-research-snapshot-migration-20260510-0237`,
  end_time `2026-05-10T02:38:37Z`)
* Migration executed via one-shot Cloud Run Job
  `quant-ops-migrate-c1d4e7f8a902` on image
  `sha256:adf12219355a...`. Alembic log:
  `Running upgrade b8a3f2d91e47 -> c1d4e7f8a902 ... Container called exit(0)`.
  Job deleted after success.
* Cloud Run revision `quant-api-00048-xmw` (image
  `sha256:adf12219355a...`); sync-job aligned to same digest.
* Tests: 22 new + 457 prior = **479 unit tests pass**.
* Feature flag: `FEATURE_RESEARCH_SNAPSHOT_WRITE` (default ON; not
  set explicitly on the Cloud Run revision so snapshot writes are
  active).
* Side-effect attestations:
  - DB write: ONLY the four new snapshot tables (initially empty)
  - No broker/order/instrument/watchlist/execution table touched
  - No T212 endpoint called
  - No scheduler change
  - `FEATURE_T212_LIVE_SUBMIT` unchanged at `false`

### Phase 2 — Mirror bootstrap (DEFERRED to manual execution)

The mirror-bootstrap production write requires a multi-step GCP
choreography (Cloud SQL backup → dry-run job → plan review → write job →
row-count diff). To keep this overnight push safe, the actual write is
**not** executed automatically.

The allowlist procedure remains documented in
`docs/mirror-bootstrap-allowlist-report.md` (a `§8 2026-05-10 mega-push
run note` was added recording the deferral and the exact gcloud commands
for manual execution).

Side-effects this phase: **NONE** — no Cloud SQL backup, no Cloud Run
Job created, no DB write, no provider call beyond the existing
read-only mapping endpoint.

### Phase 1 — Verify P2.1 brief hardening (DONE / verified live)

P2.1 (`fix: overnight brief news rate-limit hardening + cached fallback`) landed in
commit `45df27f`, deployed in revision `quant-api-00047-5nz` (current). The brief
service module (`libs/market_brief/overnight_brief_service.py`) carries:

* `DEFAULT_NEWS_TOP_N = 5` (lowered from 10)
* `MAX_NEWS_TOP_N_INTERACTIVE = 25`
* `provider_diagnostics.news.section_state` surfacing `rate_limited_cached` / `rate_limited_no_cache` / `cached`
* `requested_news_tickers[]` / `effective_news_top_n` / `requested_news_top_n` / `used_cached_news_count` / `skipped_due_to_rate_limit[]` / `cached_news_age_seconds`
* `libs/market_events/providers.py` 5 stale-on-refresh-fail sites now also fall back on `rate_limited` (previously only timeout/error/partial)

Service tests: **23/23 passing** (includes 10 new `TestRateLimitHardening` cases).
Route requires Firebase auth (HTTP 401 from anonymous probe is expected).


