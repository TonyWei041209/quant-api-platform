"""Persist the Top-3 Low-Vol strategy as a canonical backtest_run + thesis notes.

Running this creates:
  1. A backtest_run row (with REALISTIC cost model — the honest version)
  2. A thesis note explaining why the strategy worked in 2023-2024
  3. A risk note capturing when / why it might fail

The run becomes visible in Dashboard "Recent Backtests" and the notes appear
in "Recent Notes". The notes' `context` JSONB links back to the run_id so
future research can trace from note to the underlying backtest.

Scope: local dev DB only (6 of the 10 instruments exist only there). To reproduce
in production Cloud SQL, the pilot instruments must first be ingested there.

Guardrails:
- No execution impact (backtest is research-only)
- No broker write
- Notes are read-only documentation
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


def make_lowvol_signal(window: int = 60, top_n: int = 3) -> Callable:
    """Top-N low-volatility signal. Copy of matrix script version for
    reproducibility — kept local to this script so the canonical run is
    self-contained."""
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


STRATEGY_NAME = "top3_lowvol_60d_monthly"


THESIS_TITLE = "Top-3 Low-Vol (60d) survives realistic T212 costs on 2023-2024 pilot universe"

THESIS_BODY = """\
# Why this strategy works (2023-2024)

In the 10-stock pilot universe (AAPL, MSFT, NVDA, SPY + SOFI, F, SIRI, NIO,
LCID, AMC), ranking by 60-day realized volatility and holding the bottom 3
each month produced the highest Sharpe and lowest drawdown of any tested
strategy after realistic T212 GBP->USD cost (slippage 10bps, spread 25bps,
FX 15bps).

Key numbers (realistic cost, 2023-01-01 to 2024-12-31):
- Total return:     +46.6%  (vs +35.1% equal-weight baseline)
- Sharpe ratio:      1.47   (vs 0.55 baseline)
- Max drawdown:    -11.1%   (vs -36.9% baseline)
- Trades over 2y:     54
- Total costs:     $768 on $100k initial capital

## Mechanism

The strategy is essentially a quality / stability filter. In 2023-2024:
- Low-vol ranking consistently preferred SPY / AAPL / MSFT
- It systematically avoided AMC / LCID / SIRI / NIO — which fell 50-70%
- The baseline equal-weight held all 10 and got dragged down by the losers

The "alpha" here is not a smart signal — it is the AVOIDANCE of structurally
broken / meme / near-penny stocks via a simple noise-floor filter.

## Why it survives realistic costs

Only 54 trades in 2 years = low turnover. Cost drag ~38 bps/year, trivial
relative to the 21% annualized return. The strategy does not depend on
micro-moves that costs would eat.

Honesty Report verdict: HONEST (98.0% return retention).
"""


RISK_TITLE = "Low-Vol strategy regime risk — when it will underperform"

RISK_BODY = """\
# When Top-3 Low-Vol will fail

## Bull market / speculative regimes
In 2020-2021, meme and small-cap tech (AMC, LCID, NIO) had enormous upside.
Low-vol filters would have systematically missed those rallies by holding
SPY / boring large caps. Momentum would have dominated instead.

Example: if AMC returns +300% in a year, a Low-Vol strategy that excludes
it captures none of that gain, while equal-weight captures 1/10 of it.

## Rate-sensitive quality factor rotation
Low-vol stocks (utilities, staples in broader universes) are sensitive to
interest rate regimes. When rates rise sharply, "low-vol" names can
underperform as their bond-proxy characteristics reprice.

## Regime-change detection is NOT built in
The strategy has no mechanism to recognize it has entered a hostile regime
and reduce exposure. It will keep rebalancing monthly into the "least
volatile" names even as those names become progressively worse choices.

## Small-sample, single-period warning
This backtest is 2 years, 10 stocks, one broker cost profile. It is
NOT evidence of a durable edge. Treat it as:
- A proof of concept that the Honesty Report workflow works
- A demonstration that quality factor can beat raw high-vol scalping
- Something to validate against 50+ stock universes and multi-regime
  history (2008 GFC, 2020 COVID, 2015 flash crash) before any capital
  commitment

