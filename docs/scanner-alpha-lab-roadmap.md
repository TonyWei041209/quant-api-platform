# Scanner Alpha Lab — Roadmap (Phase D0)

> **Status: design-only.** Phase D0 is documentation. No code, no DB
> migration, no model training, no deploy, no scheduler change. The
> Phase C2 daily EOD sync observation window remains undisturbed.

This document plans the next layer on top of the deterministic
Stock Scanner (Phase A): a research-only **alpha lab** that tries to
estimate **short-term surge potential** for the 36-instrument scanner
universe and surfaces it in the existing Scanner UI as a "Surge Watch
Score" / "Research Priority" — never as a buy/sell instruction.

The roadmap is sized for incremental work. Every step is reversible,
test-pinned, and gated behind explicit user sign-off, mirroring the
B/C-phase discipline.

---

## 1. Why now (and the explicit guardrails)

We just finished:

- 36-ticker production scaffolding (B3.2-A) + EOD seed (B3.2-B)
- Daily incremental sync (Phase C1 + C2) with 4/5 ticks PASS so far
- A frozen, schema-locked Scanner that emits research candidates with
  `signal_strength`, `risk_flags`, `recommended_next_step`, and a
  research-toned `explanation`

The existing scanner is **deterministic and rule-based**. It tells the
operator "AMD has momentum + breakout + needs research". It does NOT
estimate "how big a move could plausibly happen in the next 5 trading
days, conditional on current state".

A model trained on the 13,000+ EOD bars now in production could fill
that gap WITHOUT changing the deterministic scanner output and
WITHOUT introducing any new execution path.

**Hard guardrails carried forward** (test-pinned in the existing
`tests/unit/test_stock_scanner.py` + `BANNED_WORDS` source pin):

- No execution objects (`order_intent` / `order_draft`) created by
  the alpha lab.
- No broker write. Trading 212 stays read-only.
- `FEATURE_T212_LIVE_SUBMIT=false` does not change.
- Scanner explanation tone (research-only) is preserved. The new
  `surge_watch_score` field MUST go through the same `BANNED_WORDS`
  gate and `Pydantic extra="forbid"` schema as the existing fields.
- Outputs are research signals, not trading instructions.

---

## 2. Product goal

| Goal | Description |
|------|-------------|
| **Detect surge candidates** | For each instrument in the scanner universe, estimate the probability of a short-term upward move (5/10/20 trading days) from current state. |
| **Rank for research priority** | Convert per-instrument probabilities into a small-integer **Research Priority** score (1–5) that the operator can sort by. |
| **Stay research-only** | The output is a *score*, never a recommendation. No `target_price`, no `position_size`, no `entry`/`exit` language anywhere. |
| **Be honest about uncertainty** | Every prediction comes with an out-of-sample evaluation summary visible from the UI. |
| **Be reversible** | The whole alpha lab can be turned off via a single feature flag without touching the deterministic scanner. |

### Output schema (proposed, will live alongside existing `ScanItem`)

```jsonc
// research-only fields appended to ScanItem (additive, extra="forbid"):
"surge_watch_score": 0.0–1.0,            // model probability, optional
"research_priority": 1–5,                 // bucketed integer, optional
"alpha_model_id": "string",               // which model produced the score
"alpha_model_version": "v1",              // version pin
"alpha_eval_summary": {                   // out-of-sample only, never train-set
  "precision_at_top_5": 0.42,
  "precision_at_top_10": 0.31,
  "avg_max_return_5d": 0.078,
  "n_walk_forward_folds": 8,
  "as_of": "2026-04-30"
}
```

`recommended_next_step` stays in the existing whitelist
(`research / validate / add_to_watchlist / run_backtest / monitor`).
The alpha lab does NOT add any new value to that enum.

---

## 3. Open-source ideas to draw from (read-only; no source copy)

