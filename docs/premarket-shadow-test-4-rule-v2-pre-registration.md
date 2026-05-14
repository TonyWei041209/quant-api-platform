# Premarket Shadow Test #4 — Rule v2 Pre-registration

**Status:** PRE-REGISTRATION (forward-looking only).
**Author of registration:** automated agent, operator-authorised.
**Pre-registered at (UTC):** `2026-05-14T00:55:00Z`
**Applies to:** the **next** premarket prediction run, no earlier than
the next US-trading-day pre-open window (target trade-date `T` is
chosen at execution time and recorded in the run's own JSON).
**Does NOT modify:** any of the 2026-05-12 artifacts:

* `docs/premarket-shadow-prediction-20260512.json` (canonical v1
  prediction) — **frozen**
* `docs/premarket-shadow-prediction-20260512.md` — frozen
* `docs/premarket-shadow-prediction-20260512-eval.md` (incl. the
  appended `§7 Results`) — frozen
* `docs/platform-prediction-accuracy-20260512-final.md` — frozen

> **Research-only.** This is a calibration exercise. The platform
> NEVER issues buy/sell/target/position guidance. The predictions
> produced under this rule live in docs JSON only and are NEVER
> surfaced as a user-facing trading signal. `FEATURE_T212_LIVE_SUBMIT`
> remains `false`. No `order_intent` / `order_draft` is created at
> any point in this test cycle.

---

## 1. Hypothesis

The Shadow v1 ruleset (per
`docs/premarket-shadow-prediction-20260512.md`) was falsified on its
first evaluable trading day (`direction_accuracy = 1/15 = 6.7 %`).
The four root causes identified in
`docs/platform-prediction-accuracy-20260512-final.md §7.4` are
addressable by the v2 changes below. **The hypothesis under test is:**

> Adding a market-regime gate, mapping `composite=0` arising from an
> extension dampener to `down` (not `flat`), introducing a
> downside-override path, filtering out un-evaluable tickers BEFORE
> the prediction, and allowing a 4-state direction
> (`up / flat-up / flat-down / down`) will produce a measurably
> better next-day direction accuracy than the v1 baseline of 6.7 %,
> while keeping all rule logic deterministic, all language
> research-only, and confidence honest.

The success threshold for accepting v2 as not-yet-falsified is
defined in §11 (Decision rule). Failure to clear the threshold opens
a Shadow Test #5 with another pre-registration — **never** an
in-place rule edit.

## 2. Data sources

Inputs are the same as v1 — no new providers, no new credentials:

| Input | Source |
|---|---|
| Per-ticker `change_1d_pct`, `change_5d_pct`, `change_1m_pct`, `week52_position_pct`, `volume_ratio`, `signal_strength`, `risk_flags`, `scan_types` | the latest persisted overnight `market_brief_run` candidate snapshot (i.e. `market_brief_candidate_snapshot.payload_json.price_move + .scanner`) |
| Per-ticker `recent_news_count`, `upcoming_earnings_count`, `source_tags`, `mapping_status`, `taxonomy` | same brief snapshot |
| **Market regime probe** (new in v2) | the brief snapshot's own `SPY` and `QQQ` rows (already in scanner-research-36). No extra provider call. |
| Eligibility anchor | production DB `price_bar_raw` rows for `T-1` (the previous trading day); used **only** to confirm we can evaluate a ticker post-close, not to fetch any forecast |
| Actuals (post-close, for §10 eval only) | production DB `price_bar_raw` for `T-1` and `T` closes. **NO** external web prices. |

No T212 endpoint, no broker call, no new HTTP. The brief snapshot the
rule reads is the one already persisted by the
`quant-market-brief-overnight` scheduled job.

## 3. Eligibility rules (NEW in v2)

A ticker enters the prediction set only if **all** of:

1. `mapping_status == "mapped"` in the brief snapshot.
2. `price_bar_raw` contains a row for `trade_date = T-1` for this
   ticker's `instrument_id`. (The actual provider close used for
   evaluation must already be in the DB by prediction time, so we
   know the eval is achievable.)
3. `change_1d_pct` is not null.

Tickers failing any of these three checks go to a separate
**watch-only list** in the same JSON (`watch_only[]`), with a
`reason` field. They are **excluded** from the accuracy denominator
both directionally and bucket-wise. They are **not** counted as
"wrong" predictions.

