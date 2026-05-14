# Platform Prediction Accuracy — 2026-05-12 (Final)

**Status:** Evaluation COMPLETE.
**Eval run at:** `2026-05-14T00:36:08Z`
**Prediction source:** `docs/premarket-shadow-prediction-20260512.json`
(commit `597156e`, pre-registered `2026-05-12T12:46:43Z` — strictly
before US 13:30Z open on the eval target trade-date)
**Actuals source:** production `price_bar_raw` only (no external web
substitution per audit policy).

---

## 1. Pre-flight gates — all passed

| Gate | Status |
|---|---|
| (1) US `2026-05-12` regular session closed | ✓ (closed `20:00Z` on `2026-05-12`) |
| (2) Tonight's `quant-sync-eod-prices-schedule` fire succeeded | ✓ — execution `quant-sync-eod-prices-p6w9k`, started `2026-05-13T21:30:09Z`, completed `2026-05-13T21:38:15Z` (8m6.14s), `succeededCount=1`, `failedCount=None`, scheduler-fired |
| (3) `price_bar_raw.max(trade_date) ≥ 2026-05-12` | ✓ `overall_max=2026-05-12`, total_rows=13476, rows_for_2026-05-12=36 |
| (4) New freshness-invariant block printed | ✓ `freshness_status=fresh`, `expected_min_trade_date=2026-05-12`, `latest_trade_date=2026-05-12`, per-ticker `fresh=36 stale=0 bar_less=7 inspected=43` |

## 2. SYNC RESULT block (verbatim from Cloud Logging)

```
SYNC RESULT — universe='scanner-research'  mode=WRITE_PRODUCTION
  ticker_count                  : 36
  succeeded                     : 36
  failed                        : 0
  bars_inserted_total           : 36
  bars_existing_or_skipped_total: 216
  runtime_seconds               : 480.8
  db_target                     : production

  Side-effect attestations:
    DB writes performed          : price_bar_raw + source_run only (PRODUCTION Cloud SQL)
    Cloud Run jobs created       : NONE
    Scheduler changes            : NONE
    Production deploy            : NONE
    Execution objects            : NONE
    Broker write                 : NONE
    Live submit                  : LOCKED (FEATURE_T212_LIVE_SUBMIT=false)

  Freshness invariant:
    today                        : 2026-05-13
    expected_min_trade_date      : 2026-05-12
    latest_trade_date            : 2026-05-12
    freshness_status             : fresh
    per-ticker: fresh=36 stale=0 bar_less=7 inspected=43
```

## 3. Headline accuracy

| Metric | Value |
|---|---|
| `total_predictions` (in prediction JSON) | **26** |
| `evaluated_count` | **15** |
| `missing_count` | **11** |
| `direction_accuracy` | **`1 / 15 = 6.7 %`** |
| `bucket_accuracy` | **`7 / 15 = 46.7 %`** |
| `MAE_pct` | **`1.7668`** |
| `low_confidence_direction_accuracy` | `1 / 15 = 6.7 %` (all 15 evaluable rows had `confidence=low`) |
| `medium_confidence_count` | 0 (Shadow v1 capped confidence at `low` for this run) |
| `high_confidence_count` | 0 |

## 4. Per-ticker results

| Ticker | Pred dir | Actual dir | Pred bucket | Actual bucket | Actual % | Dir? | Bucket? |
|---|---|---|---|---|---:|---|---|
| `MU` | flat | down | minus_1_to_plus_1 | below_minus_3 | -3.615 | N | N |
| `AMD` | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.289 | N | N |
| `AVGO` | up | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.131 | N | N |
| `GOOGL` | flat | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.332 | N | Y |
| `INTC` | flat | down | minus_1_to_plus_1 | below_minus_3 | -6.822 | N | N |
| **`AAPL`** | **up** | **up** | minus_1_to_plus_1 | minus_1_to_plus_1 | **+0.724** | **Y** | **Y** |
| `AMZN` | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -1.179 | N | N |
| `GS` | flat | up | minus_1_to_plus_1 | minus_1_to_plus_1 | +0.110 | N | Y |
| `IWM` | flat | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.967 | N | Y |
| `NVDA` | flat | up | minus_1_to_plus_1 | minus_1_to_plus_1 | +0.611 | N | Y |
| `QQQ` | up | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.848 | N | Y |
| `SIRI` | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.333 | N | N |
| `SPY` | flat | down | minus_1_to_plus_1 | minus_1_to_plus_1 | -0.151 | N | Y |
| `TSLA` | up | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -2.595 | N | N |
| `TSM` | flat | down | minus_1_to_plus_1 | minus_3_to_minus_1 | -1.795 | N | N |