The alpha lab borrows ideas, not code, from a curated set of open
research projects. We treat each as **inspiration / research
reference**, not as a runtime dependency.

| Project | What we'll borrow | What we WILL NOT do |
|---------|-------------------|---------------------|
| **Microsoft Qlib** | Walk-forward evaluation harness, factor library naming conventions (alpha158/alpha360), point-in-time joins | Use Qlib's runtime data layer; install Qlib in production; let it dictate our ORM |
| **Microsoft RD-Agent** | Idea: an agent that proposes and evaluates new factors offline, gated by human review | Auto-merge any factor it proposes; let it modify production code |
| **vectorbt** | Vectorized signal evaluation, drawdown / max-return computation patterns | Use vectorbt as a runtime backtester (we already have `libs/backtest/`) |
| **FreqAI** | Self-retraining cadence pattern, feature → model → prediction pipeline shape | Adopt FreqAI's auto-trading hooks (we forbid auto-execution) |
| **MLFinLab** | Triple-barrier labeling (López de Prado), purged k-fold, sample-weight schemes for overlapping labels | Adopt the broader "differential subscription" runtime; install MLFinLab in production |
| **ta / pandas-ta** | Indicator definitions (ATR, Bollinger, RSI, OBV, ADX) as documented references | Vendor in the libraries; let them silently install transitive deps |
| **OpenBB** | Field naming for fundamentals / macro overlays we may add in D8+ | Use OpenBB's runtime data fetchers in production (we already have Polygon + FMP) |
| **FinRobot** | Idea: a research-only narrative layer that explains why a candidate scored high | Run FinRobot agents inside production; auto-generate buy/sell narratives |
| **TradingAgents** | Idea: parallel "analyst" + "skeptic" prompts for a candidate, NEVER as an execution loop | Use it for trade execution; chain analysts to broker tools |

These references will be cited in the per-step design docs (D2/D3/D4
below). We will **not** clone, install, or import any of these
runtime libraries without a separate, reviewed sign-off.

---

## 4. Proposed schema (NOT created in D0)

These tables are designed but NOT migrated tonight. The actual
SQLAlchemy models + Alembic-style migration land in step **D1**.

### 4.1 `scanner_run`

The umbrella record for one full scanner+alpha pass.

