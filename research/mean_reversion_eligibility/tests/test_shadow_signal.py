"""Shadow z-score timing is blocked unless formation eligibility already passed."""

from __future__ import annotations

import numpy as np

from northstar_mean_reversion.reasons import EligibilityReasonCode
from northstar_mean_reversion.shadow_signal import evaluate_shadow_entry

from fixtures import (
    cointegrated_pair,
    oversold_nonstationary_pair,
    pair_candidate,
    make_config,
)


N = 240


def test_oversold_nonstationary_series_is_rejected_and_cannot_enter():
    y, x = oversold_nonstationary_pair(N, seed=31)
    candidate = pair_candidate(y, x)
    result = evaluate_shadow_entry(candidate, config=make_config())
    assert result.eligibility.eligible is False
    assert result.entry_timing_eligible is False
    assert EligibilityReasonCode.ENTRY_BLOCKED_NOT_ELIGIBLE in result.reason_codes
    # Residual may look "oversold"; that is not enough.
    if result.residual_zscore is not None:
        assert result.residual_zscore < 0


def test_entry_cannot_become_eligible_if_formation_fails():
    y, x = oversold_nonstationary_pair(N, seed=32)
    # Make the last residual even more extreme so a naive z-score rule would fire.
    y = y.copy()
    y[-1] -= 25.0
    result = evaluate_shadow_entry(pair_candidate(y, x), config=make_config(zscore_entry_abs=1.0))
    assert result.eligibility.eligible is False
    assert result.entry_timing_eligible is False
    assert result.direction == "none"


def test_eligible_pair_below_z_threshold_does_not_shadow_enter():
    y, x = cointegrated_pair(N, seed=33, residual_scale=0.2)
    result = evaluate_shadow_entry(
        pair_candidate(y, x),
        config=make_config(zscore_entry_abs=8.0),
    )
    assert result.eligibility.eligible is True
    assert result.entry_timing_eligible is False
    assert EligibilityReasonCode.ENTRY_THRESHOLD_NOT_MET in result.reason_codes


def test_eligible_pair_with_extreme_residual_can_shadow_enter():
    y, x = cointegrated_pair(N, seed=34, residual_scale=0.25)
    y = np.asarray(y, dtype=float).copy()
    y[-1] += 6.0
    result = evaluate_shadow_entry(
        pair_candidate(y, x),
        config=make_config(zscore_entry_abs=2.0),
    )
    assert result.eligibility.eligible is True
    assert result.entry_timing_eligible is True
    assert result.direction == "short_spread"
    assert EligibilityReasonCode.SHADOW_ENTRY_OBSERVED in result.reason_codes
    assert result.to_dict()["is_production_signal"] is False
    assert result.to_dict()["is_shadow_research_observation"] is True
