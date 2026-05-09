# Overnight Progress — 2026-05-09

**Authorization**: P0–P9 overnight stack. Quality > completion. No fake DONE.

## Baseline (captured 2026-05-09 ~00:50 UTC)

| Item | Value |
|---|---|
| Local HEAD | `65d8239` |
| origin/master | `65d8239` (in sync) |
| Working tree | only `.firebase/hosting…cache` modified (must remain unstaged) |
| `/api/health` | 200 OK |
| Cloud Run service revision | `quant-api-00039-jq4` (100% traffic) |
| Image digest | `sha256:108ee49e692fc5d80801c5a48d3f1bf0eb9dec043422b2a3cdcbf9c98c280f76` |
| Frontend bundle | `index-DGfjSZCd.js` |
| `FEATURE_T212_LIVE_SUBMIT` | `false` |
| Cloud Run jobs | `{quant-sync-t212, quant-sync-eod-prices}` |
| `quant-sync-eod-prices-schedule` | ENABLED, `30 21 * * 1-5`, last `2026-05-08T21:30:05Z` |
| `quant-sync-t212-schedule` | ENABLED, `0 8,21 * * 1-5`, last `2026-05-08T21:00:03Z` |
| Latest C2 execution | `quant-sync-eod-prices-c58zx` (PASS, 36/36, exit 0) |
| Latest T212 execution | `quant-sync-t212-4krch` (PASS) |

Initial state matches user-supplied context exactly. No drift detected.

## Phase log

### P0 — Market Events timeout hardening — DONE / DEPLOYED
- Commit: `a2bca27`
- Backend revision: `quant-api-00040-c95` @ `sha256:0b0dcacd5bab…`
- Frontend bundle: `index-DZgQHfOo.js`
- Tests: 9 new in `test_market_events_timeouts.py`; 346/346 full suite
- Production smoke: `/api/health=200`; all 4 market-events routes 401 unauth; no startup errors

### P1 — Taxonomy all-market scanner foundation — DONE / DEPLOYED (backend)
- Commit: `023e1d9`
- Backend revision: `quant-api-00041-t7c` @ `sha256:6c14df239513…`
- Tests: 39 new in `test_market_taxonomy.py`; 385/385 full suite
- Routes registered: `/scanner/taxonomy/categories`, `/scanner/taxonomy/universe-preview`,
  `/scanner/provider-capabilities`, `/scanner/all-market/preview`
- Frontend Scanner-page integration **deferred** (scope discipline)

### P2 — Overnight market brief plan — DONE (docs only)
- Plan doc: `docs/overnight-taxonomy-market-brief-plan.md`
- Job + scheduler creation **deferred** (depends on P6 migration)

### P5 — Prediction shadow evaluation framework — DONE (docs only)
- Framework doc: `docs/prediction-shadow-evaluation-framework.md`
- Test #1 already evaluated (commit `65d8239`); framework formalises rules

### P7 — T212 sync frequency plan — DONE (docs only; NO scheduler change)
- Plan doc: `docs/trading212-sync-frequency-plan.md`
- Recommendation: Option A `*/30 13-22 * * 1-5` UTC, but execute later
- Schedulers unchanged tonight

### P8 — Mirror manual ticker persistence plan — DONE (docs only)
- Plan doc: `docs/mirror-manual-ticker-persistence-plan.md`
- Migration **deferred** to after P6 settles

### P9 — Prediction model shadow roadmap — DONE (docs only)
- Roadmap doc: `docs/prediction-model-shadow-roadmap.md`
- No model code, no artifact, no schema change tonight
- Hard policy: `FEATURE_ALPHA_PREDICTION_VISIBLE=false`, no UI exposure ever without a separate dedicated commit + review

### P3 — Mirror unmapped instrument bootstrap — PARTIAL (dry-run only)
- Status: dry-run plan path is the existing read-only API
  `GET /api/instruments/mirror-mapping/plan?fetch_profiles=true`
- Production write **deferred**: requires Cloud SQL backup + one-shot job +
  the four-flag CLI handshake. Decided to defer to a separate review cycle
  rather than burn the night's backup budget on it; the read-only mapping
  drawer already shows the user what would be created.

### P4 — Market events provider quality — PARTIAL (P0 covered the urgent piece)
- P0 already added: per-call timeouts, section-level isolation, top-N news,
  bounded concurrency, stale-cache fallback, `provider_status` extended.
- Remaining (deferred): URL/title dedup for news, source-domain extraction,
  optional Massive/Polygon news fallback. Lower urgency now that the user-
  visible "Request timed out" failure mode is fixed.

### P6 — Scanner Alpha D1 migration — PARTIAL (deferred)
- Status: design doc `docs/scanner-alpha-d1-preimplementation-review.md`
  (commit `a15edb5`) covers the 2-table minimal schema (`scanner_run` +
  `scanner_candidate_snapshot`).
- Migration **deferred**: would touch production Cloud SQL with a brand-new
  table; want fresh-eyes review of the schema and feature-flag wiring before
  flipping. The taxonomy module (P1) does NOT depend on this migration —
  the routes use the static theme map only.
