"""Strategy Honesty Matrix.

Runs multiple low-frequency strategies on the 10-stock pilot universe
(4 large caps + 6 scalping candidates), then compares legacy vs realistic
cost for each. The output is a matrix of verdicts that shows which
strategies actually survive realistic T212 execution friction.

This is NOT a production endpoint — it's a diagnostic composition of existing
backtest + cost-model + honesty-report machinery. Nothing is persisted.

Guardrails:
- No execution impact
- No live submit
- Read-only: only queries price_bar_raw
"""
from __future__ import annotations

from datetime import date
from typing import Callable

import pandas as pd
from sqlalchemy import text

from libs.backtest.engine import CostModel, PortfolioConfig, run_backtest
from libs.db.session import get_sync_session


# ---------------------------------------------------------------------------
# Signal functions (low-frequency, transparent)
# ---------------------------------------------------------------------------

def make_momentum_signal(lookback_days: int = 252, skip_recent: int = 21, top_n: int = 3):
    """12-1 month momentum: return over trailing lookback, skipping last month.

    At each rebalance date, ranks instruments by momentum and allocates
    equal weight to the top_n. Classic Jegadeesh-Titman style.
    """
    def signal_fn(d, prices_df: pd.DataFrame) -> dict:
        if len(prices_df) < lookback_days + skip_recent:
            return {}
        # prices_df is wide: index=date, columns=instrument_id
        # End window: skip_recent days back from today
        end_idx = len(prices_df) - skip_recent - 1
        start_idx = end_idx - lookback_days
        if start_idx < 0:
            return {}
        p_end = prices_df.iloc[end_idx]
        p_start = prices_df.iloc[start_idx]
        momentum = (p_end / p_start - 1).dropna()
        if momentum.empty:
            return {}
        winners = momentum.sort_values(ascending=False).head(top_n).index.tolist()
        w = 1.0 / len(winners)
        return {iid: w for iid in winners}
    return signal_fn


def make_lowvol_signal(window: int = 60, top_n: int = 3):
    """Low-volatility quality proxy: pick top_n instruments with LOWEST
    rolling window-day return vol. Classic 'quality / stability' factor.
    """
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


def make_composite_signal(mom_weight: float = 0.5, top_n: int = 3):
    """Momentum + inverse-volatility composite. Rank by weighted combo.

    Rationale: pure momentum rides winners but buys volatility. Combining
    with low-vol filter is the textbook way to improve risk-adjusted return.
    """
    def signal_fn(d, prices_df: pd.DataFrame) -> dict:
        if len(prices_df) < 252 + 21:
            return {}

        # Momentum ranks
        end_idx = len(prices_df) - 21 - 1
        start_idx = end_idx - 252
        if start_idx < 0:
            return {}
        mom = (prices_df.iloc[end_idx] / prices_df.iloc[start_idx] - 1).dropna()

        # Inverse-vol ranks (higher = better, so negate vol)
        returns = prices_df.pct_change().tail(60)
        inv_vol = (-returns.std()).dropna()

        common = mom.index.intersection(inv_vol.index)
        if len(common) == 0:
            return {}
        # Z-score each and combine
        mom_z = (mom[common] - mom[common].mean()) / (mom[common].std() or 1)
        iv_z = (inv_vol[common] - inv_vol[common].mean()) / (inv_vol[common].std() or 1)
        score = mom_weight * mom_z + (1 - mom_weight) * iv_z

        winners = score.sort_values(ascending=False).head(top_n).index.tolist()
        w = 1.0 / len(winners)
        return {iid: w for iid in winners}
    return signal_fn


# ---------------------------------------------------------------------------
# Honesty comparison helper
# ---------------------------------------------------------------------------

