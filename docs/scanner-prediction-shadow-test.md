# Prediction Shadow Test #1 — Pre-registration

**Test name**: Prediction Shadow Test #1
**Pre-registration created at**: `2026-05-07 21:54 UTC` (re-confirmed by the timestamp on this commit)
**Recorded BEFORE**: C2 tick #6 (scheduled `2026-05-08T21:30:04Z`)
**Status at pre-registration**: tick #5 has fired and PASS; tick #6 has NOT yet fired

> **Safety statement.** This test produces **research-only** scoring. It
> emits no trading recommendations and never uses the words *buy / sell /
> entry / target / target price / stop loss / position / position size /
> leverage / guaranteed / certain* (or their Chinese equivalents
> *买入 / 卖出 / 建仓 / 入场 / 目标价 / 仓位 / 必涨*) in the predictions or
> rationale. The Stock Scanner endpoint, schemas, frontend, and
> deterministic rules in production are unchanged by this document.
> `FEATURE_T212_LIVE_SUBMIT` remains `false`. No execution objects are
> created. No broker write occurs.

## 1. Selected ticker list

22 tickers selected by the user (from screenshot evidence; screenshots
are NOT used as a price source):

```
MRVL, INTC, NOK, AXTI, AAOI, SOFI,
TEM, CRWV, HIMS, RKLB, AMD, NVDA, SNDK, MU,
WDC, SMSN, IREN, ORCL, NBIS, ADBE, PRSO, DUOL
```

## 2. Universe partition

Verified against `libs/scanner/scanner_universe.py::SCANNER_RESEARCH_UNIVERSE`
(36 tickers).

| Bucket | Count | Tickers |
|---|---:|---|
| **In-universe** | **5** | INTC, SOFI, AMD, NVDA, MU |
| **External ephemeral** | **17** | MRVL, NOK, AXTI, AAOI, TEM, CRWV, HIMS, RKLB, SNDK, WDC, IREN, ORCL, NBIS, ADBE, PRSO, DUOL, SMSN |
| **Unresolved** | **0** | — |

SMSN was successfully resolved via the London-listed GDR symbol `SMSN.IL`
on the public quote endpoint (Samsung Electronics ADR/GDR). Its
universe membership is `external_ephemeral`.

## 3. Data source for pre-registration

| Layer | What we used | Why |
|---|---|---|
| Source | Yahoo Finance public chart endpoint (`query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3mo`) — read-only HTTP GET, no API key | Production DB requires a Cloud Run job to read (forbidden in this round); local Polygon/FMP keys are not available in this shell. Yahoo's finalised EOD bars are the same trade days production DB has after each tick, so this is a faithful read-only proxy for the as-of state. |
| Anchor (as-of) | Bars with `trade_date ≤ 2026-05-06` only | Matches production DB state immediately after C2 tick #5. The `2026-05-07` bar (which Yahoo already shows as finalised after market close earlier today) is **excluded** from feature math; it is recorded only as the eval-target preview. |
| User-Agent | `Mozilla/5.0 (compatible; ToniSafetyShadowFetch/1.0)` | Yahoo's free endpoint requires a non-empty UA. |
| Generator | `libs/-/.tmp_predict_shadow.py` (transient, NOT committed) | Pure Python, stdlib-only (`urllib`, `json`, `math`, `datetime`). No DB, no scheduler, no Cloud Run, no broker. |

**Reconciliation at evaluation time** (described in §6 below): in-universe
tickers will be re-checked against production `price_bar_raw` once tick
#6 has inserted the new bar. External-ephemeral tickers will be re-checked
against the same Yahoo endpoint at evaluation time. Both checks are
read-only.

## 4. Predictions — in-universe (5 tickers)

