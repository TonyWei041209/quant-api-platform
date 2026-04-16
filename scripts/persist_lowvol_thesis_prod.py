"""Persist the 4-stock Low-Vol baseline run to the CONNECTED database.

This is the production variant of persist_lowvol_thesis.py — restricted to the
4 large caps that exist in production Cloud SQL (AAPL, MSFT, NVDA, SPY). No
dependency on the 6 pilot instruments.

Intended execution: as a one-off Cloud Run Job that reuses the existing
container image (which has Cloud SQL connection configured via
DATABASE_URL_OVERRIDE secret). This way no local cloud-sql-proxy is required.

Idempotency: re-running creates an additional backtest_run (each run has a
unique UUID). If you run it twice you get two canonical runs with the same
strategy name — distinguishable only by created_at / run_id. This is
intentional: reruns can legitimately reflect updated data.

Guardrails:
- No execution impact
- No broker write
- No production write other than backtest_run + backtest_trade + research_note
- Top-N = 2 (since universe is only 4 stocks; top 2 of 4 keeps meaningful
  dispersion. Top 3 of 4 is almost equal-weight.)
"""
from __future__ import annotations

from datetime import date
from typing import Callable

import pandas as pd
from sqlalchemy import text

from libs.backtest.engine import CostModel, PortfolioConfig, run_and_persist_backtest
from libs.core.ids import new_id
from libs.core.logging import get_logger
from libs.db.models.research_note import ResearchNote
from libs.db.session import get_sync_session

logger = get_logger(__name__)

STRATEGY_NAME = "top2_lowvol_60d_monthly_prod_baseline"


def make_lowvol_signal(window: int = 60, top_n: int = 2) -> Callable:
    def signal_fn(d, prices_df: pd.DataFrame) -> dict:
        if len(prices_df) < window + 1:
            return {}
        returns = prices_df.pct_change().tail(window)
        vol = returns.std().dropna()
        if vol.empty:
            return {}
        winners = vol.sort_values(ascending=True).head(top_n).index.tolist()
        w = 1.0 / len(winners)
        return {iid: w for iid in winners}
    return signal_fn


THESIS_TITLE = "Top-2 Low-Vol (60d) production baseline — 4 large caps, 2023-2024"

THESIS_BODY = """\
# Why this strategy persists here as a baseline

This run is the production baseline of the Low-Vol quality factor workflow.
It runs only on the 4 large-cap instruments that exist in production Cloud SQL
(AAPL, MSFT, NVDA, SPY) — so it CAN be re-run, audited, and compared over time
in this environment without relying on any dev-only pilot data.

## Mechanism
At each month end, rank the 4 instruments by 60-day realized volatility and
hold the bottom 2 equal-weighted for the following month.

## Why keep this as a baseline
- The universe here is too small (4) for Low-Vol to produce the same dramatic
  results seen in the 10-stock dev experiment.
- The value is NOT "this will make money" — it's "here is the honesty-verified
  Low-Vol workflow on production data, verifiable any time."
- Any future quality/factor strategy should be compared against THIS baseline
  first, not against an idealized benchmark.

## Regime assumptions
- Cost model: T212 GBP->USD realistic (slippage 10bps, spread 25bps, FX 15bps)
- Rebalance frequency: monthly
- Holding: top 2 of 4 by low-volatility (50% each)
- Warm-up: first 60 days needed before any rebalance

## Cross-links
- Related dev-environment thesis: `top3_lowvol_60d_monthly` (10-stock universe,
  persisted in local dev DB only)
- Honesty Report endpoint: `POST /backtest/honesty-report` can re-run this
  comparison anytime
"""

RISK_TITLE = "Low-Vol production baseline — regime & universe risk"

