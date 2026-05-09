# Prediction Shadow Evaluation Framework

Status: design doc (P5 of overnight authorization). Test #1 evaluation already completed (commit `65d8239`); this framework formalises the rules for Test #2 onward.

## 1. Why a framework

Test #1 used ad-hoc rules baked into a transient script. The result (overall direction accuracy 1/22 = 4.5 %) made the failure mode visible immediately, but the eval flow has to be auditable and re-runnable for any future test. This doc fixes the rules.

## 2. Hard rules

1. **Pre-registration must exist BEFORE the eval target bar is finalized.** The pre-registration commit hash, master HEAD at pre-reg time, and the timestamp in the pre-reg doc must be cited in the eval doc.
2. **Eval target = first newly-inserted bar after `prediction_created_at_utc`.** If multiple bars were inserted in one tick, evaluate against the earliest.
3. **No prediction promotion.** A passing eval does NOT cause any UI surface, scanner explanation, or scheduler change. It is calibration evidence only.
4. **No retrospective predictions.** A test where the target bar already existed at pre-registration time is **retrospective only** and must be labeled as such in the title — never described as a "forward shadow test".
5. **Failed predictions are kept.** No scrubbing, no cherry-picking, no late edits to the pre-registration. The doc-blob hash at the original commit must equal the doc-blob hash at eval time (verified by `git rev-parse <commit>:<file>` comparison — Test #1 eval already did this).

## 3. Pre-registration integrity check

Always run:
```
PRE_HASH=$(git rev-parse <pre-reg-commit>:<pre-reg-doc>)
HEAD_HASH=$(git rev-parse HEAD:<pre-reg-doc>)
test "$PRE_HASH" = "$HEAD_HASH"  # MUST pass
```
A mismatch is a hard fail and the eval must NOT be written.

## 4. Per-prediction metrics

| Metric | Definition |
|---|---|
| `actual_return_pct` | `(actual_close / as_of_close − 1) × 100` |
| `direction_hit` | sign of `actual_return_pct` matches predicted_direction; `flat` ⇔ \|actual\| < 2 |
| `bucket_hit` | `actual_return_pct` falls inside the predicted bucket interval |
| `absolute_error_pct` | \|actual_return_pct − bucket_midpoint\| (midpoints: below_minus_2=−4, minus_2_to_plus_2=0, plus_2_to_plus_5=3.5, above_plus_5=7.5) |
| `surge_3pct_hit` | actual_return_pct ≥ 3 |
| `surge_5pct_hit` | actual_return_pct ≥ 5 |
| `confidence_calibration_error` | \|empirical_hit_rate(confidence_bucket) − stated_confidence_score\| |

## 5. Aggregate metrics

Reported separately for **each partition**:
- in_universe vs external_ephemeral
- by `taxonomy_tags.broad` (P1) — Technology / Healthcare / Financials / etc.
- by `taxonomy_tags.subs` (P1) — AI Infrastructure / Memory Chips / Space-Rocket / etc.
- by market regime: SPY 1-day move bucket on the eval target day (`risk_off`, `flat`, `risk_on`)
- by predicted confidence bucket: high / medium / low

For each partition:
- `direction_accuracy = mean(direction_hit)`
- `bucket_accuracy = mean(bucket_hit)`
- `mean_absolute_error_pct`
- `surge_3pct_hit_rate`, `surge_5pct_hit_rate`
- `unresolved_count`
- `n` (sample size — almost always too small for inference; the doc must say so)

## 6. False positive / missed surge review

The eval doc should call out:
- **False bullish calls during a risk-off day** (e.g., Test #1: 14 of 17 `up` calls negative)
- **Missed surges** (e.g., Test #1: DUOL +8.18 % was predicted `flat`)
- **Confidence miscalibration** — high-confidence rows that were wrong (Test #1: MRVL/RKLB/IREN/NBIS as `high` confidence with −5 % to −7 % actuals)

## 7. Retrospective vs forward labelling

| Pre-reg created | Eval target bar | Label |
|---|---|---|
| BEFORE target bar finalised | trade_date strictly later than `floor(prediction_created_at_utc)` | **forward shadow test** |
| AFTER target bar finalised | trade_date earlier than `ceil(prediction_created_at_utc)` | **retrospective only** — no inference about future model behavior |

Mixed cases (some predictions forward, some retrospective) must split partitions and label each accordingly.

## 8. No model promotion

A passing eval does NOT trigger:
- ❌ UI surface change (predictions stay hidden behind `FEATURE_ALPHA_PREDICTION_VISIBLE=false`)
- ❌ Scanner explanation language change
- ❌ Scheduler frequency change
- ❌ Default-on toggling of any prediction feature

A failing eval MUST be recorded permanently and cited in the next pre-registration as prior evidence. Test #1's 4.5 % accuracy is now permanent calibration evidence.

## 9. Eval doc template

```markdown
# Prediction Shadow Test #N — Evaluation

Pre-registration honored: commit <hash>
Eval target trade_date: <YYYY-MM-DD>
C2 tick that finalised the target bar: <execution_name>
Eval written at: <timestamp>

## 1. C2 tick — sync result
(insert sync_result block from Cloud Run logs)

## 2. Guardrails (PASS list)
(API health, FEATURE_T212_LIVE_SUBMIT, jobs, schedulers, exec object counts)

## 3. Data source
(Yahoo public / production DB read-only / etc., with rationale for the choice)

## 4. Per-prediction results
(table of rows from §4)

## 5. Aggregate metrics — pilot observation, NOT model accuracy
(table per partition from §5)

## 6. False positive / missed surge review

## 7. Reading
(narrative — what does this round mean? Almost always: "single-day pilot,
below inference threshold, no promotion implied")

## 8. Forbidden-language audit
(grep result over this doc; banned terms must only appear in negations)

## 9. Strict side-effect attestations

## 10. Audit chain
```

## 10. Optional script

When ready to formalise, add `scripts/evaluate_prediction_shadow.py`:
- Reads a pre-registration markdown table (regex parse).
- Re-fetches actual closes via the same data source the pre-reg used.
- Computes the per-prediction + aggregate metrics from §4 and §5.
- Verifies the pre-registration doc-blob hash matches the cited commit.
- Emits a markdown skeleton matching the §9 template; the human still writes the §7 narrative.

This script is **not** added in P5. The transient script approach used in Test #1 is acceptable for now; we'll formalise once the third test exists and we have enough variation to know what the script needs to handle.

## 11. Side-effect attestations for any eval round

| | Status |
|---|---|
| Production DB writes | NONE |
| Manual sync executions | NONE |
| Scheduler changes | NONE |
| Trading 212 write endpoints | NONE |
| Live submit | LOCKED |
| Order/execution objects | NEVER created |
| Scraping / browser automation | NEVER used |
| Pre-registration doc edits | NEVER allowed; verified by blob-hash check |
| `.firebase` cache | NOT committed |
