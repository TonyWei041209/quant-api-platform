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


