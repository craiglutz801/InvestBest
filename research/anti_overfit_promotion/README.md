# NorthstarAlpha Stage 5 — Anti-Overfit Promotion + Conservative Sizing

Research / falsification evidence only.

This package implements **Stage 5** of `docs/NorthstarAlpha_Chan_Integration_Roadmap.md`.
It is a pure Python library. It does **not** place orders, mutate paper positions,
call a broker, change InvestBest / NorthstarAlpha buy/sell behavior, or
self-promote a candidate to paper or live.

The only non-reject promotion verdict is `eligible_for_human_review`.

## Why this home?

- Stage 1 diagnostics already live under `research/` as an isolated Python package.
  Stage 5 is the same kind of work: numerical, strategy-agnostic, and dangerous if
  accidentally imported by the hourly agent.
- `apps/web` is TypeScript paper-trading. Promotion math (DSR, CSCV/PBO, Kelly
  ceiling) belongs in a testable research library, not in execution code.
- `apps/ml-service` is a scoring stub. Putting promotion gates there would make
  accidental trade-path coupling easy.

## Install (research environment)

```bash
python3 -m pip install -e "research/anti_overfit_promotion[test]"
python3 -m pytest research/anti_overfit_promotion
```

From this directory:

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest
```

## New dependencies

| Package | Why it is needed |
|---|---|
| `numpy` | Returns math, walk-forward slicing, CSCV combinations, concentration |
| `scipy` | Normal CDF/PPF and sample skew/kurtosis for Deflated Sharpe Ratio |
| `pytest` (optional extra) | Deterministic unit tests |

No broker SDK, no HTTP trading client, no execution extra, no statsmodels.

DSR and PBO are implemented from the published formulas rather than wrapped
from a trading library (there is no single mature, pin-able library that is
clearly preferable here). Formulas and assumptions are on every result object
and in `docs/anti_overfit_promotion.md`.

## Public API

| Function | Role |
|---|---|
| `ExperimentRegistry` | Append-only trial ledger (failures included) |
| `formation_windows` / `walk_forward_splits` | PIT formation + walk-forward |
| `seal_holdout` / `audit_holdout` | Untouched final holdout contract |
| `evaluate_plateau` | Parameter-neighborhood / isolated-optimum check |
| `cost_stress` / `execution_delay_stress` | Friction and delay vetoes |
| `trade_pnl_concentration` | Trade/P&L concentration |
| `evaluate_regime_slices` | Regime-slice contract |
| `deflated_sharpe_ratio` | Bailey–López de Prado DSR |
| `probability_of_backtest_overfitting` | CSCV PBO estimator |
| `kelly_ceiling` | Uncertainty-shrunk fractional-Kelly **ceiling** |
| `evaluate_promotion` | Fail-closed decision with reason codes |

## Safety boundary

- No module accesses a broker or order API (`tests/test_isolation.py`).
- No module is imported by `hourlyMarketAgent` or the buy/sell rule files.
- Kelly is never a target. Full Kelly (`fraction >= 1`) is rejected.
- RiskGovernor remains authoritative; this package does not implement or bypass it.
- Passing gates ≠ paper promotion ≠ live trading.

See `docs/anti_overfit_promotion.md` for formulas, assumptions, and limitations.
