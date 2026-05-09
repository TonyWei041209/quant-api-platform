# Prediction Model Shadow Roadmap

Status: P9 of overnight authorization. Documentation only tonight. No code, no model artifact. **Hard policy: no UI exposure.**

## 1. Context

Test #1 (eval committed `65d8239`) showed the deterministic momentum heuristic at 4.5 % overall direction accuracy on a 22-ticker single-day pilot. That is calibration evidence, not model accuracy — but it is enough to say the heuristic alone should not be promoted to a user-visible signal. Anything beyond it must be a **model**, evaluated rigorously, and gated behind a feature flag that defaults OFF.

This doc fixes the rules for any future model-prototype work so we don't drift.

## 2. Hard policy (NEVER negotiable)

1. **No UI exposure.** `FEATURE_ALPHA_PREDICTION_VISIBLE=false` in production. The frontend must hard-code the prediction column / chip / score as hidden even if a value is computed and persisted. Test must pin this.
2. **No execution integration.** Prediction outputs MUST NOT flow into `order_intent` / `order_draft` or any other execution-side object. Source-grep guard required.
3. **No scheduler.** No prediction model job runs on a Cloud Scheduler in production until at least 60 days of shadow evaluation evidence accumulates.
4. **No trading language.** Even internally — model code, comments, docs, log lines — must use research-only vocabulary (`anomaly_score`, `research_priority`, `catalyst_score`).
5. **Promotion gate is a NoOp.** A constant `PREDICTION_PROMOTION_ALLOWED = False` literal in code. Flipping it requires a separate dedicated commit + review.
6. **Walk-forward only.** No in-sample backtest results may ever be cited as model accuracy.

## 3. Phase split

### P9.1 — Feature schema (docs only — done in this commit)

Documented features, all derivable from `price_bar_raw` + `broker_*_snapshot` + `earnings_event` + `news_*` (none yet) + `taxonomy_tags`:

```
ret_1d, ret_5d, ret_1m, ret_3m
volume_ratio_5d, volume_ratio_20d
volatility_5d, volatility_20d
range_52w_position, distance_to_52w_high
momentum_acceleration = ret_5d - 0.2*ret_1m
relative_strength_vs_spy, relative_strength_vs_qqq
relative_strength_vs_sector_etf
earnings_within_7d (bool), earnings_in_3d (bool)
recent_news_count_7d, news_recency_hours
mirror_source_tags_one_hot (HELD/RECENTLY_TRADED/WATCHED/UNMAPPED)
mapping_status_one_hot
taxonomy_broad_one_hot, taxonomy_sub_one_hot
```

### P9.2 — Label schema (docs only — done in this commit)

Three label families, evaluated separately:

| Label | Definition | Why |
|---|---|---|
| `surge_5d_10` | 1 if ret_5d ≥ 10 % AND ret_5d > max(0, ret_5d_market_avg) | mirrors what users actually look for: outsized moves vs market |
| `direction_5d` | sign of ret_5d (down / flat / up) with ±2 % flat band | direction-only baseline for comparison with Test #1 |
| `triple_barrier` | first of: +5 % up barrier, −5 % down barrier, 5d timeout | Lopez de Prado classic; rules out trivial autocorrelation |

### P9.3 — Walk-forward eval (later phase)

Bands:
- Train: trailing 252 trading days
- Validation: next 21 trading days
- Test: held-out final 21 days (NEVER touched during model selection)

Step forward by 21 days; refit each step. Report:
- Direction accuracy by partition (taxonomy / regime / confidence bucket)
- Bucket accuracy
- Calibration (Brier score)
- Surge precision / recall at top decile
- Confidence calibration error
- Cumulative anomaly-rank-IC (information coefficient) across the test windows

### P9.4 — Baselines (later phase)

Three baselines, in order of complexity:

1. **Logistic regression** on the standardized feature set. Fast, interpretable; the floor any non-trivial model must beat.
2. **Random forest** (sklearn `RandomForestClassifier`, 100 trees, max_depth=8). Already-installed dependency.
3. **Gradient boosting** (sklearn `HistGradientBoostingClassifier` or LightGBM if dependency added). Higher-capacity but with calibration overhead.

A model is **considered for shadow promotion** only after beating BOTH:
- Logistic regression on the same window
- The deterministic heuristic from Test #1 by ≥ 5 percentage points of direction accuracy across ≥ 5 walk-forward windows

It does NOT promote to UI.

### P9.5 — Storage

Model artifacts live in a **gitignored** local path: `data/artifacts/alpha-lab/`. Production has no model artifact file at this stage.

Predictions are persisted (when generated) into a future `alpha_prediction_shadow` table (deferred — D2/D3 of the alpha lab roadmap). For now, the eval flow re-runs the heuristic / model live against the eval-target bar; nothing is materialised in the DB yet.

## 4. Tonight's deliverable

- This roadmap document.
- A pinned `FEATURE_ALPHA_PREDICTION_VISIBLE` flag in `libs/core/config.py` defaulting `false` (already exists implicitly; no code change needed if not yet referenced).

That's it. No model code, no artifact, no schema. The hard rules are documented so that any future PR has to honor them.

## 5. Side-effect attestations

| | Tonight |
|---|---|
| Production DB write | NONE |
| Schema change | NONE |
| Trading 212 write | NONE |
| Live submit | LOCKED |
| Order/execution objects | NONE |
| Scraping / browser automation | NONE |
| `.firebase` commit | NO |
| New code shipped | NONE |