Rationale: the v1 eval had 11 of 26 rows excluded (7
mirror-bootstrap bar-less + 4 unmapped). The eval correctly excluded
them at *eval* time, but the prediction JSON still listed them with
`predicted_direction=flat`, which is misleading. v2 separates them up
front.

## 4. Prediction generation time gate

Same as v1:

* MUST be generated strictly before the US regular-session open at
  `T 13:30 UTC` (or `T 12:30 UTC` during DST shift if applicable).
* The `preregistered_at` timestamp in the run's JSON MUST be less
  than the US open of `T`.
* A run generated after the open is invalid and is discarded.

## 5. Market regime feature (NEW in v2)

Computed once per run from the latest persisted brief snapshot
(no extra HTTP call):

```python
spy_d1 = brief.candidates['SPY'].price_move.change_1d_pct  # or None
qqq_d1 = brief.candidates['QQQ'].price_move.change_1d_pct  # or None
spy_d5 = brief.candidates['SPY'].price_move.change_5d_pct
qqq_d5 = brief.candidates['QQQ'].price_move.change_5d_pct

REGIME_NEGATIVE_THRESHOLD = -1.0   # %
REGIME_POSITIVE_THRESHOLD = +1.0   # %
REGIME_5D_NEG = -2.0               # %
REGIME_5D_POS = +2.0               # %

if spy_d1 is None or qqq_d1 is None:
    regime = "unknown"
elif spy_d1 <= REGIME_NEGATIVE_THRESHOLD AND qqq_d1 <= REGIME_NEGATIVE_THRESHOLD:
    regime = "negative"   # broad risk-off
elif spy_d1 >= REGIME_POSITIVE_THRESHOLD AND qqq_d1 >= REGIME_POSITIVE_THRESHOLD:
    regime = "positive"   # broad risk-on
elif spy_d5 <= REGIME_5D_NEG AND qqq_d5 <= REGIME_5D_NEG:
    regime = "negative_5d"  # weekly drift down even if today mixed
else:
    regime = "neutral"
```

`regime` is one of `negative | negative_5d | neutral | positive | unknown`.

This is one signal per run, NOT per ticker. It enters the §7
composite as `regime_signal ∈ {-1, 0, +1}`:

| `regime` | `regime_signal` |
|---|---|
| `negative` | -1 |
| `negative_5d` | -1 |
| `neutral` | 0 |
| `positive` | +1 |
| `unknown` | 0 (fail-safe; do not bias) |

## 6. Per-ticker factor definitions

`momentum_signal` (revised from v1):

```python
if change_1d_pct >= +2.0:
    momentum = +1
elif change_1d_pct <= -2.0:
    momentum = -1
else:
    momentum = 0
```

`extension_signal` (revised — now both-sides; v1 was only negative-bias):

```python
extension = 0
if week52_position_pct >= 95 AND change_1d_pct >= 8:
    extension = -1   # extended after big single-day pop → mean-reversion bias
elif week52_position_pct <= 5 AND change_1d_pct <= -8:
    extension = +1   # capitulation after big single-day drop → bounce bias
```

`news_signal` (revised — v1 was too weak):

```python
news_signal = 0
if recent_news_count >= 5 AND research_priority >= 4 AND volume_ratio >= 1.5:
    news_signal = +1   # strong news + corroborating volume
elif recent_news_count >= 3 AND volume_ratio >= 1.2:
    news_signal = +1
elif recent_news_count == 0:
    news_signal = 0
else:
    news_signal = 0   # uncorroborated news count is informational only
```

`composite`:

```python
composite = momentum + extension + news_signal + regime_signal  # range -4..+4
```

The key v2 change is the addition of `regime_signal`, putting an
upper bound on bullish predictions when the broad market is down.

## 7. Direction mapping (NEW in v2 — 4-state)

```python
if extension == -1 AND regime in ("negative", "negative_5d"):
    direction = "down"          # downside override
elif extension == -1:
    direction = "flat-down"     # dampener fired but regime not opposing
elif composite >= +2:
    direction = "up"
elif composite == +1:
    direction = "flat-up"
elif composite == 0:
    if regime in ("negative", "negative_5d"):
        direction = "flat-down"
    else:
        direction = "flat-up"
elif composite == -1:
    direction = "flat-down"
elif composite <= -2:
    direction = "down"
```

