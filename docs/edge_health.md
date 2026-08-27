# Stage 4 edge health — developer notes

**Status:** research/shadow only (not wired to execution)  
**Code:** `research/edge_health/`  
**Roadmap:** `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` Stage 4  
**Stage 1 consumer:** adapter in `northstar_edge_health.adapter`

This document states what evidence causes each emitted health state. Health
snapshots are **not** orders, stops, or permission to trade. Recommended risk
multipliers are advisory and **subordinate** to any RiskGovernor.

Schema version: `4.0.0`.

## States

| State | Advisory multiplier (default) | Meaning |
|---|---|---|
| `healthy` | `1.0` | Required live properties are inside research bands |
| `degraded` | `0.5` | Edge is weakening; throttle sleeve risk if a governor later accepts the advice |
| `paused` | `0.0` | Stop **new** risk from this sleeve in research logic; still not an order |
| `research_retire_candidate` | `0.0` | Thesis looks broken; candidate for research/retirement review |

Emitted state can lag instantaneous state because of **hysteresis**:

- Soft degraded / paused metrics need consecutive confirmations (`degraded_confirmations=2`, `paused_confirmations=2` by default) so one noisy observation does not flap.
- **Hard pause** (structural break, fail-closed missing/invalid evidence, trend volatility shock) enters immediately.
- **Hard retire** (combined thesis-broken evidence) enters immediately.
- Recovery from pause/retire requires a **cooldown** then consecutive healthy observations (`cooldown_observations=2`, `recovery_confirmations=3`).
- A pause that persists for `retire_confirmations=4` emitted observations becomes `research_retire_candidate` (`mr.chronic_pause` / `trend.chronic_pause`).

Reason codes `hysteresis.hold`, `hysteresis.cooldown_active`, and
`hysteresis.recovery_pending` record why the emitted state did not follow the
instantaneous state.

## Fail-closed codes

These always hard-pause (advisory multiplier `0`) and never assume health:

| Code | Evidence |
|---|---|
| `missing_evidence` | Required field absent (ADF/CADF windows, hedge ratio, residual vol, break flag, friction, trend signs/persistence/whipsaw/shock/breadth/costs) |
| `invalid_evidence` | Non-finite values, negative costs, illegal horizon signs, or `usable=False` |
| `future_observation` | Evidence `as_of` is after the evaluation cutoff |
| `non_monotonic_history` | History / sequence is not strictly increasing in `as_of` |

Point-in-time: `HealthMonitor.evaluate_sequence(..., as_of=cutoff)` ignores later
rows. Future snapshots passed in `history` are ignored, not consumed.

## Mean-reversion evidence → state

Inputs: rolling ADF/CADF behavior, half-life drift, hedge-ratio drift, residual
volatility change, convergence rate, Stage 1 structural-break flag, realized vs
expected friction.

| Code | Default rule | Instantaneous state |
|---|---|---|
| `mr.rolling_adf_nonstationary` | Reject-unit-root fraction ≤ 0.50 or latest ADF p-value ≥ 0.05 | degraded |
| `mr.rolling_adf_nonstationary_severe` | Fraction ≤ 0.20 or latest p-value ≥ 0.25 | paused |
| `mr.rolling_cadf_nonstationary` | Same bands on CADF / Engle-Granger residual p-values | degraded |
| `mr.rolling_cadf_nonstationary_severe` | Severe CADF non-stationarity | paused |
| `mr.half_life_drift` | Symmetric relative drift vs formation baseline ≥ 1.5 | degraded |
| `mr.half_life_extreme_drift` | Relative drift ≥ 3.0 | paused |
| `mr.half_life_undefined` | Live half-life is `None` while a baseline exists (θ ≥ 0) | paused |
| `mr.hedge_ratio_drift` | \|β − β₀\| / \|β₀\| ≥ 0.25 | degraded |
| `mr.hedge_ratio_extreme_drift` | Relative hedge-ratio change ≥ 0.75 | paused |
| `mr.residual_vol_expansion` | σ / σ₀ ≥ 1.5 | degraded |
| `mr.residual_vol_extreme` | σ / σ₀ ≥ 3.0 | paused |
| `mr.convergence_rate_collapse` | Live/baseline convergence ≤ 0.50 (convergence defaults to ln(2)/half-life) | degraded |
| `mr.convergence_rate_extreme` | Ratio ≤ 0.25 | paused |
| `mr.structural_break` | Stage 1 `details.break_detected is True` | **hard pause** |
| `mr.friction_overrun` | realized / expected friction ≥ 1.5 | degraded |
| `mr.friction_extreme_overrun` | Ratio ≥ 3.0 | paused |
| `mr.thesis_broken` | Break **and** half-life undefined/extreme **and** extreme friction or residual vol | **hard retire** |
| `mr.chronic_pause` | Emitted pause persisted for `retire_confirmations` | research/retire candidate |