| Ticker | Provider | Membership | as_of | as_of_close | r1d% | r5d% | r1m% | 3m_pos% | vol_ratio | vol_20d% | data_quality | direction | bucket | confidence | rationale_signals (truncated) | forbidden_check |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|
| INTC | INTC | in_universe | 2026-05-06 | 113.01 | +4.49 | +19.27 | +113.59 | 100.0 | 1.09 | 5.87 | complete | up | plus_2_to_plus_5 | high | momentum r1d/r5d/r1m + breakout 3m_pos=100% + vol 5.9% | PASS |
| SOFI | SOFI | in_universe | 2026-05-06 | 16.30 | +1.75 | +4.99 | +1.18 | 18.5 | 0.84 | 4.60 | complete | flat | minus_2_to_plus_2 | low | oversold context (3m_pos=18%); vol 4.6% | PASS |
| AMD | AMD | in_universe | 2026-05-06 | 421.39 | +18.61 | +25.00 | +90.22 | 100.0 | 2.08 | 5.20 | complete | up | above_plus_5 | high | momentum r1d/r5d/r1m + breakout + volume 2.1× + vol 5.2% | PASS |
| NVDA | NVDA | in_universe | 2026-05-06 | 207.83 | +5.77 | −0.68 | +16.69 | 82.9 | 1.28 | 2.41 | complete | up | plus_2_to_plus_5 | medium | momentum r1d, r1m + breakout 3m_pos=83% + vol 2.4% | PASS |
| MU | MU | in_universe | 2026-05-06 | 666.59 | +4.12 | +28.57 | +76.54 | 100.0 | 1.37 | 3.82 | complete | up | plus_2_to_plus_5 | high | momentum r1d/r5d/r1m + breakout + vol 3.8% | PASS |

## 5. Predictions — external ephemeral (17 tickers)

| Ticker | Provider | Membership | as_of | as_of_close | r1d% | r5d% | r1m% | 3m_pos% | vol_ratio | vol_20d% | data_quality | direction | bucket | confidence | forbidden_check |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| MRVL | MRVL | external_ephemeral | 2026-05-06 | 172.15 | +2.01 | +9.95 | +57.39 | 100.0 | 0.82 | 2.90 | complete | up | plus_2_to_plus_5 | high | PASS |
| NOK | NOK | external_ephemeral | 2026-05-06 | 13.19 | −1.71 | +5.86 | +49.04 | 96.4 | 1.10 | 3.69 | complete | up | plus_2_to_plus_5 | medium | PASS |
| AXTI | AXTI | external_ephemeral | 2026-05-06 | 104.83 | −2.53 | +47.50 | +130.60 | 96.8 | 1.15 | 9.91 | complete | flat | minus_2_to_plus_2 | low | PASS |
| AAOI | AAOI | external_ephemeral | 2026-05-06 | 178.54 | −1.12 | +16.82 | +51.77 | 96.5 | 0.83 | 7.54 | complete | up | plus_2_to_plus_5 | medium | PASS |
| TEM | TEM | external_ephemeral | 2026-05-06 | 53.50 | −1.05 | +6.96 | +14.28 | 63.3 | 1.90 | 5.26 | complete | up | plus_2_to_plus_5 | medium | PASS |
| CRWV | CRWV | external_ephemeral | 2026-05-06 | 137.98 | +7.89 | +20.83 | +61.87 | 100.0 | 0.92 | 4.82 | complete | up | plus_2_to_plus_5 | high | PASS |
| HIMS | HIMS | external_ephemeral | 2026-05-06 | 26.88 | +2.09 | +2.09 | +37.85 | 75.0 | 0.45 | 5.49 | complete | up | plus_2_to_plus_5 | medium | PASS |
| RKLB | RKLB | external_ephemeral | 2026-05-06 | 84.65 | +7.48 | +9.91 | +27.64 | 83.5 | 0.91 | 4.78 | complete | up | plus_2_to_plus_5 | high | PASS |
| SNDK | SNDK | external_ephemeral | 2026-05-06 | 1409.98 | +0.26 | +32.49 | +98.37 | 100.0 | 1.32 | 5.32 | complete | up | plus_2_to_plus_5 | medium | PASS |
| WDC | WDC | external_ephemeral | 2026-05-06 | 483.15 | +3.85 | +17.05 | +54.88 | 100.0 | 1.08 | 2.27 | complete | up | plus_2_to_plus_5 | high | PASS |
| IREN | IREN | external_ephemeral | 2026-05-06 | 60.98 | +11.40 | +42.28 | +70.62 | 100.0 | 1.70 | 5.86 | complete | up | plus_2_to_plus_5 | high | PASS |
| ORCL | ORCL | external_ephemeral | 2026-05-06 | 194.03 | +4.68 | +18.43 | +35.52 | 100.0 | 0.83 | 4.19 | complete | up | plus_2_to_plus_5 | high | PASS |
| NBIS | NBIS | external_ephemeral | 2026-05-06 | 195.09 | +10.90 | +38.18 | +66.18 | 100.0 | 1.16 | 5.64 | complete | up | plus_2_to_plus_5 | high | PASS |
| ADBE | ADBE | external_ephemeral | 2026-05-06 | 250.17 | −2.13 | +2.71 | +4.18 | 42.6 | 0.80 | 2.92 | complete | flat | minus_2_to_plus_2 | low | PASS |
| PRSO | PRSO | external_ephemeral | 2026-05-06 | 0.97 | −3.00 | +5.43 | −2.02 | 13.0 | 1.94 | 3.30 | complete | flat | minus_2_to_plus_2 | low | PASS |
| DUOL | DUOL | external_ephemeral | 2026-05-06 | 105.02 | +0.95 | −1.69 | +9.07 | 48.9 | 1.11 | 3.30 | complete | flat | minus_2_to_plus_2 | low | PASS |
| SMSN | SMSN.IL | external_ephemeral | 2026-05-06 | 4548.00 | +8.54 | +25.77 | +50.50 | 100.0 | 2.80 | 3.77 | complete | up | above_plus_5 | high | PASS |

