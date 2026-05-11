# Prediction Shadow Test #2 — Pre-registration

**Pre-registration written at:** 2026-05-10 02:50 UTC
**Pre-registration commit:** _to be filled in by the commit landing
this file (record the SHA after landing)_
**Eval target trade_date:** the first newly inserted production EOD
bar dated **strictly after** the pre-registration commit landed, on
or after 2026-05-12 (skips the 2026-05-11 weekend gap).

> **Research only — strict no-trade-recommendation policy.** No
> buy/sell/entry/target/stop/position/leverage language is used here
> or in the model's predictions. `FEATURE_T212_LIVE_SUBMIT` is and
> stays `false`. No `order_intent` / `order_draft` is created at any
> point in this test. The shadow predictions never appear in the UI
> as user-facing scores.

## 1. Why a Test #2

Test #1 (eval in `docs/scanner-prediction-shadow-test-1-eval.md`)
was a 22-sample pilot — too small to draw any modelling conclusion
on its own. Test #2 widens the universe and fixes two issues seen
during Test #1:

1. **Universe** — Test #1 used the 22-ticker hand-picked set that
   happened to overlap with the user's holdings. Test #2 uses the
   stable Scanner Research-36 universe ∪ the live Trading 212 Mirror
   ticker set as the prediction subject pool. This is the same
   universe the overnight brief composes, so we can run the test
   alongside the existing snapshot-write path with no extra calls.
2. **Pre-registration durability** — Test #1 stored predictions in a
   markdown table. Test #2 writes them to a *new* JSON snapshot in
   `docs/prediction-shadow-test-2-predictions.json`
   committed in this same change so the predictions are
   tamper-evident and version-controlled before the target trade
   date materializes.

## 2. Strict policy boundaries

| Boundary | Status |
|---|---|
| Buy/sell/entry/target/stop/position/leverage in any prediction text | NEVER. Strict source-grep guard at landing time. |
| `order_intent` / `order_draft` created | NEVER. |
| Cloud Run Job auto-fired against this test | NO. Test #2 does NOT spin up its own scheduler; eval runs manually. |
| Predictions surfaced in user UI | NO. Eval lives in docs; predictions never get a research-priority chip, brief banner, or score. |
| `FEATURE_T212_LIVE_SUBMIT` | `false`. Untouched. |
| Provider HTTP for the eval | Read-only (FMP/Massive/Polygon news, EOD price sync already running). |
| Browser automation / scraping | None. |

## 3. Universe

Subject pool = scanner-research-36 ∪ live Trading 212 Mirror
display_tickers (held + recently_traded + watched) at the moment
this pre-registration is committed. Snapshot below; the canonical
list at eval time is whatever was committed in
`docs/prediction-shadow-test-2-predictions.json`.

Capture procedure (read-only):
```bash
# Authenticated browser tab; copy Firebase ID token from DevTools.
curl -sS -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  "https://quant-api-188966768344.asia-east2.run.app/api/market-brief/overnight-preview?days=7&scanner_limit=50&news_top_n=5" \
  | python -m json.tool > /tmp/predictions-test2-input.json
```

Fields used to build predictions per ticker:
- `change_1d_pct`, `change_5d_pct`, `change_1m_pct`
- `volume_ratio`
- `week52_position_pct`
- `signal_strength`, `scan_types`
- `recent_news` count
- `upcoming_earnings` count
- `mapping_status`
- `taxonomy.broad`

## 4. Prediction shape (rules)

For each ticker in the subject pool, exactly three labels are
recorded *before* the eval target trade_date is observed:

### 4a. `direction` — categorical, 3 buckets

```
DIR_UP    next-day close > previous-day close × (1 + ε)
DIR_FLAT  |next-day close - previous-day close| ≤ previous-day close × ε
DIR_DOWN  next-day close < previous-day close × (1 - ε)
```
where `ε = 0.001` (10 bps) to absorb rounding.

