# NorthstarAlpha — Chan Integration Roadmap

**Status:** Approved research/build direction  
**Date:** 2026-08-26  
**Project:** NorthstarAlpha (repository remains `InvestBest`)  
**Purpose:** Convert Ernest P. Chan’s durable systematic-trading principles into an agent-executable NorthstarAlpha build sequence.

## Authority and safety boundary

This document extends the existing NorthstarAlpha/InvestBest architecture. It does **not** replace the paper-safety architecture, execution boundary, RiskGovernor, point-in-time data rules, auditability requirements, or human merge gate.

The central Chan-inspired rule is:

> Never trade a pattern merely because it backtested well. Require a defensible mechanism, measurable evidence that the required market behavior exists, enough expected edge to survive friction and uncertainty, and a predefined way to detect when the thesis has broken.

Nothing in this roadmap guarantees profits. The objective is to improve the probability of retaining genuine risk-adjusted edge while reducing false positives, overfitting, cost leakage, regime mismatch, and sizing mistakes.

## Architectural change

Move from:

```text
DATA -> FEATURES -> SIGNALS -> PORTFOLIO -> RISK -> EXECUTION
```

Toward:

```text
DATA
  -> POINT-IN-TIME VALIDATION
  -> FEATURES
  -> EDGE MECHANISM
  -> STATISTICAL DIAGNOSTICS
  -> STRATEGY ELIGIBILITY
  -> SIGNAL
  -> EXPECTED EDGE AFTER COST + UNCERTAINTY HAIRCUT
  -> EDGE HEALTH / REGIME COMPATIBILITY
  -> PORTFOLIO CONSTRUCTION
  -> FRACTIONAL-KELLY CEILING
  -> RISK GOVERNOR
  -> EXECUTION
  -> ATTRIBUTION
  -> HEALTH / DECAY MONITORING
  -> RESEARCH LOOP
```

Diagnostics are evidence for eligibility. **No diagnostic may place an order.**

## Required Edge Contract

Every strategy family should eventually carry a versioned Edge Contract containing:

- economic/behavioral mechanism;
- statistical property required for the edge;
- eligible instruments and horizons;
- expected holding period;
- expected implementation costs;
- regimes where it should work and fail;
- formation tests;
- live health tests;
- structural-break conditions;
- retirement/throttle rules.

NorthstarAlpha should reason in `strategy × instrument × horizon`, not just `strategy × ticker`.

---

# Stage 1 — Statistical Diagnostics Foundation

**Build this first.** This stage is deliberately isolated from production decision logic so it can be implemented safely while paper-trading hardening is being completed.

### Required diagnostics

1. Augmented Dickey-Fuller stationarity test.
2. CADF / pair residual cointegration test.
3. Johansen multivariate cointegration test.
4. Mean-reversion half-life estimate.
5. Hurst-exponent diagnostic.
6. Variance-ratio diagnostic.
7. Rolling stationarity / parameter-stability diagnostics.
8. Structural-break interface and result contract.
9. Edge-to-Friction Ratio calculation.
10. Common diagnostic result schema with timestamps and formation-window metadata.

### Edge-to-Friction Ratio

At minimum:

```text
EFR = expected_gross_edge / expected_round_trip_friction
```

Friction must be able to include commission, spread, slippage, market impact, borrow fees/dividend substitutes for shorts, financing where relevant, and futures roll effects.

Research defaults may classify EFR roughly as fragile below ~2.5 and more implementation-resilient above that, but thresholds must remain configurable and must not create trades by themselves.

### Stage 1 acceptance criteria

- All calculations deterministic and unit tested.
- Historical calculations use only information available at the timestamp being evaluated.
- Synthetic tests include known stationary, random-walk, trending, and cointegrated series.
- Tests include degenerate inputs, missing data, short samples, NaN/Inf values, and unstable/near-singular cases.
- Every result reports assumptions, sample/window metadata, statistic(s), confidence/p-value where appropriate, and quality flags.
- No module accesses a broker or order API.
- No module modifies production positions or trade decisions.
- No live trading capability is added.
- RiskGovernor remains authoritative.
- Developer documentation explains what each statistical test can and cannot establish.
- The Stage 1 PR is a **draft PR** and may not be merged without Craig’s explicit approval.

### Stage 1 implementation guidance

Before writing code, the agent must inspect the actual repository and choose the correct home for diagnostics rather than blindly following an older folder diagram. Prefer pure, reusable functions with a stable typed result contract. Avoid unnecessary framework coupling.

The agent should document every new dependency and prefer mature statistical libraries where they improve correctness. Wrappers should normalize output and make tests deterministic.

---

# Stage 2 — Mean-Reversion Eligibility Engine

Do not treat generic oversold/overbought conditions as sufficient evidence of mean reversion.

Build candidate formation and eligibility around:

- economically related candidate universe first;
- CADF/Johansen evidence where appropriate;
- residual/spread stationarity;
- half-life compatible with intended holding period;
- rolling hedge-ratio stability;
- rolling spread-volatility stability;
- structural-break veto;
- cost cushion / EFR;
- liquidity and shortability checks when applicable;
- explicit event/fundamental-divergence vetoes.

