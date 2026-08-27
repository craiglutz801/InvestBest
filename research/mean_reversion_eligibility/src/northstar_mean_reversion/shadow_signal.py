"""Research/shadow entry timing AFTER statistical eligibility.

Residual z-score thresholds are applied only when formation gates have already
passed. An oversold or collapsing series that failed eligibility cannot become
an entry candidate here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from northstar_mean_reversion.engine import evaluate_candidate
from northstar_mean_reversion.reasons import EligibilityReasonCode
from northstar_mean_reversion.types import (
    PACKAGE_VERSION,
    SCHEMA_VERSION,
    EligibilityDecision,
    MeanReversionEligibilityConfig,
)
from northstar_mean_reversion.universe import EconomicCandidate

ShadowDirection = Literal["long_spread", "short_spread", "none"]


@dataclass(frozen=True)
class ShadowSignalResult:
    """Shadow observation only. Never a production buy/sell instruction."""

    schema_version: str
    package_version: str
    candidate_id: str
    evaluated_at: datetime
    eligibility: EligibilityDecision
    residual_zscore: float | None
    zscore_entry_abs: float
    entry_timing_eligible: bool
    direction: ShadowDirection
    reason_codes: tuple[EligibilityReasonCode, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "package_version": self.package_version,
            "candidate_id": self.candidate_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "eligibility": self.eligibility.to_dict(),
            "residual_zscore": self.residual_zscore,
            "zscore_entry_abs": self.zscore_entry_abs,
            "entry_timing_eligible": self.entry_timing_eligible,
            "direction": self.direction,
            "reason_codes": [code.value for code in self.reason_codes],
            "notes": list(self.notes),
            "is_trade": False,
            "is_production_signal": False,
            "is_shadow_research_observation": True,
        }


SHADOW_NOTES = (
    "Shadow entry timing is research-only and is not wired to hourlyMarketAgent.",
    "Z-score thresholds are applied only after formation/eligibility gates pass.",
    "This result must not place an order, mutate paper positions, or authorize live trading.",
)


def evaluate_shadow_entry(
    candidate: EconomicCandidate,
    *,
    config: MeanReversionEligibilityConfig | None = None,
    eligibility: EligibilityDecision | None = None,
    computed_at: datetime | None = None,
) -> ShadowSignalResult:
    config = config or MeanReversionEligibilityConfig()
    computed_at = computed_at or datetime.now(timezone.utc)
    decision = eligibility or evaluate_candidate(
        candidate, config=config, computed_at=computed_at
    )
    zscore = None
    if decision.residual_summary is not None:
        raw = decision.residual_summary.get("last_zscore")
        if isinstance(raw, (int, float)):
            zscore = float(raw)

    threshold = float(config.zscore_entry_abs)
    codes: list[EligibilityReasonCode] = []
    direction: ShadowDirection = "none"
    entry = False

    if not decision.eligible:
        codes.append(EligibilityReasonCode.ENTRY_BLOCKED_NOT_ELIGIBLE)
        codes.extend(
            code
            for code in decision.reason_codes
            if code is not EligibilityReasonCode.ELIGIBLE
        )
    elif zscore is None:
        codes.append(EligibilityReasonCode.MISSING_OR_INVALID_DATA)
    elif abs(zscore) < threshold:
        codes.append(EligibilityReasonCode.ENTRY_THRESHOLD_NOT_MET)
    else:
        entry = True
        direction = "short_spread" if zscore > 0 else "long_spread"
        codes.append(EligibilityReasonCode.SHADOW_ENTRY_OBSERVED)

    return ShadowSignalResult(
        schema_version=SCHEMA_VERSION,
        package_version=PACKAGE_VERSION,
        candidate_id=candidate.candidate_id,
        evaluated_at=computed_at,
        eligibility=decision,
        residual_zscore=zscore,
        zscore_entry_abs=threshold,
        entry_timing_eligible=entry,
        direction=direction,
        reason_codes=tuple(codes),
        notes=SHADOW_NOTES,
    )
