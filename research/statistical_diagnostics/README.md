# NorthstarAlpha Stage 1 — Statistical Diagnostics

Research / strategy-eligibility evidence only.

This package implements **Stage 1** of `docs/NorthstarAlpha_Chan_Integration_Roadmap.md`.
It is a pure Python library. It does **not** place orders, mutate paper positions,
call a broker, or change InvestBest / NorthstarAlpha buy/sell behavior.

Active application code remains `apps/web` (Next.js paper-trading MVP). Stage 1
lives here — not inside `hourlyMarketAgent` — so it can be developed in parallel
with the paper-safety PR without touching execution contracts.

## Why this home?

- The production app is TypeScript, but ADF / Engle-Granger / Johansen are mature
  in `statsmodels`. Reimplementing them in JS would add correctness risk.
- `apps/ml-service` is a scoring stub that may later be called from the hourly
  agent. Putting diagnostics there would make accidental trade-path coupling easy.
- `research/` is already the isolated research surface. These functions are
  reusable and typed; Stage 2+ can import them as eligibility evidence later.

## Install (research environment)

```bash
python3 -m pip install -e "research/statistical_diagnostics[test]"
python3 -m pytest research/statistical_diagnostics
```

From this directory:

```bash
python3 -m pip install -e ".[test]"
python3 -m pytest
```

## New dependencies

| Package | Why it is needed |
|---|---|
| `numpy` | Point-in-time slicing, OLS, Hurst / variance-ratio / half-life estimators |
| `scipy` | Normal and F tails for Lo-MacKinlay and Chow p-values; required by statsmodels |
| `statsmodels` | ADF, Engle-Granger/CADF (`coint`), Johansen, CUSUM of OLS residuals |
| `pytest` (optional extra) | Deterministic unit tests |

No broker SDK, no HTTP trading client, no execution extra.

## Public API

All diagnostics return `DiagnosticResult` (see `schema.py`): timestamps,
formation-window metadata, method parameters, statistics, p-value / critical
values where they exist, assumptions, quality flags, and an interpretation that
is **explicitly not a trade**.

| Function | Module |
|---|---|
| `adf_stationarity` | ADF unit-root test |
| `cadf_cointegration` | Engle-Granger / CADF pair residual cointegration |
| `johansen_cointegration` | Johansen trace / max-eigen rank |
| `mean_reversion_half_life` | AR(1) half-life from Δy on y_lag |
| `hurst_diagnostic` | Lagged-difference variance Hurst |
| `variance_ratio_diagnostic` | Lo-MacKinlay overlapping VR |
| `rolling_stationarity` | Rolling ADF + half-life |
| `rolling_parameter_stability` | Rolling OLS hedge ratio / residual vol |
| `detect_structural_break` | Chow / CUSUM OLS residual contract |
| `edge_to_friction_ratio` | EFR = gross edge / round-trip friction |

Historical calls take `as_of` (inclusive index or timestamp). Observations after
that cutoff are never used.

## Safety boundary

- Diagnostics are evidence for **strategy eligibility research** only.
- No module accesses a broker or order API (enforced by `tests/test_isolation.py`).
- No module is imported by `hourlyMarketAgent` or the buy/sell rule files.
- RiskGovernor / paper-safety gates are not modified here.

See `docs/statistical_diagnostics.md` for what each test can and cannot establish.