| Column | Type | Notes |
|---|---|---|
| `run_id` | UUID PK | new UUID per pass |
| `mode` | enum | `manual_research` / `nightly` (D7+) |
| `triggered_by` | varchar(64) | `cli` / `api` / `scheduler` |
| `universe` | varchar(64) | `scanner-research` (today's only universe) |
| `as_of_date` | date | EOD date the pass uses |
| `instrument_count` | int | sanity (should be 36) |
| `started_at` / `completed_at` | timestamptz | wall-clock |
| `error_summary` | text NULL | bounded |
| `status` | enum | `planned` / `running` / `completed` / `failed` |

### 4.2 `scanner_candidate_snapshot`

One row per (run, instrument). The *deterministic* scanner output
plus a foreign key to the alpha prediction (if any).

| Column | Type | Notes |
|---|---|---|
| `snapshot_id` | UUID PK | |
| `run_id` | UUID FK → `scanner_run` | |
| `instrument_id` | UUID FK → `instrument` | |
| `signal_strength` | enum | `low / medium / high` (existing) |
| `scan_types` | jsonb | existing `SCAN_TYPES` whitelist |
| `risk_flags` | jsonb | existing `RISK_FLAGS` whitelist |
| `volume_ratio` | numeric NULL | |
| `change_1d_pct` / `5d` / `1m` | numeric NULL | existing fields |
| `week52_position_pct` | numeric NULL | existing |
| `recommended_next_step` | enum | existing whitelist |
| `explanation` | text | existing — already BANNED_WORDS-gated |
| `alpha_prediction_id` | UUID FK → `alpha_prediction_shadow` NULL | shadow only |
| `created_at` | timestamptz | |

### 4.3 `alpha_feature_snapshot`

PIT-correct feature row used at training AND inference time. Exactly
one row per (instrument, feature_set_version, as_of_date).

| Column | Type | Notes |
|---|---|---|
| `snapshot_id` | UUID PK | |
| `instrument_id` | UUID FK | |
| `as_of_date` | date | the date these features describe |
| `feature_set_version` | varchar(32) | e.g. `fs_v1` |
| `features` | jsonb | strict, additive-only — see §6 |
| `feature_source_signature` | varchar(64) | hash of (provider versions, library versions) |
| `created_at` | timestamptz | |

UNIQUE constraint: `(instrument_id, feature_set_version, as_of_date)`.

### 4.4 `alpha_label_snapshot`

The supervised label paired with a feature snapshot. Materialized
ONCE per (instrument, label_set_version, as_of_date) and never
recomputed in place.

| Column | Type | Notes |
|---|---|---|
| `label_id` | UUID PK | |
| `instrument_id` | UUID FK | |
| `as_of_date` | date | training-time anchor |
| `label_set_version` | varchar(32) | e.g. `ls_v1` |
| `labels` | jsonb | see §5 — includes triple-barrier outcomes |
| `lookforward_horizon_days` | int | 5 / 10 / 20 |
| `is_realized` | bool | true once the lookforward window has fully closed |
| `created_at` | timestamptz | |

### 4.5 `alpha_model_run`

One row per training run. Frozen artifact path under
`data/artifacts/alpha-lab/<run_id>/`. Models live OUTSIDE the
existing `data/artifacts/learning-models/` so the lightweight
intent-classifier promotion gate cannot touch them.

| Column | Type | Notes |
|---|---|---|
| `model_run_id` | UUID PK | |
| `model_family` | enum | `linear` / `gbm` / `random_forest` / `mlp_small` (CPU only; no GPU LLM) |
| `model_version` | varchar(32) | e.g. `surge-watch-v1` |
| `feature_set_version` | varchar(32) | FK-style ref (logical) |
| `label_set_version` | varchar(32) | FK-style ref (logical) |
| `train_start_date` / `train_end_date` | date | |
| `oos_start_date` / `oos_end_date` | date | walk-forward holdout |
| `metrics` | jsonb | see §7 |
| `artifact_path` | text | `data/artifacts/alpha-lab/<id>/model.joblib` |
| `is_frozen` | bool | true once training completes; never overwritten |
| `safety_tier` | enum | `shadow_only` / `surface_in_ui` (operator must flip) |
| `created_at` | timestamptz | |

### 4.6 `alpha_prediction_shadow`

Per (snapshot, model) prediction. Default tier `shadow_only` — the
prediction is recorded but NOT shown in the UI until the operator
flips the model's `safety_tier` to `surface_in_ui`.

| Column | Type | Notes |
|---|---|---|
| `prediction_id` | UUID PK | |
| `model_run_id` | UUID FK | |
| `instrument_id` | UUID FK | |
| `as_of_date` | date | scoring-time anchor |
| `surge_watch_score` | numeric(6,4) | 0.0000–1.0000 |
| `research_priority` | int | 1–5 bucket from score |
| `feature_signature` | varchar(64) | hash of features used |
| `is_visible_in_ui` | bool | mirror of model's `safety_tier == surface_in_ui` at write time |
| `created_at` | timestamptz | |

### Side-effect attestations (schema layer)

- All schema-layer writes happen ONLY through new files under
  `libs/alpha_lab/` (planned in D1). The existing scanner +
  ingestion code paths are untouched.
- No table touches `order_intent`, `order_draft`, `broker_*`, or any
  T212 / execution surface.
- `alpha_model_run.artifact_path` is *always* under
  `data/artifacts/alpha-lab/`. The lightweight-classifier promotion
  gate (Toni-style, future) MUST NOT reach this directory.

---

## 5. Labels (proposed, NOT computed in D0)

We materialize multiple labels per (instrument, as_of_date) so the
same feature row can train models for different horizons / definitions.

### 5.1 Magnitude labels

| Label | Definition |
|-------|-----------|
| `surge_5d_10` | 1 if `max(close[t+1..t+5]) / close[t] − 1 ≥ 0.10`, else 0 |
| `surge_10d_20` | 1 if `max(close[t+1..t+10]) / close[t] − 1 ≥ 0.20`, else 0 |
| `surge_20d_30` | 1 if `max(close[t+1..t+20]) / close[t] − 1 ≥ 0.30`, else 0 |

Bucket thresholds (10 / 20 / 30 %) are deliberately coarse so
class imbalance stays manageable on a 36-ticker universe.

### 5.2 Continuous regression targets

| Label | Definition |
|-------|-----------|
| `max_return_5d` | `max(close[t+1..t+5]) / close[t] − 1` |
| `max_return_10d` | analogous |
| `max_return_20d` | analogous |

### 5.3 Triple-barrier variants (López de Prado)

For each upper threshold `u` (e.g. 0.10) and lower threshold `l`
(e.g. −0.05), record:

| Label | Definition |
|-------|-----------|
| `tb_5d_u10_l5_label` | +1 if upper hit first within 5 trading days, −1 if lower hit first, 0 if neither (timeout) |
| `tb_10d_u20_l10_label` | analogous, 10 trading days |
| `tb_20d_u30_l15_label` | analogous, 20 trading days |
| `max_drawdown_before_hit` | for samples where the upper hit, the worst close-vs-entry drawdown observed before the hit |
| `days_to_hit` | trading days until the upper barrier hit (NULL if not hit) |

`max_drawdown_before_hit` and `days_to_hit` give the operator a
read on path quality, not just terminal magnitude.

### Critical PIT / leakage rules

- `as_of_date` for a label row is the day whose features the label
  describes. Lookforward bars MUST NOT be included in the feature
  set.
- A label row is `is_realized=False` until day `t + lookforward + 2`
  to absorb late-arriving Polygon / FMP corrections.
- All training runs filter `WHERE is_realized = TRUE`.

---

## 6. Feature set v1 (proposed, NOT computed in D0)

All features computed from `price_bar_raw` ONLY. No fundamentals,
no macro, no news in v1. PIT-correct: every feature uses bars whose
`trade_date ≤ as_of_date`.

### 6.1 Returns

| Feature | Definition |
|---------|-----------|
| `return_1d` | `close[t]/close[t-1] − 1` |
| `return_5d` | `close[t]/close[t-5] − 1` |
| `return_20d` | `close[t]/close[t-20] − 1` |

### 6.2 Volatility

| Feature | Definition |
|---------|-----------|
| `volatility_20d` | stdev of daily log returns over 20 trading days |
| `volatility_60d` | stdev of daily log returns over 60 trading days |

### 6.3 Volume

| Feature | Definition |
|---------|-----------|
| `volume_ratio_20d` | `volume[t] / mean(volume[t-19..t])` |
| `volume_ratio_60d` | `volume[t] / mean(volume[t-59..t])` |

### 6.4 Position in range

| Feature | Definition |
|---------|-----------|
| `week52_position` | `(close[t] − min_52w) / (max_52w − min_52w)`; NULL if range degenerate |
| `distance_to_20d_high` | `1 − close[t] / max(close[t-19..t])` |
| `distance_to_52w_high` | `1 − close[t] / max(close[t-251..t])` |

### 6.5 Relative strength

| Feature | Definition |
|---------|-----------|
| `relative_strength_vs_SPY_5d` | `return_5d(instrument) − return_5d(SPY)` |
| `relative_strength_vs_QQQ_5d` | analogous, vs QQQ |

### 6.6 Microstructure

| Feature | Definition |
|---------|-----------|
| `gap_pct` | `open[t] / close[t-1] − 1` |
| `atr_14` | average true range over 14 days |
| `bb_position_20` | (close − 20d_lower_band) / (20d_upper − 20d_lower) |
| `momentum_acceleration_5d` | `return_1d[t] − mean(return_1d[t-5..t-1])` |

### Feature hygiene

- All features clipped at finite percentiles (e.g. 0.5/99.5) on the
  *training* set; the same clip thresholds applied at scoring time.
- NULL handling explicit: rows with required-feature NULL are not
  scored. Optional-feature NULLs become an explicit indicator
  feature (`<name>_isnull`).
- Feature versioning: any change to a definition increments
  `feature_set_version`. We never silently mutate `fs_v1`.

---

## 7. Evaluation (proposed, NOT run in D0)

### 7.1 Walk-forward split

For 13k+ EOD bars across 36 instruments (~370 bars/ticker), we use
**expanding-window walk-forward** with monthly steps:

```
Fold 0: train [t0, t0+9mo]   → OOS [t0+9mo+1, t0+10mo]
Fold 1: train [t0, t0+10mo]  → OOS [t0+10mo+1, t0+11mo]
...
```

This preserves PIT, avoids leakage, and exposes regime drift.

### 7.2 Headline metrics

For each fold, store in `alpha_model_run.metrics`:

| Metric | Definition |
|--------|-----------|
| `precision_at_top_5` | fraction of the 5 highest-scored instruments whose magnitude label is 1 |
| `precision_at_top_10` | analogous, top 10 |
| `avg_max_return_5d_top_5` | mean of `max_return_5d` over the top-5 picks |
| `avg_max_drawdown_before_hit_top_5` | mean of pre-hit drawdown for the top-5 picks where the upper barrier hit |
| `avg_days_to_hit_top_5` | mean days-to-hit for top-5 picks where upper barrier hit |
| `false_positive_rate_top_5` | fraction of top-5 picks with magnitude label 0 |
| `auc_roc` | classifier AUC on the binary `surge_5d_10` label |

The `_top_5` / `_top_10` framing matters because the operator can
only meaningfully research a handful of names per day.

### 7.3 Aggregation

Cross-fold means + medians + 25/75 percentiles are stored. We
report **out-of-sample only**. In-sample metrics are NEVER
exposed to the UI.

### 7.4 Bar for "surface in UI"

A model only earns `safety_tier = surface_in_ui` when:

- `precision_at_top_5` median across folds ≥ 0.40
- `avg_max_return_5d_top_5` median across folds ≥ 0.05
- `false_positive_rate_top_5` median across folds ≤ 0.40
- `n_walk_forward_folds ≥ 6`

Any miss → stays `shadow_only`. Operator override requires an
explicit, timestamped row in a future `alpha_model_promotion_log`.

---

## 8. Rollout (D1 → D8, all gated)

Each step is a separate, reviewed PR. Phase D0 (this doc) ships
docs only. No DB writes, no code, no deploy.

| Step | Scope | Notes / acceptance |
|------|-------|---------|
| **D1 — Persistence** | Add the 6 tables from §4. SQLAlchemy models + Alembic-style migration + ON CONFLICT idempotency. | New tables only. No data backfill. Existing tables untouched. Unit tests cover schema + UNIQUE constraints. |
| **D2 — Labels** | Materializer that scans `price_bar_raw` and writes `alpha_label_snapshot` rows for each (instrument, label_set_version, as_of_date). Backfill is a separate one-shot CLI, not a scheduler. | Idempotent. `is_realized` correctly transitions when lookforward window closes. PIT test suite. |
| **D3 — Features** | Materializer that writes `alpha_feature_snapshot` rows for `feature_set_version='fs_v1'`. | Same idempotency + PIT discipline. Source guard refuses any future fundamental/macro feature without an explicit `fs_v2`. |
| **D4 — Offline model** | Train a single CPU-only baseline (`linear` + `gbm`) on `fs_v1 × ls_v1`. Frozen artifact under `data/artifacts/alpha-lab/<run_id>/`. | `safety_tier='shadow_only'` by default. Hermetic unit tests for the trainer. |
| **D5 — Walk-forward evaluation** | Run §7 walk-forward across the entire history. Persist metrics in `alpha_model_run`. | Eval is read-only against existing tables; never writes price_bar_raw. |
| **D6 — Shadow mode** | Daily / on-demand scoring writes `alpha_prediction_shadow` rows. UI does NOT yet show them. | Operator can review predictions vs realized labels in a "shadow report" Markdown export. |
| **D7 — UI score (opt-in)** | When operator flips `safety_tier='surface_in_ui'`, the existing Scanner page surfaces `surge_watch_score` + `research_priority` + the OOS eval summary. | `BANNED_WORDS` + Pydantic `extra="forbid"` extended to the new fields. The scanner explanation is unchanged; the new fields appear as a separate badge. |
| **D8 — Larger universe** | Add fundamentals / macro / cross-sectional features (`fs_v2`) AND/OR expand beyond 36 tickers. | Out-of-scope for D1–D7; tracked here so we don't accidentally over-fit `fs_v1` to the small universe. |

### Hard freeze rules across D1–D8

- D1 cannot land before C2 declares stable (≥5 ticks PASS).
- Each step's commit is docs-or-code-or-data, never multi-purpose.
- Every step's PR description must include the side-effect
  attestation block (DB writes / jobs / scheduler / deploy /
  execution / broker / live submit).

---

## 9. Safety

| Item | Status |
|------|--------|
| Execution objects (`order_intent` / `order_draft`) | NEVER written by alpha lab |
| Broker writes | NEVER. Trading 212 stays read-only. |
| `FEATURE_T212_LIVE_SUBMIT` | remains `false`, untouched by alpha lab |
| Trading-action language in outputs | forbidden; reuses existing `BANNED_WORDS` source pin |
| Auto-trading | not implemented, not designed, not on roadmap |
| Model artifacts | local-only, under `data/artifacts/alpha-lab/`, frozen, never auto-promoted |
| Promotion to UI | requires explicit operator flip of `safety_tier`, with min-fold + min-precision gates from §7.4 |
| Off switch | one feature flag (`FEATURE_ALPHA_LAB_VISIBLE`, env-default `false`) hides ALL alpha-lab UI surfaces |
| Dependency footprint | scikit-learn + numpy + pandas only in v1; no PyTorch / no GPU; no openai / anthropic / google.generativeai imports anywhere on the alpha-lab path |

### Forbidden language in alpha-lab outputs (extension of existing BANNED_WORDS)

- `buy now`, `sell now`, `target price`, `position size`, `stop loss`,
  `take profit`, `entry`, `exit`, `enter long`, `enter short`,
  `guaranteed`
- 中文：买入 / 卖出 / 目标价 / 仓位 / 必涨 / 入场时机 / 建仓

These are pinned in tests at every step that produces user-facing
text (D6 shadow report; D7 UI badge tooltips; future D8 narrative
layer).

### Forbidden runtime imports on the alpha-lab path

- `openai`, `anthropic`, `google.generativeai`
- `torch`, `peft`, `transformers.AutoModelFor*`, `bitsandbytes`
- Any GitHub clone / install / arbitrary subprocess invocation
- Any `gh` write subcommand (`gh pr create`, `gh repo create`, …)

These are guarded by a future
`tests/unit/test_alpha_lab_safety_source_guards.py` analogous to
the existing `test_stock_scanner.py::TestExplanationGuardrail`.

---

## 10. Open questions (parked for D1+)

- **Universe size**: 36 tickers is small for an ML model. Do we
  expand the scanner universe in D8, or keep it small and lean on
  cross-sectional features carefully? (Default plan: keep 36 in
  D1–D7; revisit at D8.)
- **Label imbalance**: a 10% surge in 5 days is rare on most names.
  Class-weighting / focal loss / cost-sensitive eval will need
  attention in D5.
- **Provider drift**: Polygon vs FMP fallback can shift bar values
  fractionally. The `feature_source_signature` hash captures
  provider-version differences, but we should also pin a
  `(provider, last_known_correction_id)` snapshot per fold.
- **Operator UX**: where in the Scanner page does the
  `research_priority` badge live? (Default plan: as a small badge
  next to `signal_strength`, with a tooltip showing `surge_watch_score`,
  `n_walk_forward_folds`, and `precision_at_top_5`.)
- **Eval cadence**: refresh walk-forward eval daily after the EOD
  sync (Phase C), weekly, or only on demand? (Default plan: on-
  demand in D5, daily after-sync in D6 once shadow mode is stable.)

---

## 11. What Phase D0 EXPLICITLY does NOT do

> Phase D0 is documentation only.
>
> - No DB tables created.
> - No code written.
> - No models trained.
> - No deploy.
> - No new Cloud Run Jobs.
> - No new Cloud Schedulers.
> - No change to `quant-sync-eod-prices` / `quant-sync-eod-prices-schedule`.
> - No change to `quant-sync-t212` / `quant-sync-t212-schedule`.
> - No execution objects.
> - No broker writes.
> - `FEATURE_T212_LIVE_SUBMIT` remains `false`.
> - Phase C2 observation window remains undisturbed.
>
> Phase D1 (persistence migration) requires a separate, explicit
> sign-off in chat from the user.

---

## Appendix A — File / module layout (proposed for D1+)

```
libs/alpha_lab/                       # NEW package, zero overlap with libs/scanner
    __init__.py
    schemas.py                        # SQLAlchemy + Pydantic alpha-lab models
    labels.py                         # D2 — label materializer
    features.py                       # D3 — feature materializer
    walkforward.py                    # D5 — split + metric helpers
    train.py                          # D4 — CPU-only training pipeline
    score.py                          # D6 — shadow-mode scoring
    promote.py                        # D7 — safety_tier flip + audit
tests/unit/
    test_alpha_lab_schemas.py
    test_alpha_lab_labels.py
    test_alpha_lab_features.py
    test_alpha_lab_walkforward.py
    test_alpha_lab_safety_source_guards.py
data/artifacts/alpha-lab/<model_run_id>/
    model.joblib
    metrics.json
    walkforward.csv
docs/
    scanner-alpha-lab-roadmap.md       # this file
    scanner-alpha-lab-d1-design.md     # written before D1 starts
    scanner-alpha-lab-eval-readme.md   # written before D5 starts
```

The deterministic Scanner code under `libs/scanner/` is **not** moved
or renamed. The alpha lab is purely additive.

---

## Appendix B — References (read-only inspiration, not runtime deps)

- Microsoft Qlib — <https://github.com/microsoft/qlib>
- Microsoft RD-Agent — <https://github.com/microsoft/RD-Agent>
- vectorbt — <https://github.com/polakowo/vectorbt>
- FreqAI (within Freqtrade) — <https://www.freqtrade.io/en/stable/freqai/>
- MLFinLab — <https://github.com/hudson-and-thames/mlfinlab>
- ta — <https://github.com/bukosabino/ta>
- pandas-ta — <https://github.com/twopirllc/pandas-ta>
- OpenBB — <https://github.com/OpenBB-finance/OpenBBTerminal>
- FinRobot — <https://github.com/AI4Finance-Foundation/FinRobot>
- TradingAgents — <https://github.com/TauricResearch/TradingAgents>

These are referenced for ideas only. No code from any of these
repositories will be cloned, installed, executed, or imported into
this codebase without a separate, reviewed sign-off.
