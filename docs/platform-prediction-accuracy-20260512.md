# Platform Prediction Accuracy — 2026-05-12

**Status:** **PENDING — eval timing gate not met.** The platform-native
pre-market prediction record exists and is valid, but the production
`price_bar_raw` table does not yet contain bars for the eval target
trade dates. Per policy, this report does **not** use external web
sources to substitute, and the chat-internal manual evaluation is
**not** counted as platform accuracy.

**Audit timestamp (UTC):** `2026-05-12T20:52:19Z` (~12 minutes after US
regular session close at 20:00Z; ~38 minutes before the next
scheduled EOD sync at 21:30Z).

---

## 1. Did the platform produce a real, evaluable prediction? **YES.**

Source of truth: **`docs/premarket-shadow-prediction-20260512.json`**
(committed in `597156e`).

| Field | Value |
|---|---|
| `test_id` | `premarket-shadow-prediction-20260512` |
| `schema_version` | `1.0` |
| `preregistered_at` | **`2026-05-12T12:46:43Z`** (~44 min before US open) |
| `preregistration_horizon` | `next_close_vs_previous_close` |
| `previous_trade_date_anchor` | `2026-05-11` |
| `eval_target_trade_date` | `2026-05-12` |
| `source_brief_run_id` | `cd994ed6-44d0-41a4-b091-9459f527f184` (the 2nd auto-fire of `quant-market-brief-overnight-schedule`) |
| `predictions` (count) | **26** |
| Side-effect attestation embedded in JSON | `db_writes=NONE, broker_writes=NONE, execution_objects=NONE, live_submit=LOCKED (FEATURE_T212_LIVE_SUBMIT=false), order_intents_created=0, order_drafts_created=0` |
| Per-ticker fields present | `predicted_direction`, `predicted_return_bucket`, `confidence`, `data_quality`, `rationale_factors`, `decision.composite`, `external_headline_flags`, `inputs.{change_1d_pct, change_5d_pct, week52_position_pct, volume_ratio, recent_news_count, upcoming_earnings_count, signal_strength, risk_flags}` |

Validation checks all pass:
* Pre-registered **strictly before** US open (`12:46:43Z` < `13:30Z` ✓)
* Per-ticker structured fields (not a free-text speculation) ✓
* Research-only language tag present ✓
* Tamper-evident — committed to git before market open (commit hash `597156e`, push `2026-05-12T12:50:49Z`)

**Conclusion: this IS a platform-native prediction record.**

## 2. Why accuracy cannot be computed today (yet)

Per the eval doc `docs/premarket-shadow-prediction-20260512-eval.md`
§1, accuracy may only be computed when **all three** timing gates fire:

| Gate | Status as of audit time |
|---|---|
| (1) US regular session closed (≥ `2026-05-12T20:00Z`) | ✓ closed |
| (2) `quant-sync-eod-prices` job for trade_date 2026-05-12 has succeeded | ⏳ **not yet** — next scheduled fire `2026-05-12T21:30Z` |
| (3) `price_bar_raw` carries a row for `trade_date='2026-05-12'` for ≥ the 15 complete-data tickers | ✗ **not met** — see §3 |

### Latest `price_bar_raw` state (read-only query)

```
distinct trade_dates desc, top 5:
  2026-05-08   (Friday)
  2026-05-07
  2026-05-06
  2026-05-05
  2026-05-04
```

The **2026-05-11** bar (the anchor) and the **2026-05-12** bar (the
target) **do not exist yet**.

Observation: Monday's EOD sync job `quant-sync-eod-prices-cfbqn`
**did fire and succeeded** (createTime `2026-05-11T21:30:05Z`,
completion `2026-05-11T21:38:17Z`, succeeded=1, runtime 8m6s). The
absence of `trade_date=2026-05-11` rows in `price_bar_raw` despite
the successful job suggests one of:

1. The upstream provider feed is T-1 lagging (most likely);
2. The sync writes under a different `trade_date` mapping (e.g. it
   skipped the day for some universe filter); or
3. A silent partial-failure inside the sync that didn't bubble up to
   the Cloud Run Job exit code.

This is an **ops finding flagged for separate investigation** —
not actioned in this read-only audit, but recorded in §7 below.

