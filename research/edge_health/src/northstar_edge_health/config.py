"""Configurable thresholds, hysteresis, and advisory risk multipliers."""

from __future__ import annotations

from dataclasses import dataclass, field


def _clamp_unit(value: float, *, name: str) -> float:
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"{name} must be finite")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in [0, 1]; health cannot recommend leverage above 1.0")
    return float(value)


@dataclass(frozen=True)
class MeanReversionThresholds:
    """Instantaneous mean-reversion health thresholds (research defaults)."""

    adf_alpha: float = 0.05
    adf_reject_fraction_degraded: float = 0.50
    adf_reject_fraction_paused: float = 0.20
    adf_latest_pvalue_degraded: float = 0.05
    adf_latest_pvalue_paused: float = 0.25
    cadf_alpha: float = 0.05
    cadf_reject_fraction_degraded: float = 0.50
    cadf_reject_fraction_paused: float = 0.20
    cadf_latest_pvalue_degraded: float = 0.05
    cadf_latest_pvalue_paused: float = 0.25
    half_life_rel_drift_degraded: float = 1.50
    half_life_rel_drift_paused: float = 3.00
    hedge_ratio_rel_drift_degraded: float = 0.25
    hedge_ratio_rel_drift_paused: float = 0.75
    residual_vol_ratio_degraded: float = 1.50
    residual_vol_ratio_paused: float = 3.00
    convergence_ratio_degraded: float = 0.50
    convergence_ratio_paused: float = 0.25
    friction_ratio_degraded: float = 1.50
    friction_ratio_paused: float = 3.00


@dataclass(frozen=True)
class TrendThresholds:
    """Instantaneous trend health thresholds (research defaults)."""

    horizon_agreement_degraded: float = 0.67
    horizon_agreement_paused: float = 0.34
    persistence_degraded: float = 0.40
    persistence_paused: float = 0.15
    whipsaw_degraded: float = 0.30
    whipsaw_paused: float = 0.60
    breadth_degraded: float = 0.40
    breadth_paused: float = 0.15
    friction_ratio_degraded: float = 1.50
    friction_ratio_paused: float = 3.00


@dataclass(frozen=True)
class HysteresisConfig:
    """Stop one noisy observation from flapping emitted health states.

    Hard pauses (structural break, fail-closed invalid/missing evidence) and
    hard retire (combined thesis-broken evidence) enter immediately.
    Soft degraded / paused metrics require consecutive confirmations.
    Recovery from paused/retire requires a cooldown, then consecutive healthy
    observations. Health never skips cooldown to jump straight back to healthy.
    """

    degraded_confirmations: int = 2
    paused_confirmations: int = 2
    retire_confirmations: int = 4
    recovery_confirmations: int = 3
    cooldown_observations: int = 2

    def __post_init__(self) -> None:
        for name in (
            "degraded_confirmations",
            "paused_confirmations",
            "retire_confirmations",
            "recovery_confirmations",
            "cooldown_observations",
        ):
            value = int(getattr(self, name))
            if value < 1:
                raise ValueError(f"{name} must be >= 1")
            object.__setattr__(self, name, value)
        if self.paused_confirmations < self.degraded_confirmations:
            raise ValueError("paused_confirmations must be >= degraded_confirmations")
        if self.retire_confirmations < self.paused_confirmations:
            raise ValueError("retire_confirmations must be >= paused_confirmations")


@dataclass(frozen=True)
class AdvisoryRiskConfig:
    """Bounded advisory multipliers. Subordinate to any RiskGovernor.

    These values are recommendations only. They cannot create an order or
    mutate positions. A governor may tighten them further; health cannot loosen
    a governor bound.
    """

    healthy_multiplier: float = 1.0
    degraded_multiplier: float = 0.5
    paused_multiplier: float = 0.0
    retire_multiplier: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "healthy_multiplier", _clamp_unit(self.healthy_multiplier, name="healthy_multiplier"))
        object.__setattr__(
            self, "degraded_multiplier", _clamp_unit(self.degraded_multiplier, name="degraded_multiplier")
        )
        object.__setattr__(self, "paused_multiplier", _clamp_unit(self.paused_multiplier, name="paused_multiplier"))
        object.__setattr__(self, "retire_multiplier", _clamp_unit(self.retire_multiplier, name="retire_multiplier"))
        if self.degraded_multiplier > self.healthy_multiplier:
            raise ValueError("degraded_multiplier cannot exceed healthy_multiplier")
        if self.paused_multiplier > self.degraded_multiplier:
            raise ValueError("paused_multiplier cannot exceed degraded_multiplier")
        if self.retire_multiplier > self.paused_multiplier:
            raise ValueError("retire_multiplier cannot exceed paused_multiplier")


@dataclass(frozen=True)
class HealthConfig:
    schema_version: str = "4.0.0"
    mean_reversion: MeanReversionThresholds = field(default_factory=MeanReversionThresholds)
    trend: TrendThresholds = field(default_factory=TrendThresholds)
    hysteresis: HysteresisConfig = field(default_factory=HysteresisConfig)
    advisory: AdvisoryRiskConfig = field(default_factory=AdvisoryRiskConfig)
    fail_closed_on_missing: bool = True
    require_cadf: bool = True
    require_convergence: bool = False