Actual-direction definition: `up` if `return > +0.1 %`, `down` if
`< -0.1 %`, else `flat` (same `epsilon=0.001` as the pre-registered
ruleset).

Actual-bucket definition: same 5-bucket scheme as the prediction JSON
(`above_plus_3 / plus_1_to_plus_3 / minus_1_to_plus_1 /
minus_3_to_minus_1 / below_minus_3`).

## 5. Split metrics (direction accuracy)

| Split | Evaluable count | Direction accuracy |
|---|---:|---:|
| `HELD` ∈ source_tags | 1 (MU) | 0 / 1 = 0.0 % |
| Not held | 14 | 1 / 14 = 7.1 % |
| `recent_news_count > 0` (news-linked) | 2 (MU, AMD) | 0 / 2 = 0.0 % |
| No recent news | 13 | 1 / 13 = 7.7 % |
| `SCANNER` ∈ source_tags | 15 | 1 / 15 = 6.7 % |
| Mirror-only (no SCANNER) | 0 | N/A |

The Mirror-only split is empty because all 11 mirror-only candidates
were either bar-less (mirror-bootstrap scaffolding) or unmapped. All
15 evaluable rows carry the SCANNER tag.

## 6. Missing tickers (11 / 26 excluded from denominator)

| Ticker | Reason | Source category |
|---|---|---|
| `LITE` | no `instrument_identifier` row | unmapped Mirror |
| `IPOE` | no `instrument_identifier` row | unmapped (deferred in 2026-05-11 bootstrap as `unresolved`) |
| `OAC` | no `instrument_identifier` row | unmapped (same) |
| `SNDK1` | no `instrument_identifier` row | unmapped (same) |
| `NOK` | no `price_bar_raw` seed | `bootstrap_prod` source — scaffolding-only by design |
| `AAOI` | no `price_bar_raw` seed | same |
| `ORCL` | no `price_bar_raw` seed | same |
| `VACQ` | no `price_bar_raw` seed | same |
| `CRWV` | no `price_bar_raw` seed | same |
| `CRCL` | no `price_bar_raw` seed | same |
| `TEM` | no `price_bar_raw` seed | same |

These are excluded from the accuracy denominator. They are **not**
counted as wrong predictions; they're "not measurable from platform DB"
and pre-classified as `data_quality=weak` in the prediction JSON
itself.

## 7. Calibration narrative — what the rule got right, what it got wrong

### 7.1 The day's market shape

13 of 15 evaluable tickers closed **down**, 2 closed up, **0 ended
flat**. The actual_returns spanned `-6.82 %` (INTC) to `+0.72 %`
(AAPL). The day was a broad **risk-off** session.

### 7.2 What the rule got right

* **AAPL (1/15 direction hit)** — predicted `up` with `composite=+1`
  driven by `change_1d_pct=+2.05`; actual `+0.72 %`. Honest hit.
* **Bucket accuracy 7/15 (46.7 %)** — the conservative
  `minus_1_to_plus_1` default bucket caught all the small-magnitude
  tickers (GOOGL -0.33, GS +0.11, IWM -0.97, NVDA +0.61, QQQ -0.85,
  SPY -0.15) plus AAPL. The shadow-v1 cap on never-predict-extreme
  buckets was vindicated for small-mover names.
* **Extension dampener fired on MU / AMD / INTC** — those three were
  the rule's only "extension=-1 ⇒ flat" signals. Actual outcomes:
  MU `-3.62 %`, AMD `-2.29 %`, INTC `-6.82 %`. The dampener was
  **directionally correct** in saying "not sustained up" (they all
  went down), but **predicted the wrong direction** because the rule
  collapses `-1` to `flat` instead of to `down`. The bias was right
  for the wrong language.

### 7.3 What the rule got wrong

* **Direction accuracy `6.7 %` is essentially worst-case** for a
  3-bucket classifier on a single trading day. The conservative
  flat-heavy default fails when the market has a one-sided move.
