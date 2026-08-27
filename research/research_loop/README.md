# NorthstarAlpha Stage 6 — Bounded Research Loop

Research / paper only.

This package implements **Stage 6** of `docs/NorthstarAlpha_Chan_Integration_Roadmap.md`.
It is an integration layer: versioned Edge Contracts, bounded proposals, adapters
for Chan Stages 1–5, a deterministic evaluation pipeline, an append-only
experiment registry, and a synthetic morning harness.

It does **not** place orders, mutate paper positions, call a broker, merge,
deploy, or promote a candidate to live. RiskGovernor / paper-safety gates
remain authoritative.

## Native Stage 1–5 APIs

On this integration branch the adapters call typed public functions:

| Stage | Call |
|---|---|
| 1 | `cadf_cointegration`, `edge_to_friction_ratio` |
| 2 | `evaluate_candidate(candidate, *, config=)` |
| 3 | `evaluate_asset_trend(series, ...)`, `refuse_performance_sweep_selection` |
| 4 | `HealthMonitor.evaluate(evidence, *, identity=)` |
| 5 | `evaluate_promotion(evidence, config=)`, `kelly_ceiling(returns, *, caps=)`; DSR gets registry `trial_sharpes` (no invented `sharpe_trials_variance`) |

`require_native_stages()` fails the harness if any of those packages is missing. There is no silent `synthetic_fail_closed` pass.

## Install (research environment)

```bash
bash research/run_chan_research_tests.sh
```

## Pipeline

```text
proposal + Edge Contract
  -> Stage 1 diagnostics
  -> Stage 2 eligibility
  -> after-friction (EFR + cost stress)
  -> Stage 5 robustness / anti-overfit
  -> Stage 4 health
  -> Stage 5 conservative sizing ceiling (advisory)
  -> state machine
  -> append-only registry (winners and failures)
```

Legal candidate statuses: `proposed`, `rejected`, `research-qualified`,
`shadow-ready`, `paused`, `retired`. There is no `live` status.

Allowed mutation targets: `strategy_config`, `thresholds`, `feature_set`,
`formation_window`, `health_settings`.

## New dependencies

None at runtime. Tests use `pytest`. Stage 1 `numpy` / `scipy` / `statsmodels`
are used only when `northstar_diagnostics` is installed. No broker SDK.

## Safety boundary

- Agent capability bitmap cannot place a trade, bypass risk, self-merge,
  self-deploy, or self-promote to live.
- Health `advisory_risk_multiplier` never mutates positions.
- Fractional-Kelly output is a **ceiling**, clamped below hard risk caps,
  never a full-Kelly target, always marked subordinate to RiskGovernor.
  Health’s advisory multiplier is applied **once** (not also as
  `drawdown_throttle`). Missing `risk_governor_cap` fails closed at 0;
  the adapter does not invent a 20% governor cap.
- Isolation tests forbid broker/order APIs and imports from `hourlyMarketAgent`.
