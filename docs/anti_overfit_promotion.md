# Stage 5 — Anti-overfit promotion and conservative sizing

Research-only evaluation framework for NorthstarAlpha. Diagnostics and promotion
gates are **evidence for a human**, not orders, signals, or permission to trade.

Package: `research/anti_overfit_promotion` (`northstar_promotion`).

## What this stage is for

Make backtesting a falsification process:

1. Count every trial, including failures.
2. Attack the candidate with cost, delay, neighborhood, walk-forward, holdout,
   and regime slices.
3. Apply multiple-testing-aware metrics (DSR, PBO/CSCV).
4. If anything required is missing or fails, **reject** (fail-closed).
5. If every configured gate passes, the verdict is `eligible_for_human_review`.
   That is not paper activation, live activation, merge, or deploy.
6. If Kelly is used at all, it is an uncertainty-shrunk **fractional ceiling**,
   subordinate to vol target, concentration, drawdown, exposure, liquidity, and
   RiskGovernor caps.

## Formulas

### Per-period Sharpe

```text
SR_hat = mean(r) / std(r, ddof=1)
```

DSR/PBO use **per-period** Sharpe. Do not mix annualized Sharpe into DSR.

### Deflated Sharpe Ratio (Bailey & López de Prado, 2014)

```text
denom = sqrt(1 - γ3 * SR_hat + ((γ4 - 1) / 4) * SR_hat^2)
V[SR] = denom^2 / (n - 1)
SR0   = sqrt(V[SR]) * [(1-γ) Φ^{-1}(1 - 1/N) + γ Φ^{-1}(1 - 1/(N e))]
DSR   = Φ[ (SR_hat - SR0) * sqrt(n - 1) / denom ]
```

- γ3 = sample skewness, γ4 = Pearson kurtosis (normal = 3)
- γ = Euler–Mascheroni constant ≈ 0.5772156649
- N = trial count (independent-trials assumption)
- For N = 1, SR0 is defined as 0 so DSR reduces to PSR(0)

**Assumptions:** trials are treated as independent (positive correlation among
tried variants *understates* SR0); the expected-max formula is an extreme-value
approximation (slightly biased at small N; exact E[max of two N(0,1)] =
1/sqrt(pi) ≈ 0.564).

More trials raise SR0 and **reduce** DSR. That is the intended multiple-testing
penalty.

### Probability of Backtest Overfitting (CSCV)

Bailey, Borwein, López de Prado, Zhu (2014):

1. Split T bars into S even contiguous slices (S ≥ 4 even).
2. For every combination of S/2 slices as IS, the complement is OOS.
3. Pick the IS-best strategy (highest IS Sharpe).
4. Relative OOS rank λ = mid-rank of that strategy among OOS Sharpes
   (λ = 1 unique OOS best).
5. PBO = Pr(λ < 0.5).

**Assumptions:** exhaustive deterministic combinations (no random subsample);
remainder bars dropped so T is divisible by S; at least two strategies; this is
an estimator, not the exact probability of overfitting. Independent noise across
strategies yields PBO around 1/2 in large samples. A slice-local spike that does
not persist OOS yields PBO near 1.

### Uncertainty-shrunk fractional Kelly (ceiling)

Gaussian / continuous approximation on per-period returns:

```text
f_full = μ / σ²
t = μ / se(μ)
s = t² / (t² + ν)          # default ν = 1
μ_shrunk = s * μ
f_frac = α * (μ_shrunk / σ²)   # default α = 0.25
```

α ≥ 1 (full Kelly) is **rejected**. Ceiling:

```text
f_vol = vol_target / asset_vol
f_ceiling = min(f_frac, f_vol, f_conc, f_exp, f_liq, f_RG, f_hard) * τ_DD
```

τ_DD ∈ [0, 1] is a drawdown throttle. Role is always `ceiling_not_target`.

Missing `risk_governor_cap` is a **warning**, not unlimited capacity. Production
must not size from this number without a RiskGovernor cap. This package does not
implement RiskGovernor.

### Trial-count confidence haircut

Informational, alongside DSR:

```text
h = 1 / sqrt(N_trials)
```

### Cost and delay stress

- Cost: `net = gross - m * cost` with default m ∈ {1.0, 1.5, 2.0}
  (baseline, +50%, +100%).
- Delay: positions shifted forward by d bars (later fill, no lookahead).
- One failed scenario vetoes the candidate.

### Concentration

Herfindahl–Hirschman index and top-k shares on the **positive P&L mass**.
High concentration is always surfaced; it vetoes only when a cap is configured.

### Holdout

Sealed contract: research window, optional embargo, untouched holdout.
Any trial window that touches holdout, `used_holdout=True`, or `as_of` inside
holdout is contamination and fail-closed.

## Fail-closed reason codes

`INSUFFICIENT_SAMPLE`, `INVALID_INPUT`, `MISSING_REQUIRED_EVIDENCE`,
`HOLDOUT_CONTAMINATION`, `HOLDOUT_NOT_SEALED`, `HOLDOUT_FAIL`,
`ISOLATED_OPTIMUM`, `PLATEAU_FAIL`, `COST_STRESS_FAIL`, `DELAY_STRESS_FAIL`,
`CONCENTRATION_FAIL`, `DSR_BELOW_THRESHOLD`, `PBO_ABOVE_THRESHOLD`,
`WALK_FORWARD_FAIL`, `REGIME_SLICE_FAIL`, `KELLY_INVALID`,
`MULTIPLE_TESTING_FAIL`, `TRIAL_COUNT_EXCESSIVE`, `SHADOW_FORWARD_REQUIRED`,
`COMPUTATION_ERROR`.

Default verdict is `reject`. There is no `promote_to_paper` or `promote_to_live`.

## Limitations

- Strategy-agnostic: callers supply returns, trades, parameter grids, and trial
  records. This package does not run strategies or fetch market data.
- DSR independence assumption is optimistic if many nearby parameterizations
  were tried.
- CSCV PBO depends on slice count and the Sharpe metric; other metrics are not
  implemented in this stage.
- Kelly `f* = μ/σ²` is a continuous approximation, not a full discrete
  betting-system Kelly solver.
- Shadow forward testing is a contract flag, not a live paper loop.
- No point-in-time market-data vendor checks beyond index-window `as_of` /
  holdout sealing.
- Not wired into `hourlyMarketAgent`, buy/sell rules, or any broker adapter.

## Blockers

None for this draft. Live broker, production signal activation, full Kelly,
self-promotion, merge, and deploy remain out of scope.

## Safety

No live broker, no production signal activation, no self-promotion, no
merge/deploy, no full-Kelly sizing, no LLM trade decision.