## Decision rules before using this live
1. Re-test on 50+ stocks spanning multiple sectors
2. Include at least one full bull cycle (e.g. 2020-2021) to see factor failure
3. Test on different realistic cost assumptions (wider spread, higher FX)
4. Require minimum 3 independent periods of HONEST verdict before trust

Until then: research artifact only. NOT an execution-eligible strategy.
"""


def main():
    db = get_sync_session()
    try:
        # Resolve universe tickers to instrument_ids
        all_tickers = ["AAPL", "MSFT", "NVDA", "SPY",
                       "SOFI", "F", "SIRI", "NIO", "LCID", "AMC"]
        rows = db.execute(
            text(
                "SELECT id_value, instrument_id::text "
                "FROM instrument_identifier "
                "WHERE id_type='ticker' AND id_value = ANY(:t)"
            ),
            {"t": all_tickers},
        ).fetchall()
        tmap = {r[0]: r[1] for r in rows}
        missing = set(all_tickers) - set(tmap.keys())
        if missing:
            raise SystemExit(f"Missing tickers in DB: {missing}. Run pilot_scalping_universe.py first.")
        instrument_ids = [tmap[t] for t in all_tickers]

        # Build cost model — realistic T212 GBP->USD for a mixed universe
        realistic_cost = CostModel(
            slippage_bps=10.0,
            spread_bps=25.0,
            fx_fee_bps=15.0,
            base_currency="GBP",
        )
        portfolio_cfg = PortfolioConfig(
            max_positions=10,
            rebalance_frequency="monthly",
        )

        # Run + persist the backtest
        signal_fn = make_lowvol_signal(window=60, top_n=3)
        result, run_id = run_and_persist_backtest(
            session=db,
            instrument_ids=instrument_ids,
            start_date=date(2023, 1, 1),
            end_date=date(2024, 12, 31),
            strategy_name=STRATEGY_NAME,
            config=portfolio_cfg,
            cost_model=realistic_cost,
            signal_fn=signal_fn,
        )
        db.commit()

        print(f"Persisted backtest run: {run_id}")
        print(f"  strategy       : {STRATEGY_NAME}")
        print(f"  total_return   : {result.metrics['total_return']*100:.2f}%")
        print(f"  sharpe_ratio   : {result.metrics['sharpe_ratio']:.2f}")
        print(f"  max_drawdown   : {result.metrics['max_drawdown']*100:.2f}%")
        print(f"  total_trades   : {result.metrics['total_trades']}")
        print(f"  total_costs    : ${result.metrics['total_costs']:.2f}")
        print(f"  cost_breakdown : {result.metrics.get('cost_breakdown')}")

        # Write thesis note
        thesis_note = ResearchNote(
            note_id=new_id(),
            instrument_id=None,  # portfolio-level note
            note_type="thesis",
            title=THESIS_TITLE,
            content=THESIS_BODY,
            tags={"tags": ["low-vol", "quality-factor", "honest-verdict", "pilot"]},
            context={
                "backtest_run_id": str(run_id),
                "strategy": STRATEGY_NAME,
                "universe_size": len(instrument_ids),
                "period": "2023-01-01 to 2024-12-31",
                "source": "Strategy Honesty Matrix",
            },
        )
        db.add(thesis_note)

        # Write risk note
        risk_note = ResearchNote(
            note_id=new_id(),
            instrument_id=None,
            note_type="risk",
            title=RISK_TITLE,
            content=RISK_BODY,
            tags={"tags": ["regime-risk", "low-vol", "factor-failure", "pilot"]},
            context={
                "backtest_run_id": str(run_id),
                "strategy": STRATEGY_NAME,
                "related_thesis": str(thesis_note.note_id),
            },
        )
        db.add(risk_note)

        db.commit()

        print()
        print("Research notes persisted:")
        print(f"  thesis note_id : {thesis_note.note_id}")
        print(f"  risk note_id   : {risk_note.note_id}")
        print()
        print("Visible in:")
        print("  - Dashboard 'Recent Backtests' (via /backtest/runs)")
        print("  - Dashboard 'Recent Notes' (via /notes?limit=4)")
        print("  - Research panel filtered by note_type=thesis or note_type=risk")

    finally:
        db.close()


if __name__ == "__main__":
    main()
