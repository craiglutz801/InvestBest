"""Typed Stage 2 eligibility decision, config, and gate evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Mapping, Sequence

from northstar_diagnostics.schema import DiagnosticResult

from northstar_mean_reversion.reasons import (
    INSUFFICIENT_DATA_CODES,
    EligibilityReasonCode,
)

SCHEMA_VERSION = "1.0.0"
PACKAGE_VERSION = "0.1.0"


@dataclass(frozen=True)
class MeanReversionEligibilityConfig:
    """Research defaults. Thresholds never place an order by themselves."""

    min_obs: int = 60
    cadf_pvalue_max: float = 0.05
    adf_pvalue_max: float = 0.05
    johansen_min_rank: int = 1
    half_life_max_multiple_of_horizon: float = 2.0
    half_life_min_fraction_of_horizon: float = 0.05
    hedge_beta_relative_std_max: float = 0.5
    spread_vol_cv_max: float = 0.85
    rolling_window: int = 60
    rolling_step: int = 10
    efr_min: float = 2.5
    require_efr: bool = True
    structural_break_method: str = "cusum_ols_resid"
    structural_break_significance: float = 0.01
    require_liquidity_snapshot: bool = False
    min_adv: float | None = None
    max_spread_bps: float | None = None
    require_shortable: bool = False
    zscore_entry_abs: float = 2.0
    frequency: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_obs": self.min_obs,
            "cadf_pvalue_max": self.cadf_pvalue_max,
            "adf_pvalue_max": self.adf_pvalue_max,
            "johansen_min_rank": self.johansen_min_rank,
            "half_life_max_multiple_of_horizon": self.half_life_max_multiple_of_horizon,
            "half_life_min_fraction_of_horizon": self.half_life_min_fraction_of_horizon,
            "hedge_beta_relative_std_max": self.hedge_beta_relative_std_max,
            "spread_vol_cv_max": self.spread_vol_cv_max,
            "rolling_window": self.rolling_window,
            "rolling_step": self.rolling_step,
            "efr_min": self.efr_min,
            "require_efr": self.require_efr,
            "structural_break_method": self.structural_break_method,
            "structural_break_significance": self.structural_break_significance,
            "require_liquidity_snapshot": self.require_liquidity_snapshot,
            "min_adv": self.min_adv,
            "max_spread_bps": self.max_spread_bps,
            "require_shortable": self.require_shortable,
            "zscore_entry_abs": self.zscore_entry_abs,
            "frequency": self.frequency,
        }


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    passed: bool
    reason_code: EligibilityReasonCode
    message: str
    evidence: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_id": self.gate_id,
            "passed": self.passed,
            "reason_code": self.reason_code.value,
            "message": self.message,
            "evidence": dict(self.evidence),
        }


EligibilityStatus = Literal["eligible", "ineligible", "insufficient_data"]


@dataclass(frozen=True)
class EligibilityDecision:
    """Formation/eligibility verdict. Not an order and not an entry signal."""

    schema_version: str
    package_version: str
    candidate_id: str
    candidate_kind: str
    symbols: tuple[str, ...]
    evaluated_at: datetime
    as_of: datetime | None
    status: EligibilityStatus
    eligible: bool
    reason_codes: tuple[EligibilityReasonCode, ...]
    gates: tuple[GateResult, ...]
    diagnostics: Mapping[str, DiagnosticResult]
    hedge_ratio: Mapping[str, float] | None
    residual_summary: Mapping[str, float | None] | None
    holding_horizon: float | None
    config: Mapping[str, Any]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_version": self.package_version,
            "candidate_id": self.candidate_id,
            "candidate_kind": self.candidate_kind,
            "symbols": list(self.symbols),
            "evaluated_at": _iso(self.evaluated_at),
            "as_of": _iso(self.as_of),
            "status": self.status,
            "eligible": self.eligible,
            "reason_codes": [code.value for code in self.reason_codes],
            "gates": [gate.to_dict() for gate in self.gates],
            "diagnostics": {key: value.to_dict() for key, value in self.diagnostics.items()},
            "hedge_ratio": dict(self.hedge_ratio) if self.hedge_ratio is not None else None,
            "residual_summary": dict(self.residual_summary) if self.residual_summary else None,
            "holding_horizon": self.holding_horizon,
            "config": dict(self.config),
            "notes": list(self.notes),
            "is_trade": False,
            "is_production_signal": False,
        }


def decision_status(reason_codes: Sequence[EligibilityReasonCode]) -> EligibilityStatus:
    failures = [code for code in reason_codes if code is not EligibilityReasonCode.ELIGIBLE]
    if not failures:
        return "eligible"
    if any(code in INSUFFICIENT_DATA_CODES for code in failures):
        return "insufficient_data"
    return "ineligible"


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
