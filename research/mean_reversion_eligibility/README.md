# NorthstarAlpha Stage 2 — Mean-Reversion Eligibility Engine

Research / shadow-only.

This package implements **Stage 2** of `docs/NorthstarAlpha_Chan_Integration_Roadmap.md`.
It decides whether a **declared, economically related** pair or basket is statistically
eligible as a mean-reversion *candidate*. It does **not** place orders, mutate paper
positions, call a broker, or change InvestBest / NorthstarAlpha buy/sell behavior.

Residual z-score entry timing lives in `evaluate_shadow_entry` and runs **only after**
formation gates pass. An oversold or collapsing security is not purchased because it
is far from a historical mean.

Active application code remains `apps/web` (Next.js paper-trading MVP). Stage 2 lives
here — not inside `hourlyMarketAgent` — stacked on the Stage 1 diagnostics package.

## Why this home?

- Stage 1 already lives in `research/statistical_diagnostics/` as a Python library
  using statsmodels. Stage 2 is an eligibility layer over those diagnostics.
- `apps/ml-service` and `hourlyMarketAgent` are production/paper decision paths.
  Putting eligibility there would make accidental trade-path coupling easy.
- LLM ticker generation is explicitly **not** used to discover a universe.

## Install (research environment)

```bash
python3 -m pip install -e research/statistical_diagnostics
python3 -m pip install -e "research/mean_reversion_eligibility[test]"
python3 -m pytest research/mean_reversion_eligibility
python3 -m pytest research/statistical_diagnostics
```

## New dependencies

No new third-party libraries. Stage 2 imports Stage 1 (`northstar-diagnostics`) and
uses its existing `numpy` / `scipy` / `statsmodels` stack. Pytest is an optional test extra.

No broker SDK, no HTTP trading client, no execution extra.

## Public API

| Symbol | Role |
|---|---|
| `EconomicCandidate` / `EconomicCandidateUniverse` | Caller-supplied economically related groups |
| `LiquiditySnapshot` | Caller-supplied ADV / spread / shortability (no live broker) |
| `EventVetoFlags` | Deterministic event / fundamental-divergence vetoes |
| `evaluate_candidate` / `evaluate_universe` | Formation/eligibility decision with reason codes |
| `evaluate_shadow_entry` | Residual z-score timing **after** eligibility |

Every `EligibilityDecision` includes gate-level reason codes and the Stage 1
`DiagnosticResult` evidence used (CADF/Johansen, ADF, half-life, rolling hedge,
structural break, EFR). `eligible=True` is not a trade.

Historical calls take `as_of` (inclusive index or timestamp). Observations after
that cutoff are never used.

## Safety boundary

- Eligibility is evidence for **research/shadow mean-reversion formation** only.
- No module accesses a broker or order API (enforced by `tests/test_isolation.py`).
- No module is imported by `hourlyMarketAgent` or the buy/sell rule files.
- RiskGovernor / paper-safety gates are not modified here.

See `docs/mean_reversion_eligibility.md` for what each gate can and cannot establish.