* **0 / 11 flat-direction predictions hit** the narrow `|return| ≤
  0.1 %` band. The market always moves more than 10 bps on the day
  for liquid US equities. The `epsilon` for the flat band may be too
  tight relative to the bucket boundary at `±1 %`.
* **3 of 4 "up" picks reversed**: AVGO (`-2.13 %`), QQQ (`-0.85 %`),
  TSLA (`-2.60 %`). The pure `change_1d_pct ≥ +2 %` momentum signal
  was a coincident-momentum trap on the prior day.
* **The "news_linked" split** showed 0 / 2 — MU and AMD both had
  news, both predicted flat, both went down hard. News count alone
  is too weak a signal at threshold 3 with research_priority ≥ 4.

### 7.4 Pre-registered improvement notes for Shadow Test #4

These are **research observations**, NOT changes to the existing
pre-registration (which remains canonical and frozen).

1. **Consider a 4-state direction**: `up / flat-up / flat-down / down`,
   where `flat-up` and `flat-down` cover the `0.1 %–1 %` magnitude
   bands. The current flat band is unrealistically tight.
2. **Decouple the extension dampener**: when `extension=-1`, predict
   `down` (not `flat`). The dampener already says "this is too
   stretched". The current rule wastes that signal by collapsing it
   to flat.
3. **Tighten the bucket cap relaxation**: if `composite ≤ -2`, allow
   the rule to predict `minus_3_to_minus_1` (currently used) but
   ALSO consider relaxing the shadow v1 "never predict
   `below_minus_3`" cap. INTC was `-6.82 %` — the rule had no way to
   express that magnitude.
4. **Weight the news signal**: news count alone is noise. Pair it
   with implied volatility / spike volume signals before letting it
   add to `composite`.
5. **Confidence cap revisit**: all 15 evaluable rows had
   `confidence=low`. That's honest but means we cannot test the
   confidence-stratified accuracy. A future shadow run could allow a
   `medium` tier when `composite ≥ +2 AND signal_strength=high AND
   no risk_flags AND extension == 0`, but only for direction not
   bucket.

None of the above is applied to the existing 2026-05-12 prediction.
The pre-registration is canonical; any rule change requires a
**separate Shadow Test #4 pre-registration** before it can be
evaluated.

## 8. Strict side-effect attestations (this eval)

| | Status |
|---|---|
| Manual EOD sync triggered this turn | **NO** — `p6w9k` is the natural `2026-05-13T21:30Z` scheduler-fired execution (createTime `21:30:05Z`, matches scheduler tick) |
| Manual `quant-sync-t212` execution | NONE |
| Manual brief-overnight execution | NONE |
| T212 endpoint write | NONE |
| Broker submit | NONE |
| `order_intent` / `order_draft` created | 0 (unchanged) |
| `FEATURE_T212_LIVE_SUBMIT` mutated | NO — remains `false` |
| Schedulers modified | NONE — all 3 (`quant-sync-eod-prices-schedule`, `quant-sync-t212-schedule`, `quant-market-brief-overnight-schedule`) ENABLED, cron unchanged |
| Cloud Run service deploy | NONE — still `quant-api-00053-4p7` |
| Migration | NONE |
| Cloud SQL backup taken | NONE (eval is read-only) |
| Production DB write driven by THIS eval | NONE — only `SELECT` queries via a transient Cloud Run Job |
| Transient Cloud Run Job created and deleted | `quant-ops-eval-closes` — created, executed, **deleted in-run** after success. No persistent footprint. |
| External web prices used | **NO** — production `price_bar_raw` only |
| Browser automation / scraping | NONE |
| Secrets exposed in committed text | NONE (DB URL appears as `quantuser:***@…` redacted; no Bearer / API key / private key in committed files) |
| `.firebase/` cache committed | NO |

## 9. References

* Canonical prediction: `docs/premarket-shadow-prediction-20260512.json`
  (commit `597156e`, pushed `2026-05-12T12:50:49Z`)
* Pre-registration narrative: `docs/premarket-shadow-prediction-20260512.md`
* Eval procedure (appended results in `§7`):
  `docs/premarket-shadow-prediction-20260512-eval.md`
* EOD freshness diagnosis: `docs/eod-freshness-lag-diagnosis-20260512.md`
* Continuous validation run log: `docs/overnight-continuous-validation-20260513.md`
* Runbook §15 — Evaluating a Pre-market Shadow Prediction: `docs/runbook.md`
