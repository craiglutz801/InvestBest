# Stage 1 statistical diagnostics — developer notes

**Status:** research-only foundation (not wired to execution)  
**Code:** `research/statistical_diagnostics/`  
**Roadmap:** `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` Stage 1

This document states what each diagnostic **can** and **cannot** establish. None
of these functions may place an order, mutate a simulated position, or authorize
live trading. Interpretations in `DiagnosticResult` are eligibility evidence, not
signals.

## Common result schema

Every call returns `DiagnosticResult` with:

- `computed_at` / `as_of` timestamps
- formation-window metadata (`sample.n_obs_used`, start/end index and timestamps)
- `method` + `parameters` + `library_versions` (enough to reproduce)
- `statistics`, `pvalue` (when defined), `critical_values`
- `hypotheses`, `assumptions`, `quality_flags`, `interpretation`, `notes`

Quality flags fail-closed on short samples, NaN/Inf, degenerate variance,
unequal or misaligned pair lengths, unsorted or mismatched timestamps,
rank-deficient / constant / duplicate / near-collinear panels, invalid
friction, and other unusable inputs. Point-in-time slicing uses only
observations at or before `as_of`. Unequal-length pair inputs are never
truncated.

## 1. Augmented Dickey-Fuller (`adf_stationarity`)

**Can:** Reject (or fail to reject) a unit-root null on a specified window and
deterministic specification (`n` / `c` / `ct` / `ctt`), using MacKinnon p-values
from statsmodels.

**Cannot:** Prove the series is economically mean-reverting, tradable, or
cointegrated; choose a holding period; survive lag/trend misspecification; or
override the RiskGovernor.

## 2. CADF / Engle-Granger (`cadf_cointegration`)

**Can:** Test residual stationarity of an OLS hedge of `y` on `x` with
cointegration critical values; report the in-sample hedge ratio. `y` and `x`
must be equal-length and date-aligned; mismatched lengths or timestamps fail
closed instead of truncating.

**Cannot:** Guarantee the hedge ratio is stable out of sample; identify which
leg is independent; rule out spurious residual stationarity around breaks; or
imply a pairs trade after costs.

## 3. Johansen (`johansen_cointegration`)

**Can:** Report trace / max-eigen statistics, statsmodels critical values, a
sequential 5% trace suggested rank, and a scaled cointegrating vector.

**Cannot:** Produce unique trading weights (vectors are identified up to
scaling); supply p-values (statsmodels does not); remain reliable in short
samples; or authorize basket trades. Rank-deficient, constant, duplicate, or
near-collinear panels fail closed and do not run Johansen.

## 4. Mean-reversion half-life (`mean_reversion_half_life`)

**Can:** Estimate an AR(1)/OU time scale from `Δy_t = μ + θ y_{t-1} + ε` when
`θ < 0`.

**Cannot:** Be a holding-period recommendation if the DGP is not AR(1); remain
defined when `θ >= 0`; replace cost, horizon, or break checks.

## 5. Hurst (`hurst_diagnostic`)

**Can:** Summarize lagged-difference variance scaling: H ≈ 0.5 (RW-like),
H < 0.5 (anti-persistent), H > 0.5 (persistent). Also reports a Chan-style
lagged-std estimator as a secondary statistic.

**Cannot:** Provide a well-sized p-value in this implementation; overcome short-
sample bias; or establish a tradable edge.

## 6. Variance ratio (`variance_ratio_diagnostic`)

**Can:** Estimate overlapping Lo-MacKinlay VR(q) on first differences of the
level series, with homo- and heteroskedastic z-statistics.

**Cannot:** Translate VR ≠ 1 into a strategy; choose q uniquely; or incorporate
costs.

## 7. Rolling stationarity / parameter stability

**Can:** Describe how ADF p-values, half-lives, OLS hedge ratios, and residual
volatility move across **point-in-time** windows that never peek past the window
end.

**Cannot:** Treat overlapping windows as independent tests; prove future
stability; or emit orders when a window “looks stationary.”

## 8. Structural-break interface (`detect_structural_break`)

**Contract:** `StructuralBreakDetector.detect(...)` → `DiagnosticResult` whose
`details` always include `break_detected` and method metadata, plus
`candidate_index` / `candidate_timestamp` when a date is identified.

Reference implementations:

- `chow_ols` — Chow F test at a pre-specified split, or a max-F scan flagged
  `break_date_estimated` (p-value then anti-conservative)
- `cusum_ols_resid` — Ploberger–Kramer CUSUM of OLS residuals via statsmodels

**Can:** Provide evidence of coefficient/mean instability under those models.

**Cannot:** Name the economic cause; act as a stop or kill switch; or replace a
later Stage 4 health monitor.

## 9. Edge-to-Friction Ratio (`edge_to_friction_ratio`)

**Can:** Compute `expected_gross_edge / expected_round_trip_friction` with
commission, spread, slippage, market impact, borrow fees, dividend substitutes,
financing, futures roll, and other. Research default: label EFR < 2.5 as
fragile (configurable).

**Cannot:** Create trades; validate that the numerator is a real edge; or
replace statistical eligibility tests. Zero, negative, NaN, or Inf friction
fails closed.

## What Stage 1 intentionally does not do

- Strategy parameter optimization
- Production signal activation
- LLM trade decisions
- Broker / order API access
- Live trading
- Changes to `hourlyMarketAgent`, buy/sell rules, or paper-safety gates
- Stage 2 mean-reversion eligibility engine
