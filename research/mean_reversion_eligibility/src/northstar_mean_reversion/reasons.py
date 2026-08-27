"""Typed Stage 2 eligibility and shadow-signal reason codes.

Every rejection must carry at least one of these codes so a caller can
explain why a candidate was not eligible. Codes are evidence labels, not
orders or permissions to trade.
"""

from __future__ import annotations

from enum import Enum


class EligibilityReasonCode(str, Enum):
    ELIGIBLE = "eligible"

    # Universe / formation identity
    MISSING_ECONOMIC_RELATIONSHIP = "missing_economic_relationship"
    INVALID_CANDIDATE_UNIVERSE = "invalid_candidate_universe"
    INSUFFICIENT_LEGS = "insufficient_legs"

    # Data quality / point-in-time
    MISSING_OR_INVALID_DATA = "missing_or_invalid_data"
    SHORT_SAMPLE = "short_sample"
    POINT_IN_TIME_VIOLATION = "point_in_time_violation"
    MISALIGNED_INPUTS = "misaligned_inputs"

    # Statistical formation
    CADF_NOT_COINTEGRATED = "cadf_not_cointegrated"
    JOHANSEN_RANK_ZERO = "johansen_rank_zero"
    SPREAD_NOT_STATIONARY = "spread_not_stationary"
    BROKEN_COINTEGRATION = "broken_cointegration"
    HEDGE_RATIO_NOT_ESTIMATED = "hedge_ratio_not_estimated"
    UNSTABLE_HEDGE_RATIO = "unstable_hedge_ratio"
    UNSTABLE_SPREAD_VOLATILITY = "unstable_spread_volatility"
    HALF_LIFE_UNDEFINED = "half_life_undefined"
    HALF_LIFE_MISMATCH = "half_life_mismatch"
    STRUCTURAL_BREAK_VETO = "structural_break_veto"

    # Cost / implementation
    MISSING_EFR_INPUTS = "missing_efr_inputs"
    INSUFFICIENT_EFR = "insufficient_efr"
    INVALID_FRICTION = "invalid_friction"

    # Liquidity / shortability (caller-supplied snapshots; no live broker)
    MISSING_LIQUIDITY_SNAPSHOT = "missing_liquidity_snapshot"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"
    NOT_SHORTABLE = "not_shortable"

    # Caller-supplied event / fundamental flags
    EVENT_DIVERGENCE_VETO = "event_divergence_veto"
    FUNDAMENTAL_DIVERGENCE_VETO = "fundamental_divergence_veto"

    # Entry timing (shadow only; never runs as a substitute for eligibility)
    ENTRY_BLOCKED_NOT_ELIGIBLE = "entry_blocked_not_eligible"
    ENTRY_THRESHOLD_NOT_MET = "entry_threshold_not_met"
    SHADOW_ENTRY_OBSERVED = "shadow_entry_observed"


INSUFFICIENT_DATA_CODES = frozenset(
    {
        EligibilityReasonCode.MISSING_ECONOMIC_RELATIONSHIP,
        EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
        EligibilityReasonCode.INSUFFICIENT_LEGS,
        EligibilityReasonCode.MISSING_OR_INVALID_DATA,
        EligibilityReasonCode.SHORT_SAMPLE,
        EligibilityReasonCode.POINT_IN_TIME_VIOLATION,
        EligibilityReasonCode.MISALIGNED_INPUTS,
        EligibilityReasonCode.MISSING_EFR_INPUTS,
        EligibilityReasonCode.INVALID_FRICTION,
        EligibilityReasonCode.MISSING_LIQUIDITY_SNAPSHOT,
        EligibilityReasonCode.HEDGE_RATIO_NOT_ESTIMATED,
    }
)