### 4b. `return_bucket` — categorical, 5 buckets

```
RB_LE_M2   next-day return ≤ -2.0%
RB_M2_M05  -2.0% < return ≤ -0.5%
RB_M05_P05 -0.5% < return < +0.5%
RB_P05_P2  +0.5% ≤ return < +2.0%
RB_GE_P2   return ≥ +2.0%
```

### 4c. `confidence` — ordinal, 3 buckets

```
LOW     model uncertain
MEDIUM  multiple weak signals agree
HIGH    multiple strong signals agree
```

These three labels are deterministic functions of the rules in
§4d below. Any ML/statistical scoring used to derive them stays
inside the model code; nothing is regressed into a "buy" word.

### 4d. Decision rules (deterministic)

For each ticker:

1. Compute a `momentum_signal` ∈ {+1, 0, -1} from
   `change_1d_pct + change_5d_pct/5`:
   - `> +0.5%` → +1
   - `< -0.5%` → -1
   - else → 0
2. Compute a `news_pressure` ∈ {+1, 0, -1} from
   `len(recent_news)`:
   - `≥ 3` headlines AND any aggregate priority ≥ 4 → +1
   - 0 headlines → 0
   - else → -1 (sentiment unclear; treat as headwind)
3. Compute a `range_signal` ∈ {+1, 0, -1} from `week52_position_pct`:
   - `≥ 90%` → +1
   - `≤ 10%` → -1
   - else → 0
4. `composite = momentum_signal + news_pressure + range_signal`
   ∈ {-3..+3}.
5. `direction`:
   - `composite ≥ +1` → `DIR_UP`
   - `composite ≤ -1` → `DIR_DOWN`
   - `composite == 0` → `DIR_FLAT`
6. `return_bucket`:
   - `composite ≥ +2` → `RB_P05_P2`
   - `composite == +1` → `RB_M05_P05` (small-positive bias)
   - `composite == 0` → `RB_M05_P05`
   - `composite == -1` → `RB_M05_P05` (small-negative bias)
   - `composite ≤ -2` → `RB_M2_M05`
   - Note: the model deliberately does NOT predict the extreme
     buckets (`RB_GE_P2` / `RB_LE_M2`) because Test #1 showed they
     overfit on small samples.
7. `confidence`:
   - `|composite| ≥ 2` AND no `risk_flags` → `HIGH`
   - `|composite| == 1` → `MEDIUM`
   - else → `LOW`

These rules are the canonical algorithm. Any divergence between
this doc and the actual snapshot (next item) is a bug in the
snapshot.

## 5. Snapshot file

After the rules in §4 produce predictions for every ticker in the
subject pool, the snapshot is written to:

```
docs/prediction-shadow-test-2-predictions.json
```

with shape:

```json
{
  "schema_version": "1.0",
  "test_id": "prediction-shadow-test-2",
  "preregistered_at": "2026-05-10T02:50:00Z",
  "preregistration_commit": "<commit SHA>",
  "subject_pool_universe": "scanner-research-36 + t212-mirror",
  "data_as_of_trade_date": "<input bar trade_date>",
  "eval_target_trade_date": "<first new EOD bar after preregistration>",
  "epsilon": 0.001,
  "predictions": [
    {
      "ticker": "NVDA",
      "direction": "DIR_UP",
      "return_bucket": "RB_M05_P05",
      "confidence": "MEDIUM",
      "factors_used": ["momentum_signal=+1", "news_pressure=0",
                       "range_signal=0"]
    }
  ],
  "side_effects": {
    "db_writes": "NONE",
    "broker_writes": "NONE",
    "order_intents_created": 0,
    "live_submit": "LOCKED (FEATURE_T212_LIVE_SUBMIT=false)"
  }
}
```

Important: the snapshot file is generated by hand from the same
brief output captured in §3. It is **not** auto-generated by a job
in this run — that's the next phase if the framework holds up.