RISK_BODY = """\
# When this production baseline is misleading

## Universe too small to be decisive
Only 4 instruments. Top-2 of 4 is essentially "pick the two most boring of four
well-known names". The result will largely track SPY + one other large cap.
This is NOT an independent factor test — it's a proof that the infrastructure
works end-to-end against production data.

## Homogeneous universe
AAPL / MSFT / NVDA are all US mega-cap tech. Low-vol vs high-vol distinctions
within this set are small. The factor's power comes from excluding genuinely
different assets (staples, utilities, cash). That exclusion is absent here.

## Do not treat as execution evidence
This run exists so that:
1. The production backtest_run + research_note pipeline is verified end-to-end
2. Future broader-universe experiments have an anchor baseline for comparison

It is NOT evidence that this specific strategy is tradeable. Before any
capital commitment:
- Expand universe to 50+ instruments spanning sectors
- Re-test on multiple regimes (2020-2021 bull, 2022 bear, 2023-2024 recovery)
- Add out-of-sample hold-out period
- Verify honest verdict survives realistic cost variations
"""


def main() -> None:
    session = get_sync_session()
    try:
        engine = session.get_bind()
        url_str = str(engine.url)
        # Only print whether we're talking to Cloud SQL or localhost (no creds)
        if "cloudsql" in url_str.lower() or "/cloudsql/" in url_str:
            env_label = "Cloud SQL (production)"
        elif "localhost" in url_str or "127.0.0.1" in url_str:
            env_label = "localhost (dev)"
        else:
            env_label = "unknown"
        print(f"DB target: {env_label}")

        # Resolve 4 large-cap tickers
        tickers = ["AAPL", "MSFT", "NVDA", "SPY"]
        rows = session.execute(
            text(
                "SELECT id_value, instrument_id::text "
                "FROM instrument_identifier "
                "WHERE id_type='ticker' AND id_value = ANY(:t)"
            ),
            {"t": tickers},
        ).fetchall()
        tmap = {r[0]: r[1] for r in rows}
        missing = set(tickers) - set(tmap.keys())
        if missing:
            raise SystemExit(f"Missing tickers in DB: {missing}. Aborting.")
        instrument_ids = [tmap[t] for t in tickers]

        # Realistic cost (T212 GBP -> USD)
        realistic_cost = CostModel(
            slippage_bps=10.0,
            spread_bps=25.0,
            fx_fee_bps=15.0,
            base_currency="GBP",
        )
        portfolio_cfg = PortfolioConfig(
            max_positions=4,
            rebalance_frequency="monthly",
        )

        signal_fn = make_lowvol_signal(window=60, top_n=2)
        result, run_id = run_and_persist_backtest(
            session=session,
            instrument_ids=instrument_ids,
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            strategy_name=STRATEGY_NAME,
            config=portfolio_cfg,
            cost_model=realistic_cost,
            signal_fn=signal_fn,
        )
        session.commit()

        print(f"\nPersisted backtest run: {run_id}")
        print(f"  strategy       : {STRATEGY_NAME}")
        print(f"  total_return   : {result.metrics['total_return']*100:.2f}%")
        print(f"  sharpe_ratio   : {result.metrics['sharpe_ratio']:.2f}")
        print(f"  max_drawdown   : {result.metrics['max_drawdown']*100:.2f}%")
        print(f"  total_trades   : {result.metrics['total_trades']}")
        print(f"  total_costs    : ${result.metrics['total_costs']:.2f}")

        thesis = ResearchNote(
            note_id=new_id(),
            instrument_id=None,
            note_type="thesis",
            title=THESIS_TITLE,
            content=THESIS_BODY,
            tags={"tags": ["low-vol", "production-baseline", "quality-factor"]},
            context={
                "backtest_run_id": str(run_id),
                "strategy": STRATEGY_NAME,
                "universe_size": 4,
                "period": "2023-01-01 to 2024-12-31",
                "source": "persist_lowvol_thesis_prod.py",
                "environment": env_label,
            },
        )
        session.add(thesis)

        risk = ResearchNote(
            note_id=new_id(),
            instrument_id=None,
            note_type="risk",
            title=RISK_TITLE,
            content=RISK_BODY,
            tags={"tags": ["production-baseline", "universe-limit", "regime-risk"]},
            context={
                "backtest_run_id": str(run_id),
                "strategy": STRATEGY_NAME,
                "related_thesis": str(thesis.note_id),
            },
        )
        session.add(risk)
        session.commit()

        print(f"\nResearch notes persisted:")
        print(f"  thesis note_id : {thesis.note_id}")
        print(f"  risk note_id   : {risk.note_id}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