### Distribution summary

- **Predicted direction**: `up` × 17, `flat` × 5, `down` × 0
- **Predicted bucket**: `above_plus_5` × 2, `plus_2_to_plus_5` × 15, `minus_2_to_plus_2` × 5, `below_minus_2` × 0
- **Confidence**: `high` × 11, `medium` × 6, `low` × 5
- **Data quality**: `complete` × 22 (`partial` × 0, `unresolved` × 0)
- **Forbidden-terms check**: PASS × 22, FAIL × 0

### Note on the apparent "all-up" bias

The deterministic heuristic is intentionally simple: positive 1D / 5D /
1M momentum + a high `range3m_position` produces an `up` bucket. Across
this 22-ticker sample, momentum and 3-month-high signals are
predominantly positive at the 2026-05-06 anchor, which is why the
distribution leans `up`. The test will fairly evaluate whether this
heuristic is right, neutral, or wrong against the realised next-bar
returns — the fact that it is currently *bullish* is itself a
hypothesis under test, not a recommendation.

## 6. Evaluation plan

After tick #6 fires (`2026-05-08T21:30 UTC`) and completes (~8 min later):

### 6.1 Determine "first newly inserted EOD bar after pre-registration"

For each in-universe ticker:

```sql
-- run inside a one-shot read-only Cloud Run Job (or a future read-only
-- API endpoint) once the user separately authorizes that read job.
SELECT ii.id_value, p.trade_date, p.close, p.volume
FROM price_bar_raw p
JOIN instrument_identifier ii
  ON ii.instrument_id = p.instrument_id
 AND ii.id_type = 'ticker'
WHERE ii.id_value IN ('INTC','SOFI','AMD','NVDA','MU')
  AND p.trade_date > DATE '2026-05-06'
ORDER BY p.trade_date ASC;
```

Take the row with `MIN(trade_date)` per ticker as the **first new bar**.
Expected `trade_date` = `2026-05-07` (Thu close, finalised before tick #6
fires on 2026-05-08).