## 3. Mapping coverage of the 26 prediction tickers

Read-only resolution against `instrument_identifier` (`id_type='ticker'`):

| Ticker | instrument_id present? | Bars (2026-05-04..05-08)? |
|---|---|---|
| MU | ✓ | ✓ |
| AMD | ✓ | ✓ |
| AVGO | ✓ | ✓ |
| GOOGL | ✓ | ✓ |
| INTC | ✓ | ✓ |
| AAPL | ✓ | ✓ |
| AMZN | ✓ | ✓ |
| GS | ✓ | ✓ |
| IWM | ✓ | ✓ |
| NVDA | ✓ | ✓ |
| QQQ | ✓ | ✓ |
| SIRI | ✓ | ✓ |
| SPY | ✓ | ✓ |
| TSLA | ✓ | ✓ |
| TSM | ✓ | ✓ |
| NOK | ✓ (mirror-bootstrapped 2026-05-11) | ✗ no bars seeded |
| AAOI | ✓ (mirror-bootstrapped) | ✗ no bars seeded |
| CRCL | ✓ (mirror-bootstrapped) | ✗ no bars seeded |
| CRWV | ✓ (mirror-bootstrapped) | ✗ no bars seeded |
| ORCL | ✓ (mirror-bootstrapped) | ✗ no bars seeded |
| TEM | ✓ (mirror-bootstrapped) | ✗ no bars seeded |
| VACQ | ✓ (mirror-bootstrapped) | ✗ no bars seeded |
| **LITE** | **✗ NOT_MAPPED** | — |
| **IPOE** | **✗ NOT_MAPPED** | — |
| **OAC** | **✗ NOT_MAPPED** | — |
| **SNDK1** | **✗ NOT_MAPPED** | — |

Summary:

* 22 of 26 tickers are mapped (instrument_id present);
* 4 are unmapped (`LITE`, `IPOE`, `OAC`, `SNDK1`) — these match the
  three "unresolved" tickers from the mirror bootstrap plus `LITE`
  (likely newly added to the T212 Mirror this week and not yet
  resolvable via FMP);
* Among mapped tickers, only the 15 scanner-research-36 names have
  price bars; the 7 newly-bootstrapped Mirror tickers were
  scaffolded without seed bars (by design of
  `execute_bootstrap` — see `docs/mirror-bootstrap-allowlist-report.md` §5).

Even when the EOD sync catches up to `trade_date=2026-05-12`, the 7
newly-bootstrapped tickers will likely remain bar-less until either
(a) a separate price-bar seed job is run, or (b) the regular EOD sync
extends its universe to include them.

## 4. Accuracy table — **not yet computable**

|  | Value |
|---|---|
| `evaluated_tickers_count` | **0** |
| `missing_data_tickers_count` | **26** (all — anchor + target dates absent) |
| `direction_accuracy` | **N/A — pending** |
| `bucket_accuracy` | **N/A — pending** |
| `MAE_pct` | **N/A — pending** |
| `high_confidence_accuracy` | **N/A** (no medium-or-higher confidence predictions in this run) |
| `mirror_vs_scanner_split` | **N/A — pending** |
| `news_linked_vs_non_news_split` | **N/A — pending** |
| `held_vs_nonheld_split` | **N/A — pending** |

Per-ticker `actual_return` cannot be filled in without a row for
`trade_date=2026-05-12` in `price_bar_raw`. The platform does NOT
synthesize prices, and per the audit policy in the prompt
("不要用外部网页补"), no external substitution is performed here.

## 5. When the eval will actually run

The eval becomes possible when **either**:

* `quant-sync-eod-prices-schedule` fires at `2026-05-12T21:30Z` AND
  bars for `2026-05-11` + `2026-05-12` land in `price_bar_raw`; **or**
