"""Health states and deterministic reason codes.

Emitted states are research/shadow evidence. They never create an order and
never bypass a RiskGovernor.
"""

from __future__ import annotations

from enum import Enum


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    PAUSED = "paused"
    RESEARCH_RETIRE_CANDIDATE = "research_retire_candidate"


STATE_SEVERITY: dict[HealthState, int] = {
    HealthState.HEALTHY: 0,
    HealthState.DEGRADED: 1,
    HealthState.PAUSED: 2,
    HealthState.RESEARCH_RETIRE_CANDIDATE: 3,
}


def worse_state(left: HealthState, right: HealthState) -> HealthState:
    return left if STATE_SEVERITY[left] >= STATE_SEVERITY[right] else right


def is_worse_or_equal(left: HealthState, right: HealthState) -> bool:
    return STATE_SEVERITY[left] >= STATE_SEVERITY[right]


class ReasonCode:
    """Stable reason-code strings persisted on health snapshots."""

    MISSING_EVIDENCE = "missing_evidence"
    INVALID_EVIDENCE = "invalid_evidence"
    FUTURE_OBSERVATION = "future_observation"
    NON_MONOTONIC_HISTORY = "non_monotonic_history"

    MR_ROLLING_ADF_NONSTATIONARY = "mr.rolling_adf_nonstationary"
    MR_ROLLING_ADF_NONSTATIONARY_SEVERE = "mr.rolling_adf_nonstationary_severe"
    MR_ROLLING_CADF_NONSTATIONARY = "mr.rolling_cadf_nonstationary"
    MR_ROLLING_CADF_NONSTATIONARY_SEVERE = "mr.rolling_cadf_nonstationary_severe"
    MR_HALF_LIFE_DRIFT = "mr.half_life_drift"
    MR_HALF_LIFE_EXTREME_DRIFT = "mr.half_life_extreme_drift"
    MR_HALF_LIFE_UNDEFINED = "mr.half_life_undefined"
    MR_HEDGE_RATIO_DRIFT = "mr.hedge_ratio_drift"
    MR_HEDGE_RATIO_EXTREME_DRIFT = "mr.hedge_ratio_extreme_drift"
    MR_RESIDUAL_VOL_EXPANSION = "mr.residual_vol_expansion"
    MR_RESIDUAL_VOL_EXTREME = "mr.residual_vol_extreme"
    MR_CONVERGENCE_COLLAPSE = "mr.convergence_rate_collapse"
    MR_CONVERGENCE_EXTREME = "mr.convergence_rate_extreme"
    MR_STRUCTURAL_BREAK = "mr.structural_break"
    MR_FRICTION_OVERRUN = "mr.friction_overrun"
    MR_FRICTION_EXTREME = "mr.friction_extreme_overrun"
    MR_THESIS_BROKEN = "mr.thesis_broken"
    MR_CHRONIC_PAUSE = "mr.chronic_pause"

    TREND_HORIZON_DISAGREEMENT = "trend.horizon_sign_disagreement"
    TREND_HORIZON_DISAGREEMENT_SEVERE = "trend.horizon_sign_disagreement_severe"
    TREND_PERSISTENCE_COLLAPSE = "trend.persistence_collapse"
    TREND_PERSISTENCE_EXTREME = "trend.persistence_extreme"
    TREND_WHIPSAW_ELEVATED = "trend.whipsaw_elevated"
    TREND_WHIPSAW_EXTREME = "trend.whipsaw_extreme"
    TREND_VOLATILITY_SHOCK = "trend.volatility_shock"
    TREND_FRICTION_OVERRUN = "trend.friction_overrun"
    TREND_FRICTION_EXTREME = "trend.friction_extreme_overrun"
    TREND_BREADTH_COLLAPSE = "trend.breadth_collapse"
    TREND_BREADTH_EXTREME = "trend.breadth_extreme"
    TREND_THESIS_BROKEN = "trend.thesis_broken"
    TREND_CHRONIC_PAUSE = "trend.chronic_pause"

    HYSTERESIS_HOLD = "hysteresis.hold"
    COOLDOWN_ACTIVE = "hysteresis.cooldown_active"
    RECOVERY_PENDING = "hysteresis.recovery_pending"


ALL_REASON_CODES: tuple[str, ...] = tuple(
    value for key, value in vars(ReasonCode).items() if key.isupper() and isinstance(value, str)
)
