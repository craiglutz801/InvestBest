# NorthstarAlpha Stage 4 — Edge Health + Structural-Break Monitoring

Research / shadow only.

This package implements **Stage 4** of `docs/NorthstarAlpha_Chan_Integration_Roadmap.md`.
It is a pure Python library. It does **not** place orders, mutate paper positions,
call a broker, change InvestBest / NorthstarAlpha buy/sell behavior, or bypass a
RiskGovernor.

Health snapshots may **recommend** a bounded risk multiplier (`1.0` / reduced /
`0`). That recommendation is advisory and subordinate to hard risk controls.

## Why this home?

Stage 1 diagnostics live in `research/statistical_diagnostics/`. Stage 4 is a
separate research package so:

- health-state contracts stay independently testable (plain evidence dataclasses,
  no statsmodels required);
- a documented adapter maps Stage 1 `DiagnosticResult` objects onto those
  dataclasses when stacking on `cursor/chan-stage1-statistical-diagnostics-fd6c`;
- nothing is imported by `hourlyMarketAgent` or buy/sell rules.

## Stacking / dependency choice

This work is **stacked on Stage 1** (draft PR #4). Direct reuse is the
structural-break `details.break_detected` contract, rolling ADF/half-life
windows, rolling hedge-ratio / residual-vol windows, CADF p-values, and
half-life statistics.

The evaluator does **not** import Stage 1 at runtime. Tests construct evidence
directly. `mean_reversion_evidence_from_stage1(...)` is the adapter.

If Stage 1 is not installed, health contracts remain testable. If Stage 1
results are unusable, the adapter omits fields so health **fails closed**.

## Install (research environment)

```bash
python3 -m pip install -e "research/edge_health[test]"
python3 -m pytest research/edge_health
```

`[test]` optionally pulls `northstar-diagnostics` (Stage 1) for adapter
integration. Core scoring has **no** scientific-stack dependency.

## Public API

| Symbol | Role |
|---|---|
| `HealthMonitor` | Deterministic evaluator with hysteresis / cooldown |
| `HealthSnapshot` | Persistable audit/attribution schema (`to_json` / `from_json`) |
| `HealthState` | `healthy` / `degraded` / `paused` / `research_retire_candidate` |
| `MeanReversionEvidence` / `TrendEvidence` | Family inputs |
| `mean_reversion_evidence_from_stage1` | Stage 1 adapter |
| `apply_advisory` | Bounded multiplier; never mutates positions |

Historical calls take `as_of`. Snapshots after that cutoff are unused.

## Safety boundary

- Research/shadow evidence only.
- No broker / order API (enforced by `tests/test_isolation.py`).
- No import from the hourly paper-trading agent.
- Recommended multipliers cannot exceed 1.0 and cannot raise a governor bound.
- RiskGovernor remains authoritative when present; health cannot bypass it.

See `docs/edge_health.md` for what evidence causes each state.