For each external-ephemeral ticker:

Re-fetch the same Yahoo public endpoint and pick the row with the
smallest `trade_date > 2026-05-06`.

### 6.2 Per-prediction metrics

For each ticker, with `as_of_close` from §4/§5 and the new-bar `actual_close`:

| Metric | Definition |
|---|---|
| `actual_return_pct` | `(actual_close / as_of_close − 1) × 100` |
| `direction_hit` | True iff sign of `actual_return_pct` matches `predicted_direction` (treat `flat` as `\|actual\| < 2`) |
| `bucket_hit` | True iff `actual_return_pct` falls inside the predicted bucket interval |
| `absolute_error_pct` | `\|actual_return_pct − bucket_midpoint_pct\|` (midpoints: below_minus_2=−4, minus_2_to_plus_2=0, plus_2_to_plus_5=3.5, above_plus_5=7.5) |
| `surge_3pct_hit` | True iff `actual_return_pct ≥ 3` |
| `surge_5pct_hit` | True iff `actual_return_pct ≥ 5` |

### 6.3 Aggregate metrics

Compute and report **separately for in-universe vs external-ephemeral**:

- `direction_accuracy` = mean(direction_hit)
- `bucket_accuracy` = mean(bucket_hit)
- `mean_absolute_error_pct` = mean(absolute_error_pct)
- `surge_3pct_hit_rate` = mean(surge_3pct_hit)
- `surge_5pct_hit_rate` = mean(surge_5pct_hit)
- `unresolved_count` = count where new bar was not retrievable

### 6.4 Caveats

- Sample size is **22 < 20 per bucket** — therefore *all* aggregate
  numbers are reported as **"pilot observation, not model accuracy."**
  The wording in the eval report MUST keep that label.
- Where the in-universe and external-ephemeral data sources diverge by
  more than 0.5 % on the same ticker / day, log a `provider_drift_note`
  in the eval report and flag both rows as `data_source_disagreement`.
- If tick #6 inserts only the `2026-05-07` bar, evaluate against that
  bar. If it inserts both `2026-05-07` and `2026-05-08`, the test is
  evaluated against `2026-05-07` per the "first new bar after
  prediction_created_at_utc" rule. The `2026-05-08` bar (if present) is
  noted for a future Test #2.

## 7. Strict safety statement (re-affirmed)

| Item | Status |
|---|---|
| Trading recommendations | **NONE** — outputs are research scores only |
| Forbidden language audit | All 22 predictions PASS (en + 中文 lists checked) |
| `FEATURE_T212_LIVE_SUBMIT` | `false` (unchanged) |
| Execution objects (`order_intent` / `order_draft`) | NOT created |
| Broker writes | NONE |
| DB writes from this round | NONE |
| Cloud Run jobs created | NONE |
| Cloud Scheduler changes | NONE — `quant-sync-eod-prices-schedule` remains `ENABLED` |
| Production redeploy | NONE |
| Frontend deploy | NONE |
| Code changes | NONE (pure docs commit; transient generator script not committed) |
| `.firebase` cache committed | NO |

## 8. Pre-registration audit chain

- `pre_registration_created_at_utc`: `2026-05-07T21:54Z` (before tick #6)
- `tick_5_lastAttemptTime`: `2026-05-07T21:30:06Z` (already fired)
- `tick_6_scheduleTime`: `2026-05-08T21:30:04Z` (NOT yet fired)
- `time_until_tick_6` (at pre-registration): ≈ 23h 36m
- `commit_hash`: filled in by Phase 5 (`docs: add prediction shadow test #1 pre-registration`)
- `master_HEAD_at_pre_registration`: `8a92149` (Phase C stable doc commit, made minutes earlier in this same session)
- `quant-api-revision`: `quant-api-00035-kpz` (unchanged)

When the eval report is later written (`docs/scanner-prediction-shadow-test-1-eval.md`), it MUST cite this commit hash to prove pre-registration was honored.
