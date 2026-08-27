# NorthstarAlpha Stage 6 — Bounded Research Loop

Research / paper only.

This package implements **Stage 6** of `docs/NorthstarAlpha_Chan_Integration_Roadmap.md`.
It is an integration layer: versioned Edge Contracts, bounded proposals, adapters
for Chan Stages 1–5, a deterministic evaluation pipeline, an append-only
experiment registry, and a synthetic morning harness.

It does **not** place orders, mutate paper positions, call a broker, merge,
deploy, or promote a candidate to live. RiskGovernor / paper-safety gates
remain authoritative.

## Why adapters instead of a Stage 2–5 rewrite?

Issue #9 is an assembly task. Stage 1 already exists as draft PR #4
(`northstar_diagnostics`). Stages 2–5 were still in-flight when this package
was started, so Stage 6:

- **reuses** Stage 1 `DiagnosticResult` / `FrictionInputs` / EFR / structural-break contracts;
- **wraps** later packages when they are importable (`discover_stage`);
- **consumes explicit evidence records** and **fails closed** when a later
  module is missing and no evidence was supplied.

That is not a second eligibility/health/promotion engine.

## Install (research environment)

```bash
python3 -m pip install -e "research/statistical_diagnostics[test]"
python3 -m pip install -e "research/research_loop[test]"
python3 -m pytest research/research_loop
python3 -m northstar_research_loop
```

One-command suite (Stage 1 + Stage 6):

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
- Isolation tests forbid broker/order APIs and imports from `hourlyMarketAgent`.