Worst instantaneous finding wins. Soft findings still pass through hysteresis
before they are emitted.

## Trend evidence → state

Inputs: horizon sign agreement, persistence, whipsaw rate, volatility shock,
realized implementation cost, cross-market breadth.

Horizon agreement is the share of supplied signs equal to the majority of
non-zero signs (`-1` / `0` / `1`). All-zero signs score `0`.

| Code | Default rule | Instantaneous state |
|---|---|---|
| `trend.horizon_sign_disagreement` | Agreement ≤ 0.67 | degraded |
| `trend.horizon_sign_disagreement_severe` | Agreement ≤ 0.34 | paused |
| `trend.persistence_collapse` | Persistence ≤ 0.40 | degraded |
| `trend.persistence_extreme` | Persistence ≤ 0.15 | paused |
| `trend.whipsaw_elevated` | Whipsaw rate ≥ 0.30 | degraded |
| `trend.whipsaw_extreme` | Whipsaw rate ≥ 0.60 | paused |
| `trend.volatility_shock` | `volatility_shock is True` | **hard pause** |
| `trend.friction_overrun` | realized / expected implementation cost ≥ 1.5 | degraded |
| `trend.friction_extreme_overrun` | Ratio ≥ 3.0 | paused |
| `trend.breadth_collapse` | Cross-market breadth ≤ 0.40 | degraded |
| `trend.breadth_extreme` | Breadth ≤ 0.15 | paused |
| `trend.thesis_broken` | Vol shock **and** extreme whipsaw **and** extreme breadth | **hard retire** |
| `trend.chronic_pause` | Emitted pause persisted for `retire_confirmations` | research/retire candidate |

## Advisory risk multiplier (not an order)

`HealthSnapshot.recommended_risk_multiplier` is `1.0` / `0.5` / `0.0` by state.
`apply_advisory(snapshot, positions=..., governor=...)`:

- never mutates `positions`;
- never sets `may_create_order` or `may_mutate_positions`;
- always keeps `subordinate_to_risk_governor=True` and `bypasses_risk_governor=False`;
- authorized multiplier is `min(health recommendation, governor authorization)`,
  clamped to `[0, 1]`;
- a governor that tries to **raise** the multiplier is clamped back to the
  health recommendation (health cannot loosen hard controls; a governor can
  only tighten).

There is still no production `RiskGovernor` module on `main`. Stage 4 defines a
`RiskGovernorPort` and does not implement or weaken one.

## Persistable snapshot

`HealthSnapshot.to_json()` is the audit/attribution record: identity
(`strategy × instrument × horizon`), `as_of`, emitted and instantaneous states,
reason codes/details, hysteresis counters, evidence digest, and the advisory
multiplier. It cannot be deserialized into an object that is allowed to create
an order.

## Stage 1 adapter

`mean_reversion_evidence_from_stage1(...)` reads:

- `rolling_stationarity.details.windows[].adf_pvalue` / `half_life`
- `rolling_parameter_stability.details.windows[].beta` / `residual_std`
- `structural_break.details.break_detected` (Stage 1 contract)
- `half_life.statistics.half_life`
- `cadf.pvalue` and hedge/residual statistics

Unusable Stage 1 results **omit** fields rather than treating them as healthy.
That includes CADF `length_mismatch` / `timestamp_mismatch`, rolling pair
length mismatch, and other `is_usable=false` diagnostics. Rank-deficient
Johansen panels fail closed in Stage 1 and are not ingested here as a healthy
substitute. The adapter records omitted diagnostics under
`evidence.extra["unusable_stage1"]`.

## What Stage 4 intentionally does not do

- Live execution, broker access, or production wiring
- LLM regime discretion
- Creating or mutating paper/live positions
- Bypassing paper-safety gates or a future RiskGovernor
- Stage 2 mean-reversion eligibility, Stage 3 trend construction, Stage 5
  promotion/sizing, or Stage 6 research-loop integration
