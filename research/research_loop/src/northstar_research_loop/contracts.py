"""Normalized Stage 1–5 contracts consumed by the Stage 6 pipeline.

These shapes are adapters, not reimplementations. When a later Chan package
is importable, discovery wraps its native objects into these records. When
it is not, callers must supply the same records explicitly — missing evidence
fails closed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Mapping, Protocol, Sequence

HealthStateName = Literal["healthy", "degraded", "paused", "research_retire"]
GateName = Literal[
    "edge_contract",
    "proposal",
    "diagnostics",
    "eligibility",
    "after_friction",
    "robustness",
    "health",
    "sizing",
    "safety",
]


@dataclass(frozen=True)
class GateResult:
    gate: str
    passed: bool
    reason_codes: tuple[str, ...]
    source_package: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    advisory_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "source_package": self.source_package,
            "details": dict(self.details),
            "advisory_only": self.advisory_only,
        }


@dataclass(frozen=True)
class DiagnosticBundle:
    """Stage 1 evidence. Prefer wrapping northstar_diagnostics.DiagnosticResult."""

    usable: bool
    required_property_present: bool
    reason_codes: tuple[str, ...]
    diagnostic_ids: tuple[str, ...]
    efr: float | None
    efr_fragile: bool
    break_detected: bool
    statistics: Mapping[str, Any] = field(default_factory=dict)
    source_package: str | None = "northstar_diagnostics"

    def to_dict(self) -> dict[str, Any]:
        return {
            "usable": self.usable,
            "required_property_present": self.required_property_present,
            "reason_codes": list(self.reason_codes),
            "diagnostic_ids": list(self.diagnostic_ids),
            "efr": self.efr,
            "efr_fragile": self.efr_fragile,
            "break_detected": self.break_detected,
            "statistics": dict(self.statistics),
            "source_package": self.source_package,
        }


@dataclass(frozen=True)
class EligibilityDecision:
    """Stage 2 mean-reversion (or family) eligibility. Entry timing is not eligibility."""

    eligible: bool
    family: str
    reason_codes: tuple[str, ...]
    source_package: str | None = None
    evidence: Mapping[str, Any] = field(default_factory=dict)
    zscore_after_eligibility: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "family": self.family,
            "reason_codes": list(self.reason_codes),
            "source_package": self.source_package,
            "evidence": dict(self.evidence),
            "zscore_after_eligibility": self.zscore_after_eligibility,
        }


@dataclass(frozen=True)
class TrendCarryContext:
    """Stage 3 research context. Never a live portfolio instruction."""

    usable: bool
    reason_codes: tuple[str, ...]
    horizons: tuple[str, ...] = ()
    horizon_agreement: float | None = None
    chose_single_optimized_horizon: bool = False
    source_package: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "usable": self.usable,
            "reason_codes": list(self.reason_codes),
            "horizons": list(self.horizons),
            "horizon_agreement": self.horizon_agreement,
            "chose_single_optimized_horizon": self.chose_single_optimized_horizon,
            "source_package": self.source_package,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class HealthSnapshot:
    """Stage 4 persistable health snapshot. Advisory risk multiplier only."""

    state: HealthStateName
    reason_codes: tuple[str, ...]
    advisory_risk_multiplier: float
    break_detected: bool
    source_package: str | None = None
    family: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason_codes": list(self.reason_codes),
            "advisory_risk_multiplier": self.advisory_risk_multiplier,
            "break_detected": self.break_detected,
            "source_package": self.source_package,
            "family": self.family,
            "details": dict(self.details),
            "mutates_positions": False,
            "bypasses_risk_governor": False,
        }


@dataclass(frozen=True)
class RobustnessDecision:
    """Stage 5 anti-overfit / promotion research decision. Never live promotion."""

    passed: bool
    reason_codes: tuple[str, ...]
    trial_count: int
    plateau_stable: bool
    holdout_contaminated: bool
    cost_stress_failed: bool
    delay_stress_failed: bool
    concentration_flag: bool
    deflated_sharpe: float | None = None
    pbo: float | None = None
    source_package: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "trial_count": self.trial_count,
            "plateau_stable": self.plateau_stable,
            "holdout_contaminated": self.holdout_contaminated,
            "cost_stress_failed": self.cost_stress_failed,
            "delay_stress_failed": self.delay_stress_failed,
            "concentration_flag": self.concentration_flag,
            "deflated_sharpe": self.deflated_sharpe,
            "pbo": self.pbo,
            "source_package": self.source_package,
            "details": dict(self.details),
            "self_promotes_to_live": False,
        }


@dataclass(frozen=True)
class SizingRecommendation:
    """Uncertainty-shrunk fractional-Kelly *ceiling*, never a target."""

    fractional_kelly_ceiling: float
    applied_caps: Mapping[str, float]
    reason_codes: tuple[str, ...]
    subordinate_to_risk_governor: bool = True
    source_package: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fractional_kelly_ceiling": self.fractional_kelly_ceiling,
            "applied_caps": dict(self.applied_caps),
            "reason_codes": list(self.reason_codes),
            "subordinate_to_risk_governor": self.subordinate_to_risk_governor,
            "is_target": False,
            "full_kelly": False,
            "source_package": self.source_package,
        }


class DiagnosticsPort(Protocol):
    def evaluate(self, evidence: Mapping[str, Any]) -> DiagnosticBundle: ...


class EligibilityPort(Protocol):
    def evaluate(
        self, diagnostics: DiagnosticBundle, evidence: Mapping[str, Any]
    ) -> EligibilityDecision: ...


class TrendCarryPort(Protocol):
    def evaluate(self, evidence: Mapping[str, Any]) -> TrendCarryContext: ...


class HealthPort(Protocol):
    def evaluate(self, evidence: Mapping[str, Any]) -> HealthSnapshot: ...


class RobustnessPort(Protocol):
    def evaluate(self, evidence: Mapping[str, Any]) -> RobustnessDecision: ...


class SizingPort(Protocol):
    def evaluate(self, evidence: Mapping[str, Any]) -> SizingRecommendation: ...


def fail_closed_gate(
    gate: str,
    reason_codes: Sequence[str],
    *,
    source_package: str | None = None,
    details: Mapping[str, Any] | None = None,
    advisory_only: bool = False,
) -> GateResult:
    return GateResult(
        gate=gate,
        passed=False,
        reason_codes=tuple(reason_codes),
        source_package=source_package,
        details=dict(details or {}),
        advisory_only=advisory_only,
    )