## 6. Evaluation procedure

Run after the eval target trade_date has a confirmed EOD bar in
`price_bar_raw` (synced by the existing
`quant-sync-eod-prices-schedule`):

1. For each entry in `predictions[]`, look up the ticker's
   close on the eval target trade_date and the close on the
   previous trade_date.
2. Compute `actual_return = (close_t - close_t-1) / close_t-1`.
3. Bucket `actual_return` into the same 5 buckets in §4b.
4. Compute `actual_direction` from §4a.
5. Compare `predicted` vs `actual` per (direction, return_bucket).
6. Aggregate by `confidence` bucket.

Output goes to `docs/prediction-shadow-test-2-eval.md` in the same
shape as the Test #1 eval.

## 7. Acceptance / non-acceptance criteria

| Outcome | Decision |
|---|---|
| `direction` accuracy ≥ 55 % AND `confidence=HIGH` accuracy ≥ 65 % AND >100 samples | Run a Test #3 with a wider universe; still no UI surfacing. |
| Lower than the above | Document the gap; treat the rule set as falsified for the next test cycle. |
| Any banned word appears in the eval | Eval invalid; rerun. |
| Any side-effect attestation in §1 fails | Eval invalid; rollback per the runbook. |

## 8. Side-effect attestations (this doc)

| | Status |
|---|---|
| Production DB write | NONE (this doc + a sibling JSON snapshot, both committed via git) |
| Cloud SQL backup taken | N/A — pure docs |
| Cloud Run Job created | NONE for this test |
| Cloud Scheduler change | NONE for this test |
| Production sync execution | NONE for this test |
| Trading 212 write | NONE |
| `order_intent` / `order_draft` created | NONE |
| `FEATURE_T212_LIVE_SUBMIT` | `false`, untouched |
| Browser automation / scraping | NONE |
| User-facing prediction surface | NONE — predictions live in docs, not in the UI |

This pre-registration is the canonical snapshot. Any change to the
rules in §4 after the eval target trade_date is a violation of the
pre-registration contract — open a Test #3 instead.

---

## 9. 2026-05-10 Continuation-push status note

The pre-registration commit landed in `1acfeaf` (the mega-push). Two
new persisted brief runs now exist:

| run_id | source | generated_at | tickers |
|---|---|---|---|
| `3685a390-ce5f-4204-908f-4a89ec6f869a` | overnight (validation) | `2026-05-10T02:58Z` | 24 |
| `0c5be84f-0fa3-48cd-acdb-c4662e64225f` | overnight (validation) | `2026-05-11T03:20Z` | 24 |

The newer run `0c5be84f…` is the **canonical input snapshot** for the
prediction capture step (§5) once the operator has authenticated
access to the brief detail. The capture procedure (manual, deferred):

1. Sign in to the Market Events page (Firebase auth).
2. Click **"Show history"** → click the `0c5be84f…` row to load the
   full brief detail.
3. Save the JSON locally.
4. Apply the deterministic rules from §4d to each candidate to
   produce the predictions list.
5. Commit the result to
   `docs/prediction-shadow-test-2-predictions.json` BEFORE the
   next EOD bar lands (`2026-05-11` is a Monday US session; the EOD
   bar arrives ~21:30 UTC the next trading day).
6. After the bar lands, run §6 evaluation; write
   `docs/prediction-shadow-test-2-eval.md`.

**This run (Continuation Push) deliberately does NOT capture the
predictions JSON automatically.** Reasons:

* The pre-registration explicitly says the snapshot is "generated by
  hand … not auto-generated by a job in this run" (§5).
* Auto-capturing without the operator's review would weaken the
  tamper-evidence guarantee.
* Predictions remain docs-only — never UI-surfaced.

Side-effect attestations for this status note: NONE — pure docs
update, no provider call, no DB write, no scheduler change.