Actual-direction definition for eval (`epsilon=0.005`, i.e. 50 bps,
relaxed from v1's 10 bps):

```python
if actual_return > +0.005:           actual_direction = "up"
elif actual_return >= +0.001:        actual_direction = "flat-up"
elif actual_return > -0.001:         actual_direction = "flat-flat"  # informational only
elif actual_return >= -0.005:        actual_direction = "flat-down"
else:                                actual_direction = "down"
```

For direction accuracy scoring, we collapse to 3 evaluable bands:

| Predicted | Counts as direction-correct when actual is |
|---|---|
| `up` | `up` |
| `flat-up` | `up` OR `flat-up` OR `flat-flat` (positive bias band) |
| `flat-down` | `down` OR `flat-down` OR `flat-flat` (negative bias band) |
| `down` | `down` |

A `flat-up` prediction with an actual `down` is **incorrect**. A
`flat-up` with an actual `flat-flat` is correct. This widens the
hit-band without making the rule trivially accurate.

## 8. Bucket rules (NEW in v2)

```python
if direction == "up" AND composite >= +3 AND regime == "positive":
    bucket = "above_plus_3"
elif direction == "up":
    bucket = "plus_1_to_plus_3"
elif direction == "flat-up":
    bucket = "minus_1_to_plus_1"   # default flat band
elif direction == "flat-down":
    bucket = "minus_1_to_plus_1"
elif direction == "down" AND composite <= -3 AND regime in ("negative","negative_5d"):
    bucket = "below_minus_3"
elif direction == "down":
    bucket = "minus_3_to_minus_1"
```

This explicitly relaxes v1's "never predict the extreme buckets"
cap. v2 ALLOWS `above_plus_3` and `below_minus_3` but only when BOTH
the composite is `≥ 3` in magnitude AND the regime aligns. Without
both, the rule still caps at `±1..±3` to stay honest.

## 9. Confidence calibration (NEW in v2)

v1 capped everything at `low` so the confidence-stratified accuracy
table was untestable. v2 defines three explicit tiers:

```python
if data_quality != "complete":
    confidence = "low"
elif abs(composite) >= 3 AND signal_strength == "high" AND no risk_flags AND regime_aligns_with_direction:
    confidence = "high"
elif abs(composite) >= 2 AND data_quality == "complete":
    confidence = "medium"
else:
    confidence = "low"
```

`regime_aligns_with_direction`:

* `direction in {up, flat-up}` and `regime in {positive, neutral}`
* OR `direction in {down, flat-down}` and `regime in {negative, negative_5d, neutral}`
* `neutral` regime aligns with both sides
* `unknown` regime BLOCKS the `high` tier (fail-safe — never claim
  certainty without market-regime evidence)

Hard rule: if `data_quality != complete`, the confidence is `low`
regardless of composite. This keeps the missing-data set isolated.

## 10. Evaluation metrics

After the natural EOD sync confirms `freshness_status=fresh` and the
target trade-date `T` is in `price_bar_raw`:

| Metric | Definition |
|---|---|
| `evaluated_count` | tickers in the prediction set (NOT `watch_only`) with both `T-1` and `T` closes in `price_bar_raw` |
| `direction_accuracy` | per the §7 collapse-to-3-bands rule |
| `bucket_accuracy` | exact bucket match |
| `MAE_pct` | mean of `|actual_return_pct - bucket_midpoint_pct|` (midpoints `±4, ±2, 0`) |
| `confidence_stratified_direction_accuracy` | direction accuracy within `confidence=high`, `medium`, `low` subsets |
| `regime_alignment_accuracy` | direction accuracy when the prediction direction "agreed with" the regime |
| Splits | by `HELD` tag, by `recent_news_count > 0`, by SCANNER tag, by `signal_strength`, by `extension_signal` |
| `extension_dampener_calibration` | for tickers with `extension=-1`: how many actually went down vs flat |
| `downside_override_calibration` | how often the `extension=-1 AND regime=negative` override fired and how many of those actually went down |

## 11. Decision rule (success / falsified)

| Outcome | Decision |
|---|---|
| `direction_accuracy ≥ 50 %` AND `confidence=high` accuracy is `≥ 65 %` (when N≥3) AND `bucket_accuracy ≥ 50 %` | Rule v2 not falsified this cycle. Run again on a future trading day. |
| `direction_accuracy ≥ 35 %` only | Treat as a single-day data point. **Do not** claim non-falsification. Run another cycle before deciding. |
| Below the above | Rule v2 falsified. Open Shadow Test #5 with another pre-registration. |
| Any banned trade-action word appears in prediction text | Run invalid; rerun with corrected language. |
| Any side-effect attestation in §13 fails | Run invalid; investigate. |

Three cycles minimum before declaring "v2 working" — single-day
results are too noisy.

## 12. Missing-data policy

* Tickers failing the §3 eligibility filter → `watch_only[]` list
  with a `reason` string.
* Tickers in `predictions[]` but missing `T-1` or `T` close at eval
  time (rare; would indicate an EOD sync regression) → marked
  `missing_at_eval` and excluded from the denominator.
* **NEVER** substituted with external web prices.
* **NEVER** mock-filled with a synthetic close.
* The `watch_only` list is research-only context — not a
  recommendation.

## 13. Strict side-effect attestations (this pre-registration)

| | Status |
|---|---|
| 2026-05-12 prediction JSON | **NOT MODIFIED** |
| 2026-05-12 prediction MD | **NOT MODIFIED** |
| 2026-05-12 eval doc §1-§6 | **NOT MODIFIED** |
| 2026-05-12 eval doc §7 Results | **NOT MODIFIED** (frozen post-append) |
| 2026-05-12 final accuracy doc | **NOT MODIFIED** |
| Retroactive backfill of v1 predictions under v2 rules | **NEVER** |
| Production DB write | NONE |
| Cloud Run service deploy | NONE |
| Migration | NONE |
| Manual EOD sync | NONE |
| Manual `quant-sync-t212` execution | NONE |
| Manual brief-overnight execution | NONE |
| Scheduler create / update / pause / resume | NONE |
| T212 endpoint write / broker submit | NONE |
| `order_intent` / `order_draft` created | 0 |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (preserved) |
| External web prices | NEVER |
| Browser automation / scraping | NONE |
| Secrets exposed | NONE |
| `.firebase/` cache committed | NO |

## 14. No trading advice disclaimer (verbatim, MUST be preserved)

> **This is a deterministic shadow research experiment. It is NOT a
> trading recommendation, NOT investment advice, and NEVER outputs
> buy/sell directives, target prices, position sizes, stop levels,
> or entry/exit instructions. Predictions are generated for
> calibration accuracy measurement only. They live exclusively in
> docs/*.json and docs/*.md and are NEVER surfaced as a user-facing
> trading signal in the platform UI. The platform's
> `FEATURE_T212_LIVE_SUBMIT` flag is and remains `false`. No
> `order_intent` or `order_draft` is ever created by this
> experiment.**

## 15. References

* v1 prediction (frozen): `docs/premarket-shadow-prediction-20260512.json`
* v1 eval results (frozen): `docs/platform-prediction-accuracy-20260512-final.md`
* v1 narrative (frozen): `docs/premarket-shadow-prediction-20260512.md`
* v1 procedure with §7 Results (frozen): `docs/premarket-shadow-prediction-20260512-eval.md`
* Shadow Test #2 design (separately pre-registered): `docs/prediction-shadow-test-2-pre-registration.md`
* EOD freshness invariant (deployed): `libs/ingestion/eod_freshness.py` + `docs/eod-freshness-lag-diagnosis-20260512.md`
* Runbook (procedure for evaluating any premarket prediction): `docs/runbook.md §15`

## 16. Status

This document is **pre-registration only**. It does NOT trigger a new
prediction run automatically. A future agent turn or operator action
must:

1. Verify the target trade-date `T` has a fresh `T-1` close in
   `price_bar_raw` (use the freshness invariant block printed by the
   most recent `quant-sync-eod-prices` execution).
2. Pull the latest persisted `market_brief_run` candidate snapshot
   and the SPY/QQQ rows for the regime probe.
3. Apply the rules in §3, §5–§9.
4. Write `docs/premarket-shadow-prediction-YYYYMMDD-v2.json` +
   `.md` + `-eval.md` (placeholder for the eval).
5. Commit + push **before** the US open of `T`.
6. After the natural EOD fire on `T 21:30Z`, run the §10 eval and
   append `§7 Results` to the eval doc.

No part of step 1–6 is performed by THIS commit. THIS commit only
registers the v2 ruleset (and an optional pure-function helper in
`libs/prediction/rule_v2.py`).
