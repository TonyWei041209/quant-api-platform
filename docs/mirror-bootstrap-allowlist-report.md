# Mirror Bootstrap — Allowlist Report (read-only)

Status: **read-only report only**. Production write deferred until separately authorized.

## 1. Purpose

This doc describes the allowlist of `NEWLY_RESOLVABLE` tickers that a future production mirror bootstrap would create. It does not execute the bootstrap. The data shown is observed via the read-only `GET /api/instruments/mirror-mapping/plan?fetch_profiles=true` endpoint and the Trading 212 Mirror state.

## 2. How to generate the live allowlist

The allowlist is dynamic — it depends on the user's current Trading 212 Mirror (held + recently traded + manually watched). To capture it deterministically before a bootstrap run:

```bash
# 1. Authenticated browser tab, copy the Firebase ID token from DevTools.
# 2. Capture the live mapping plan into a snapshot file (read-only):

curl -sS \
  -H "Authorization: Bearer ${FIREBASE_ID_TOKEN}" \
  "https://quant-api-188966768344.asia-east2.run.app/api/instruments/mirror-mapping/plan?fetch_profiles=true&include_recent_orders=true&lookback_days=7" \
  | python -m json.tool > /tmp/mirror-mapping-plan-$(date -u +%Y%m%d-%H%M%S).json
```

Then the bootstrap CLI re-derives the same set when run in dry-run:
```bash
gcloud run jobs create quant-ops-mirror-bootstrap-dryrun \
  --region=asia-east2 \
  --image=<current quant-api digest> \
  --command="python" \
  --args="-m,apps.cli.main,bootstrap-mirror-instruments,--dry-run,--fetch-profiles" \
  --task-timeout=300 --max-retries=0 \
  --memory=512Mi \
  --set-secrets=DATABASE_URL_OVERRIDE=DATABASE_URL:latest,FMP_API_KEY=FMP_API_KEY:latest \
  --set-env-vars="APP_ENV=production,DB_TARGET_OVERRIDE=production,PYTHONPATH=/app"
gcloud run jobs execute quant-ops-mirror-bootstrap-dryrun --region=asia-east2 --wait
gcloud run jobs delete quant-ops-mirror-bootstrap-dryrun --region=asia-east2 --quiet
```

The job logs print the per-ticker plan with mapping_status. Save the output as evidence before any production write.

## 3. Observed allowlist (as of 2026-05-09 daytime)

The user has confirmed via the live Dashboard mapping drawer that **AAOI** classifies as `NEWLY_RESOLVABLE` with these provider fields:

| Field | Value (from drawer screenshot) |
|---|---|
| Display ticker | `AAOI` |
| Mapping status | `NEWLY_RESOLVABLE` |
| Company name | (resolved by FMP profile) |
| Exchange | (resolved by FMP profile) |
| Currency | (resolved by FMP profile) |
| Country | (resolved by FMP profile) |
| Asset type | EQUITY |
| Would create | `instrument`, `instrument_identifier`, `ticker_history` (all 3) |

