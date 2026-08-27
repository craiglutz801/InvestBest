"""Quality flags and fail-closed reason codes for Stage 5 evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class QualityLevel(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class QualityCode:
    OK = "ok"
    SHORT_SAMPLE = "short_sample"
    MISSING_DATA = "missing_data"
    NON_FINITE = "non_finite"
    DEGENERATE_VARIANCE = "degenerate_variance"
    CONSTANT_SERIES = "constant_series"
    INVALID_INPUT = "invalid_input"
    INSUFFICIENT_TRIALS = "insufficient_trials"
    INSUFFICIENT_STRATEGIES = "insufficient_strategies"
    INSUFFICIENT_SLICES = "insufficient_slices"
    INSUFFICIENT_NEIGHBORS = "insufficient_neighbors"
    NOT_COMPUTED = "not_computed"
    COMPUTATION_ERROR = "computation_error"
    HOLDOUT_CONTAMINATION = "holdout_contamination"
    HOLDOUT_NOT_SEALED = "holdout_not_sealed"
    HOLDOUT_OVERLAP = "holdout_overlap"
    HOLDOUT_SCORE_BELOW_THRESHOLD = "holdout_score_below_threshold"
    POINT_IN_TIME_VIOLATION = "point_in_time_violation"
    FULL_KELLY_REJECTED = "full_kelly_rejected"
    NON_POSITIVE_EDGE = "non_positive_edge"
    RISK_GOVERNOR_CAP_NOT_SUPPLIED = "risk_governor_cap_not_supplied"
    MISSING_REQUIRED_EVIDENCE = "missing_required_evidence"


class ReasonCode(str, Enum):
    """Fail-closed promotion reason codes.

    A candidate is rejected unless every required gate passes. Passing all
    gates yields ``eligible_for_human_review``, never self-promotion.
    """

    INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_REQUIRED_EVIDENCE = "MISSING_REQUIRED_EVIDENCE"
    HOLDOUT_CONTAMINATION = "HOLDOUT_CONTAMINATION"
    HOLDOUT_NOT_SEALED = "HOLDOUT_NOT_SEALED"
    HOLDOUT_FAIL = "HOLDOUT_FAIL"
    ISOLATED_OPTIMUM = "ISOLATED_OPTIMUM"
    PLATEAU_FAIL = "PLATEAU_FAIL"
    COST_STRESS_FAIL = "COST_STRESS_FAIL"
    DELAY_STRESS_FAIL = "DELAY_STRESS_FAIL"
    CONCENTRATION_FAIL = "CONCENTRATION_FAIL"
    DSR_BELOW_THRESHOLD = "DSR_BELOW_THRESHOLD"
    PBO_ABOVE_THRESHOLD = "PBO_ABOVE_THRESHOLD"
    WALK_FORWARD_FAIL = "WALK_FORWARD_FAIL"
    REGIME_SLICE_FAIL = "REGIME_SLICE_FAIL"
    KELLY_INVALID = "KELLY_INVALID"
    MULTIPLE_TESTING_FAIL = "MULTIPLE_TESTING_FAIL"
    TRIAL_COUNT_EXCESSIVE = "TRIAL_COUNT_EXCESSIVE"
    SHADOW_FORWARD_REQUIRED = "SHADOW_FORWARD_REQUIRED"
    COMPUTATION_ERROR = "COMPUTATION_ERROR"


@dataclass(frozen=True)
class QualityFlag:
    code: str
    level: QualityLevel
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "level": self.level.value, "message": self.message}


def ok_flag(message: str = "Inputs were usable and the statistic was computed.") -> QualityFlag:
    return QualityFlag(code=QualityCode.OK, level=QualityLevel.OK, message=message)


def fail_flag(code: str, message: str) -> QualityFlag:
    return QualityFlag(code=code, level=QualityLevel.FAIL, message=message)


def warn_flag(code: str, message: str) -> QualityFlag:
    return QualityFlag(code=code, level=QualityLevel.WARN, message=message)
