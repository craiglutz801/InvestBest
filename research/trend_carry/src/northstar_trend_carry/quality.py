"""Quality-flag codes for Stage 3 trend / carry research results."""

from __future__ import annotations

from enum import Enum


class QualityLevel(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


class QualityCode:
    SHORT_SAMPLE = "short_sample"
    MISSING_DATA = "missing_data"
    NON_FINITE = "non_finite"
    DEGENERATE_VARIANCE = "degenerate_variance"
    CONSTANT_SERIES = "constant_series"
    INVALID_INPUT = "invalid_input"
    UNSORTED_TIMESTAMPS = "unsorted_timestamps"
    NON_POSITIVE_PRICE = "non_positive_price"
    POINT_IN_TIME_SLICE = "point_in_time_slice"
    HORIZON_UNAVAILABLE = "horizon_unavailable"
    MIXED_HORIZON_SIGNS = "mixed_horizon_signs"
    VOLATILITY_SHOCK = "volatility_shock"
    HIGH_WHIPSAW = "high_whipsaw"
    MISSING_CONTRACT = "missing_contract"
    EXPIRED_CONTRACT = "expired_contract"
    INSUFFICIENT_CHAIN = "insufficient_chain"
    LOOKAHEAD_BLOCKED = "lookahead_blocked"
    INVALID_FRICTION = "invalid_friction"
    INVALID_EDGE = "invalid_edge"
    NOT_COMPUTED = "not_computed"
    RESEARCH_ONLY = "research_only"
    SHORT_EXPRESSION_BLOCKED = "short_expression_blocked"


def flag(code: str, level: QualityLevel, message: str) -> "QualityFlag":
    from northstar_trend_carry.schema import QualityFlag

    return QualityFlag(code=code, level=level, message=message)