Other Mirror tickers seen in recent T212 order history (per pre-reg `7ff4d83` data and the user's screenshots) that are likely `NEWLY_RESOLVABLE` once FMP is queried:

```
AAOI, AXTI, CRCL, CRWV, DUOL, HIMS, IPOE, IREN, NBIS, NOK,
ORCL, PRSO, RKLB, SNDK, TEM, VACQ, WDC, MRVL, OAC, SMSN
```

The exact list at bootstrap time depends on:
- which tickers are currently held (Trading 212 Mirror endpoint)
- which were filled in the lookback window
- whether FMP returns a profile for each (some thinly-traded tickers may come back `unresolved`)
- which are already mapped (NVDA / AAPL / MSFT / SPY / the 36-ticker scanner universe — these are protected and excluded by `bootstrap_research_universe_prod`)

The report MUST be re-generated immediately before any production write, not based on this static doc.

## 4. Tables a future bootstrap would write

For each `NEWLY_RESOLVABLE` ticker, the bootstrap would create exactly:

| Table | Row count | Columns populated |
|---|---|---|
| `instrument` | 1 per ticker | `instrument_id`, `asset_type`, `issuer_name_current`, `exchange_primary`, `currency`, `country_code`, `is_active=true` |
| `instrument_identifier` | 1 per ticker | `instrument_id`, `id_type='ticker'`, `id_value=<TICKER>`, `source='mirror_bootstrap'`, `valid_from='2020-01-01'`, `valid_to=NULL`, `is_primary=true` |
| `ticker_history` | 1 per ticker | `instrument_id`, `ticker=<TICKER>`, `effective_from='2020-01-01'`, `issuer_name`, `exchange`, `effective_to=NULL`, `source='mirror_bootstrap'` |

Tables explicitly **NOT** touched: `price_bar_raw`, `corporate_action`, `earnings_event`, `financial_*`, `watchlist_*`, `broker_*`, `order_intent`, `order_draft`.

## 5. Production execution gate

Before authorizing the production write, verify:

1. **Pre-flight backup** — Cloud SQL backup taken with description `pre-mirror-bootstrap-YYYYMMDD-HHMM`, status `SUCCESSFUL`.
2. **Dry-run plan captured** — output of the dry-run job from §2 saved as evidence and reviewed.
3. **Allowlist explicit** — the executor sees the same list as the dry-run; no environmental drift between capture and execute.
4. **Protected tickers excluded** — `NVDA / AAPL / MSFT / SPY` not in the plan (the bootstrap module's `PROTECTED_TICKERS` filter is the canonical guard; the dry-run output should show 0 rows for these).
5. **Ambiguous / unresolved tickers excluded** — only `mapping_status == 'newly_resolvable'` qualifies.
6. **No price_bar_raw delta** — verified by row-count diff before/after on `price_bar_raw` (must be 0).
7. **No broker / order / execution table delta** — verified by row-count diff (must all be 0).

The `bootstrap_research_universe_prod.execute_bootstrap` function already enforces (4), (5), and the table allowlist by design; (6) and (7) are belt-and-braces verification.

## 6. Rollback

If a production write needs to be reverted, the deletion order is the inverse of the creation order:

```sql
-- 1) Drop the ticker_history rows scoped to source='mirror_bootstrap'
--    AND in the captured allowlist, AND with no price_bar_raw children.
DELETE FROM ticker_history
WHERE source = 'mirror_bootstrap'
  AND ticker = ANY(:allowlist)
  AND NOT EXISTS (
    SELECT 1 FROM price_bar_raw p
    WHERE p.instrument_id = ticker_history.instrument_id
  );

-- 2) Drop instrument_identifier rows similarly.
DELETE FROM instrument_identifier
WHERE source = 'mirror_bootstrap'
  AND id_value = ANY(:allowlist)
  AND id_type = 'ticker';

-- 3) Drop the instrument rows ONLY when no remaining identifier or
--    history rows reference them (defense in depth — should always
--    be true after steps 1+2 if no other source touched them).
DELETE FROM instrument
WHERE instrument_id IN (
  SELECT instrument_id FROM instrument_identifier
  WHERE source = 'mirror_bootstrap'
)
AND NOT EXISTS (
  SELECT 1 FROM instrument_identifier ii2
  WHERE ii2.instrument_id = instrument.instrument_id
    AND ii2.source <> 'mirror_bootstrap'
);
```

Always run inside a single transaction with `BEGIN; ... ; COMMIT;` and verify counts before commit. The protected scanner-universe rows have `source='bootstrap_research_universe_prod'` so the `WHERE source = 'mirror_bootstrap'` clause naturally excludes them.

## 7. Side-effect attestations (this doc)

| | Status |
|---|---|
| Production DB write | NONE |
| Cloud SQL backup taken | NONE |
| One-shot Cloud Run job created | NONE |
| Production migration | NONE |
| Production sync execution | NONE |
| Scheduler change | NONE |
| Trading 212 write | NONE |
| Live submit | LOCKED |
| `.firebase` cache committed | NO |

This doc is purely descriptive of the procedure. The actual production write requires a separate explicit authorization and a fresh allowlist capture per §2.