Potential entry thresholds (e.g. residual z-score) come **after** statistical eligibility. Exit as the residual normalizes or eligibility deteriorates. A collapsing security must not be purchased simply because it is statistically distant from a historical mean.

Stage 2 remains research/shadow-first until it clears normal promotion gates.

---

# Stage 3 — Multi-Speed Trend + Futures Carry Context

Trend should be a diversified primary return engine rather than one indicator.

Research a multi-speed time-series momentum ensemble such as approximately 1m / 3m / 6m / 12m horizons, with:

- volatility normalization;
- signal-strength caps;
- long/short expression only where permitted by the system and broker/risk design;
- cross-asset diversification;
- explicit horizon metadata;
- neighboring-parameter robustness tests;
- regime and trend-health diagnostics.

For futures, separate research continuous series from executable contract economics. Model actual contract selection, rolls, and curve/carry effects. Trend and carry should inform confidence without double-counting the same exposure.

No trend enhancement is promoted because one optimized lookback wins a backtest.

---

# Stage 4 — Edge Health + Structural-Break Monitoring

Create explicit health signals for each strategy family. Examples:

### Mean-reversion health
- rolling ADF/CADF behavior;
- half-life drift;
- hedge-ratio drift;
- residual-volatility change;
- convergence rate;
- structural-break flags;
- realized vs expected cost.

### Trend health
- sign agreement across horizons;
- realized trend persistence;
- volatility shock state;
- whipsaw rate;
- realized implementation cost;
- cross-market breadth.

Health metrics may throttle sleeve risk within pre-approved bounds. They do not authorize unrestricted AI discretion.

The system must define what evidence causes `healthy`, `degraded`, `paused`, or `retire/research` states.

---

# Stage 5 — Anti-Overfit Promotion + Conservative Sizing

Make backtesting a falsification process rather than a beauty contest.

Every serious candidate should be attacked with:

- point-in-time data checks;
- realistic costs and cost stress (+50%, +100% scenarios where sensible);
- execution-delay stress;
- parameter-neighborhood/plateau tests;
- multiple formation windows;
- walk-forward evaluation;
- untouched final holdout;
- regime slices;
- trade/P&L concentration diagnostics;
- explicit experiment/trial counting;
- multiple-testing-aware metrics such as Deflated Sharpe Ratio and Probability of Backtest Overfitting concepts;
- shadow forward testing before promotion.

Store failed experiments, not just winners.

Kelly sizing, if used, is an **uncertainty-shrunk fractional-Kelly ceiling**, never a full-Kelly target. It remains subordinate to volatility targets, concentration limits, drawdown throttles, exposure caps, liquidity constraints, and the RiskGovernor.

---

# Stage 6 — Research Loop Integration

NorthstarAlpha’s improvement/research agent may propose bounded changes to strategy configs, thresholds, feature sets, formation windows, and health settings, but every proposal must run through the deterministic evaluation and promotion gates above.

Good agent uses:
- propose hypotheses;
- compare diagnostics;
- identify broken assumptions;
- create controlled experiments;
- summarize attribution;
- propose bounded config changes.

Disallowed:
- free-form trades from news;
- bypassing risk rules;
- self-approving live deployment;
- optimizing only recent P&L;
- hiding failed experiments;
- changing broker/execution safety code as part of a strategy experiment.

---

# Chan Test — Mandatory Strategy Review

Before a strategy reaches paper promotion, it should answer:

1. Why should this edge exist?
2. Who/what creates the inefficiency?
3. Why should it persist after costs and competition?
4. What measurable property must be true?
5. Is that property present out of sample?
6. Is it stable through time?
7. What is expected edge after realistic friction?
8. What happens if costs are materially higher?
9. What happens with delayed execution?
10. Does it work around neighboring parameters?
11. Does it work across multiple windows/regimes?
12. How many variants were tested before this one won?
13. Does multiple-testing-aware evaluation still support it?
14. What does a structural break look like?
15. What live metric stops new risk?
16. What regime should hurt the strategy?
17. What portfolio risk does it add?
18. What existing risk does it diversify?
19. How much capital survives uncertainty haircuts and hard risk limits?

If these cannot be answered with evidence, the strategy is not ready.

---

# Build order

1. Statistical Diagnostics Foundation.
2. Statistical mean-reversion eligibility.
3. Multi-speed trend and futures carry context.
4. Edge-health / structural-break monitoring.
5. Anti-overfit promotion and conservative sizing.
6. Research-loop integration.

Each stage gets its own scoped issue/branch/draft PR unless a later explicit approval changes that rule.

## Current sequencing note

A separate draft PR is hardening the paper-only safety and market-data gates. The Stage 1 diagnostics work may be developed in parallel **only because it must remain isolated from trade activation and execution behavior**. The paper-safety work should be merged/reconciled first if the two branches touch the same files or contracts.

## Completion contract for every Cursor stage

- Inspect current `main` before coding.
- State files expected to change.
- State new dependencies.
- Implement only the approved stage.
- Add/execute focused tests plus existing relevant regression tests.
- Open a draft PR.
- Report tests, deviations, limitations, and blockers.
- Do not merge.
- Do not deploy.
- Do not enable live trading.
- Stop for ChatGPT review and Craig’s merge approval.
