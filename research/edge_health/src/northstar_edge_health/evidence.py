"""Point-in-time health evidence for strategy families.

These dataclasses are independently testable. They do not require Stage 1
diagnostics at runtime; the Stage 1 adapter fills them from DiagnosticResult
objects when stacking is available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from math import log
from typing import Mapping, Sequence

from northstar_edge_health.states import ReasonCode


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and value == value and value not in (float("inf"), float("-inf"))


def relative_drift(current: float, baseline: float) -> float | None:
    """Symmetric relative change: max(c/b, b/c) for same-sign finite values."""

    if not is_finite_number(current) or not is_finite_number(baseline):
        return None
    if current == 0.0 or baseline == 0.0:
        if current == baseline:
            return 1.0
        return None
    if (current > 0.0) != (baseline > 0.0):
        return None
    ratio = abs(float(current) / float(baseline))
    if ratio == 0.0:
        return None
    return max(ratio, 1.0 / ratio)


def expansion_ratio(current: float, baseline: float) -> float | None:
    if not is_finite_number(current) or not is_finite_number(baseline):
        return None
    if float(baseline) == 0.0:
        return None
    return float(current) / float(baseline)


def reject_fraction(pvalues: Sequence[float | None] | None, *, alpha: float) -> float | None:
    if pvalues is None:
        return None
    finite = [float(p) for p in pvalues if is_finite_number(p)]
    if not finite:
        return None
    return sum(1.0 for p in finite if p < alpha) / float(len(finite))


def latest_finite(pvalues: Sequence[float | None] | None) -> float | None:
    if pvalues is None:
        return None
    for value in reversed(tuple(pvalues)):
        if is_finite_number(value):
            return float(value)
    return None


def horizon_sign_agreement(signs: Sequence[int]) -> float | None:
    if not signs:
        return None
    nonzero = [int(s) for s in signs if int(s) != 0]
    if not nonzero:
        return 0.0
    majority = 1 if sum(1 for s in nonzero if s > 0) >= sum(1 for s in nonzero if s < 0) else -1
    return sum(1.0 for s in signs if int(s) == majority) / float(len(signs))


def implied_convergence(half_life: float | None) -> float | None:
    if not is_finite_number(half_life) or float(half_life) <= 0.0:
        return None
    return log(2.0) / float(half_life)


@dataclass(frozen=True)
class MeanReversionEvidence:
    """Mean-reversion live-health inputs (point-in-time as of ``as_of``)."""

    as_of: datetime
    rolling_adf_pvalues: tuple[float | None, ...] | None = None
    rolling_adf_reject_fraction: float | None = None
    rolling_cadf_pvalues: tuple[float | None, ...] | None = None
    rolling_cadf_reject_fraction: float | None = None
    half_life: float | None = None
    half_life_baseline: float | None = None
    hedge_ratio: float | None = None
    hedge_ratio_baseline: float | None = None
    residual_volatility: float | None = None
    residual_volatility_baseline: float | None = None
    convergence_rate: float | None = None
    convergence_rate_baseline: float | None = None
    structural_break_detected: bool | None = None
    realized_friction: float | None = None
    expected_friction: float | None = None
    usable: bool = True
    source: str = "direct"
    notes: tuple[str, ...] = ()
    extra: Mapping[str, object] = field(default_factory=dict)

    def missing_fields(self, *, require_cadf: bool, require_convergence: bool) -> tuple[str, ...]:
        missing: list[str] = []
        if self.as_of is None:
            missing.append("as_of")
        adf_ok = (
            (self.rolling_adf_pvalues is not None and len(self.rolling_adf_pvalues) > 0)
            or self.rolling_adf_reject_fraction is not None
        )
        if not adf_ok:
            missing.append("rolling_adf")
        cadf_ok = (
            (self.rolling_cadf_pvalues is not None and len(self.rolling_cadf_pvalues) > 0)
            or self.rolling_cadf_reject_fraction is not None
        )
        if require_cadf and not cadf_ok:
            missing.append("rolling_cadf")
        if self.half_life is None and self.half_life_baseline is None:
            missing.append("half_life")
        if self.hedge_ratio is None:
            missing.append("hedge_ratio")
        if self.hedge_ratio_baseline is None:
            missing.append("hedge_ratio_baseline")
        if self.residual_volatility is None:
            missing.append("residual_volatility")
        if self.residual_volatility_baseline is None:
            missing.append("residual_volatility_baseline")
        if self.structural_break_detected is None:
            missing.append("structural_break_detected")
        if self.realized_friction is None:
            missing.append("realized_friction")
        if self.expected_friction is None:
            missing.append("expected_friction")
        if require_convergence and self.effective_convergence() is None and self.convergence_rate_baseline is None:
            missing.append("convergence_rate")
        return tuple(missing)

    def invalid_fields(self) -> tuple[str, ...]:
        invalid: list[str] = []
        numeric = {
            "rolling_adf_reject_fraction": self.rolling_adf_reject_fraction,
            "rolling_cadf_reject_fraction": self.rolling_cadf_reject_fraction,
            "half_life": self.half_life,
            "half_life_baseline": self.half_life_baseline,
            "hedge_ratio": self.hedge_ratio,
            "hedge_ratio_baseline": self.hedge_ratio_baseline,
            "residual_volatility": self.residual_volatility,
            "residual_volatility_baseline": self.residual_volatility_baseline,
            "convergence_rate": self.convergence_rate,
            "convergence_rate_baseline": self.convergence_rate_baseline,
            "realized_friction": self.realized_friction,
            "expected_friction": self.expected_friction,
        }
        for name, value in numeric.items():
            if value is not None and not is_finite_number(value):
                invalid.append(name)
        for name, series in (
            ("rolling_adf_pvalues", self.rolling_adf_pvalues),
            ("rolling_cadf_pvalues", self.rolling_cadf_pvalues),
        ):
            if series is None:
                continue
            for item in series:
                if item is not None and not is_finite_number(item):
                    invalid.append(name)
                    break
        if self.realized_friction is not None and is_finite_number(self.realized_friction) and self.realized_friction < 0:
            invalid.append("realized_friction")
        if self.expected_friction is not None and is_finite_number(self.expected_friction) and self.expected_friction <= 0:
            invalid.append("expected_friction")
        return tuple(dict.fromkeys(invalid))

    def effective_convergence(self) -> float | None:
        if is_finite_number(self.convergence_rate):
            return float(self.convergence_rate)
        return implied_convergence(self.half_life)

    def effective_convergence_baseline(self) -> float | None:
        if is_finite_number(self.convergence_rate_baseline):
            return float(self.convergence_rate_baseline)
        return implied_convergence(self.half_life_baseline)

    def to_digest(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
            "rolling_adf_pvalues": list(self.rolling_adf_pvalues) if self.rolling_adf_pvalues is not None else None,
            "rolling_adf_reject_fraction": self.rolling_adf_reject_fraction,
            "rolling_cadf_pvalues": list(self.rolling_cadf_pvalues) if self.rolling_cadf_pvalues is not None else None,
            "rolling_cadf_reject_fraction": self.rolling_cadf_reject_fraction,
            "half_life": self.half_life,
            "half_life_baseline": self.half_life_baseline,
            "hedge_ratio": self.hedge_ratio,
            "hedge_ratio_baseline": self.hedge_ratio_baseline,
            "residual_volatility": self.residual_volatility,
            "residual_volatility_baseline": self.residual_volatility_baseline,
            "convergence_rate": self.effective_convergence(),
            "convergence_rate_baseline": self.effective_convergence_baseline(),
            "structural_break_detected": self.structural_break_detected,
            "realized_friction": self.realized_friction,
            "expected_friction": self.expected_friction,
            "usable": self.usable,
            "source": self.source,
        }


@dataclass(frozen=True)
class TrendEvidence:
    """Trend live-health inputs (point-in-time as of ``as_of``)."""

    as_of: datetime
    horizon_signs: tuple[int, ...] | None = None
    persistence: float | None = None
    whipsaw_rate: float | None = None
    volatility_shock: bool | None = None
    realized_implementation_cost: float | None = None
    expected_implementation_cost: float | None = None
    cross_market_breadth: float | None = None
    usable: bool = True
    source: str = "direct"
    notes: tuple[str, ...] = ()
    extra: Mapping[str, object] = field(default_factory=dict)

    def missing_fields(self) -> tuple[str, ...]:
        missing: list[str] = []
        if self.as_of is None:
            missing.append("as_of")
        if self.horizon_signs is None or len(self.horizon_signs) == 0:
            missing.append("horizon_signs")
        if self.persistence is None:
            missing.append("persistence")
        if self.whipsaw_rate is None:
            missing.append("whipsaw_rate")
        if self.volatility_shock is None:
            missing.append("volatility_shock")
        if self.realized_implementation_cost is None:
            missing.append("realized_implementation_cost")
        if self.expected_implementation_cost is None:
            missing.append("expected_implementation_cost")
        if self.cross_market_breadth is None:
            missing.append("cross_market_breadth")
        return tuple(missing)

    def invalid_fields(self) -> tuple[str, ...]:
        invalid: list[str] = []
        if self.horizon_signs is not None:
            for sign in self.horizon_signs:
                if int(sign) not in (-1, 0, 1):
                    invalid.append("horizon_signs")
                    break
        numeric = {
            "persistence": self.persistence,
            "whipsaw_rate": self.whipsaw_rate,
            "realized_implementation_cost": self.realized_implementation_cost,
            "expected_implementation_cost": self.expected_implementation_cost,
            "cross_market_breadth": self.cross_market_breadth,
        }
        for name, value in numeric.items():
            if value is not None and not is_finite_number(value):
                invalid.append(name)
        for name in ("persistence", "whipsaw_rate", "cross_market_breadth"):
            value = getattr(self, name)
            if is_finite_number(value) and not 0.0 <= float(value) <= 1.0:
                invalid.append(name)
        if (
            self.realized_implementation_cost is not None
            and is_finite_number(self.realized_implementation_cost)
            and self.realized_implementation_cost < 0
        ):
            invalid.append("realized_implementation_cost")
        if (
            self.expected_implementation_cost is not None
            and is_finite_number(self.expected_implementation_cost)
            and self.expected_implementation_cost <= 0
        ):
            invalid.append("expected_implementation_cost")
        return tuple(dict.fromkeys(invalid))

    def to_digest(self) -> dict[str, object]:
        return {
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
            "horizon_signs": list(self.horizon_signs) if self.horizon_signs is not None else None,
            "horizon_sign_agreement": horizon_sign_agreement(self.horizon_signs or ()),
            "persistence": self.persistence,
            "whipsaw_rate": self.whipsaw_rate,
            "volatility_shock": self.volatility_shock,
            "realized_implementation_cost": self.realized_implementation_cost,
            "expected_implementation_cost": self.expected_implementation_cost,
            "cross_market_breadth": self.cross_market_breadth,
            "usable": self.usable,
            "source": self.source,
        }


Evidence = MeanReversionEvidence | TrendEvidence

FAIL_CLOSED_REASON_CODES = frozenset(
    {
        ReasonCode.MISSING_EVIDENCE,
        ReasonCode.INVALID_EVIDENCE,
        ReasonCode.FUTURE_OBSERVATION,
        ReasonCode.NON_MONOTONIC_HISTORY,
    }
)