def honesty_compare(
    db, instrument_ids: list[str], start: date, end: date,
    signal_fn: Callable | None,
    rebalance: str,
    legacy_cm: CostModel,
    realistic_cm: CostModel,
) -> dict:
    """Run the same strategy twice (legacy vs realistic) and return deltas."""
    cfg = PortfolioConfig(max_positions=10, rebalance_frequency=rebalance)

    r_legacy = run_backtest(
        session=db, instrument_ids=instrument_ids,
        start_date=start, end_date=end, config=cfg,
        cost_model=legacy_cm, signal_fn=signal_fn,
    )
    r_realistic = run_backtest(
        session=db, instrument_ids=instrument_ids,
        start_date=start, end_date=end, config=cfg,
        cost_model=realistic_cm, signal_fn=signal_fn,
    )
    lm = r_legacy.metrics
    rm = r_realistic.metrics
    if "total_return" not in lm or "total_return" not in rm:
        return {"error": "no data"}

    leg = lm["total_return"]
    real = rm["total_return"]
    retention = (real / leg) * 100 if leg > 0 else (100.0 if real >= 0 else 0.0)

    # Verdict
    if real <= 0:
        verdict = "illusion"
    elif retention >= 85:
        verdict = "honest"
    elif retention >= 50:
        verdict = "degraded"
    else:
        verdict = "illusion"

    return {
        "legacy_return": leg,
        "realistic_return": real,
        "legacy_sharpe": lm.get("sharpe_ratio"),
        "realistic_sharpe": rm.get("sharpe_ratio"),
        "legacy_mdd": lm.get("max_drawdown"),
        "realistic_mdd": rm.get("max_drawdown"),
        "legacy_trades": lm.get("total_trades"),
        "realistic_costs": rm.get("total_costs"),
        "retention_pct": round(retention, 1),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    db = get_sync_session()
    try:
        # Resolve all 10 tickers
        all_tickers = ["AAPL", "MSFT", "NVDA", "SPY",
                       "SOFI", "F", "SIRI", "NIO", "LCID", "AMC"]
        rows = db.execute(text("""
            SELECT id_value, instrument_id::text FROM instrument_identifier
            WHERE id_type='ticker' AND id_value = ANY(:t)
        """), {"t": all_tickers}).fetchall()
        ticker_to_iid = {r[0]: r[1] for r in rows}
        missing = set(all_tickers) - set(ticker_to_iid.keys())
        if missing:
            print(f"WARNING: tickers missing from DB: {missing}")
        instrument_ids = [ticker_to_iid[t] for t in all_tickers if t in ticker_to_iid]

        # Common window (all 10 have data from 2023)
        start = date(2023, 1, 1)
        end = date(2024, 12, 31)

        # Two cost models
        legacy_cm = CostModel(slippage_bps=5.0)
        realistic_cm = CostModel(
            slippage_bps=10.0,       # mixed universe (large + small cap)
            spread_bps=25.0,         # blended spread
            fx_fee_bps=15.0,         # T212 FX
            base_currency="GBP",
        )

        # Define strategies
        strategies = [
            ("Equal-weight all 10 (monthly)",    None,                                  "monthly"),
            ("Equal-weight all 10 (weekly)",     None,                                  "weekly"),
            ("Top-3 Momentum (12-1, monthly)",   make_momentum_signal(252, 21, 3),      "monthly"),
            ("Top-3 Low-Vol (60d, monthly)",     make_lowvol_signal(60, 3),             "monthly"),
            ("Top-3 Mom+LowVol composite (monthly)", make_composite_signal(0.5, 3),     "monthly"),
            ("Top-5 Momentum (monthly)",         make_momentum_signal(252, 21, 5),      "monthly"),
        ]

        # Run the matrix
        print()
        print("=" * 110)
        print("STRATEGY HONESTY MATRIX — 10-stock universe (4 large caps + 6 pilot small/mid caps)")
        print("Window: 2023-01-01 to 2024-12-31. Realistic cost: slip=10, spread=25, fx=15 (T212 GBP->USD)")
        print("=" * 110)
        header = f'{"Strategy":<40}{"Legacy":>10}{"Realistic":>12}{"Retain%":>10}{"Trades":>8}{"Cost$":>10}{"Verdict":>12}'
        print(header)
        print("-" * 110)

        results = []
        for name, sig, freq in strategies:
            r = honesty_compare(
                db, instrument_ids, start, end, sig, freq, legacy_cm, realistic_cm,
            )
            if "error" in r:
                print(f'{name:<40}  ERROR: {r["error"]}')
                continue
            line = (
                f'{name:<40}'
                f'{r["legacy_return"]*100:>9.1f}%'
                f'{r["realistic_return"]*100:>11.1f}%'
                f'{r["retention_pct"]:>10.1f}'
                f'{r["legacy_trades"]:>8d}'
                f'${r["realistic_costs"]:>8.0f}'
                f'{r["verdict"]:>12}'
            )
            print(line)
            results.append({"name": name, **r})

        print()
        print("=" * 110)
        print("INSIGHTS")
        print("=" * 110)
        honest = [r for r in results if r["verdict"] == "honest"]
        degraded = [r for r in results if r["verdict"] == "degraded"]
        illusion = [r for r in results if r["verdict"] == "illusion"]
        print(f"  honest   : {len(honest)} | {[r['name'] for r in honest]}")
        print(f"  degraded : {len(degraded)} | {[r['name'] for r in degraded]}")
        print(f"  illusion : {len(illusion)} | {[r['name'] for r in illusion]}")

        # Compare best honest vs monthly baseline
        if honest:
            best = max(honest, key=lambda r: r["realistic_return"])
            baseline = next((r for r in results if r["name"].startswith("Equal-weight all 10 (monthly)")), None)
            if baseline:
                print()
                print(f"  Best honest strategy: {best['name']}")
                print(f"    Realistic return: {best['realistic_return']*100:.1f}%  "
                      f"(vs baseline {baseline['realistic_return']*100:.1f}%)")
                print(f"    Sharpe:           {best['realistic_sharpe']:.2f}  "
                      f"(vs baseline {baseline['realistic_sharpe']:.2f})")
                print(f"    Max drawdown:     {best['realistic_mdd']*100:.1f}%  "
                      f"(vs baseline {baseline['realistic_mdd']*100:.1f}%)")

    finally:
        db.close()


if __name__ == "__main__":
    main()