* The provider lag clears for any future trading day, at which point
  the eval doc §1 procedure runs against THAT day instead (with a
  fresh pre-registration — Test #5).

When that happens, results will be appended to
`docs/premarket-shadow-prediction-20260512-eval.md §7` (append-only —
no rule changes after the gates fire).

## 6. Manual chat-internal "7/12 direction, 2/12 bucket" — explicitly NOT platform accuracy

The user noted a chat-internal manual evaluation that produced
`7/12 direction, 2/12 bucket` numbers. **Those numbers are not
counted as platform accuracy and are not propagated into this report
as such.** They were produced from chat content and untyped sources
that are NOT tamper-evident and NOT bound to the
pre-registered ruleset in §1.

The platform-native result is:

> The platform produced a valid pre-market prediction record. Its
> accuracy on the target trade_date (`2026-05-12`) is **pending**
> because the platform's own production EOD data has not yet ingested
> the target trade_date.

That sentence is the canonical answer to "did the platform model
work" for this run. **Anything else is not platform accuracy.**

## 7. Ops findings (informational, no action taken)

Recorded here for follow-up in a separate ticket, **not actioned in
this audit**:

1. **EOD provider feed appears to lag.** `quant-sync-eod-prices-cfbqn`
   (the 2026-05-11T21:30Z fire) reported `succeeded=1` and ran for
   ~8 min, but no `2026-05-11` bars appear in `price_bar_raw`. Likely
   T-1 provider delivery — but the sync should fail loud, not
   silently produce zero new rows. **Recommend a future ops check**:
   add a post-sync invariant that fails the job when
   `max(trade_date) < CURRENT_DATE - 1`.
2. **Mirror-bootstrapped tickers have no price bars.** This is by
   design (scaffolding-only), but it means prediction accuracy for
   `NOK / AAOI / CRCL / CRWV / ORCL / TEM / VACQ` cannot be evaluated
   even after the EOD sync catches up — unless someone seeds their
   historical bars or extends the EOD universe.
3. **Four tickers not mapped at all** (`LITE`, `IPOE`, `OAC`,
   `SNDK1`). These were "unresolved" at bootstrap dry-run time
   (per `docs/mirror-bootstrap-execution-20260510.md §3 Deferred`)
   and remain unresolved. Predictions for these have
   `data_quality=weak` and will never produce a comparable result
   under the current pipeline. Consider either filtering them out
   of future pre-registrations or running a separate FMP
   profile-resolve pass.

## 8. Strict side-effect attestations (this audit run)

| | Status |
|---|---|
| Production DB write | NONE — every query was `SELECT` only |
| Cloud Run Job created | `quant-ops-eval-fetch` (read-only `SELECT`, **deleted in-run** after success, no persistent footprint) |
| Cloud Run service deploy | NONE — revision still `quant-api-00052-t5j` |
| Migration | NONE |
| Cloud SQL backup | NONE (read-only run, no backup required) |
| Scheduler modification | NONE — all 3 schedulers (`quant-market-brief-overnight-schedule`, `quant-sync-eod-prices-schedule`, `quant-sync-t212-schedule`) untouched |
| Sync job triggered manually | NONE — waiting for the regular 21:30Z fire |
| Trading 212 endpoint | NONE |
| Live submit | LOCKED — `FEATURE_T212_LIVE_SUBMIT=false` (verified at start, preserved end-to-end) |
| `order_intent` / `order_draft` created | NONE |
| Browser automation / scraping | NONE |
| External web source used as primary | NONE — strict platform-DB only |
| Secrets exposed | NONE |
| `.firebase/` cache committed | NO |
| Prediction surfaced to user UI | NO — this report stays in docs |

---

## Final answer to the prompt's three questions

> **平台是否真的产生了可评估 prediction？**

**YES** — `docs/premarket-shadow-prediction-20260512.json` (committed
in `597156e` at `2026-05-12T12:50:49Z`) is a valid, tamper-evident,
pre-market platform-native prediction record with 26 ticker
predictions and a deterministic ruleset.

> **如果有，平台准确率是多少？**

**Currently pending.** The eval target trade dates (`2026-05-11`
anchor + `2026-05-12` target) are not yet in platform
`price_bar_raw`. Per policy, no external substitution is performed.
Accuracy will be computed once the EOD sync lands those rows
(append-only into `…-eval.md §7`).

> **如果没有，本次只能算 manual shadow prediction，不算 platform model accuracy。**

The platform record exists, so this clause does not apply. The
chat-internal manual `7/12 direction, 2/12 bucket` numbers remain
**separate from platform accuracy** by definition — they are not
bound to the committed pre-registration and not derived from
production `price_bar_raw`.
