"""Quality-flag codes shared by every Stage 1 diagnostic."""

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
    NEAR_SINGULAR = "near_singular"
    COLLINEAR_SERIES = "collinear_series"
    INSUFFICIENT_RANK = "insufficient_rank"
    INVALID_FRICTION = "invalid_friction"
    INVALID_EDGE = "invalid_edge"
    INVALID_INPUT = "invalid_input"
    LENGTH_MISMATCH = "length_mismatch"
    TIMESTAMP_MISMATCH = "timestamp_mismatch"
    UNSORTED_TIMESTAMPS = "unsorted_timestamps"
    MISSING_TIMESTAMPS = "missing_timestamps"
    INTERIOR_MISSING = "interior_missing"
    HALF_LIFE_UNDEFINED = "half_life_undefined"
    INSUFFICIENT_LAGS = "insufficient_lags"
    BREAK_DATE_ESTIMATED = "break_date_estimated"
    UNSTABLE_PARAMETERS = "unstable_parameters"
    NOT_COMPUTED = "not_computed"
    COMPUTATION_ERROR = "computation_error"
    POINT_IN_TIME_SLICE = "point_in_time_slice"
