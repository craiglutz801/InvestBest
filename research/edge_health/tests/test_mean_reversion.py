"""Unit tests for each mean-reversion state transition and reason code."""

from __future__ import annotations

import pytest

from northstar_edge_health import HealthMonitor, HealthState, ReasonCode

from health_fixtures import MR_IDENTITY, healthy_mr, instant_config, ts


def _instant(evidence, config=None):
    return HealthMonitor(config or instant_config()).evaluate(evidence, identity=MR_IDENTITY)


def test_healthy_mean_reversion_has_full_multiplier():
    snap = _instant(healthy_mr(ts(1)))
    assert snap.state is HealthState.HEALTHY
    assert snap.instantaneous_state is HealthState.HEALTHY
    assert snap.recommended_risk_multiplier == 1.0
    assert snap.may_create_order is False
    assert snap.subordinate_to_risk_governor is True
    assert snap.fail_closed is False


@pytest.mark.parametrize(
    "overrides,code,state",
    [
        ({"rolling_adf_reject_fraction": 0.40, "rolling_adf_pvalues": (0.08, 0.09)}, ReasonCode.MR_ROLLING_ADF_NONSTATIONARY, HealthState.DEGRADED),
        ({"rolling_adf_reject_fraction": 0.10, "rolling_adf_pvalues": (0.40, 0.50)}, ReasonCode.MR_ROLLING_ADF_NONSTATIONARY_SEVERE, HealthState.PAUSED),
        ({"rolling_cadf_reject_fraction": 0.40, "rolling_cadf_pvalues": (0.08, 0.10)}, ReasonCode.MR_ROLLING_CADF_NONSTATIONARY, HealthState.DEGRADED),
        ({"rolling_cadf_reject_fraction": 0.05, "rolling_cadf_pvalues": (0.40, 0.45)}, ReasonCode.MR_ROLLING_CADF_NONSTATIONARY_SEVERE, HealthState.PAUSED),
        ({"half_life": 16.0}, ReasonCode.MR_HALF_LIFE_DRIFT, HealthState.DEGRADED),
        ({"half_life": 35.0}, ReasonCode.MR_HALF_LIFE_EXTREME_DRIFT, HealthState.PAUSED),
        ({"half_life": None}, ReasonCode.MR_HALF_LIFE_UNDEFINED, HealthState.PAUSED),
        ({"hedge_ratio": 1.30}, ReasonCode.MR_HEDGE_RATIO_DRIFT, HealthState.DEGRADED),
        ({"hedge_ratio": 1.90}, ReasonCode.MR_HEDGE_RATIO_EXTREME_DRIFT, HealthState.PAUSED),
        ({"residual_volatility": 0.035}, ReasonCode.MR_RESIDUAL_VOL_EXPANSION, HealthState.DEGRADED),
        ({"residual_volatility": 0.08}, ReasonCode.MR_RESIDUAL_VOL_EXTREME, HealthState.PAUSED),
        ({"convergence_rate": 0.030, "convergence_rate_baseline": 0.069}, ReasonCode.MR_CONVERGENCE_COLLAPSE, HealthState.DEGRADED),
        ({"convergence_rate": 0.010, "convergence_rate_baseline": 0.069}, ReasonCode.MR_CONVERGENCE_EXTREME, HealthState.PAUSED),
        ({"structural_break_detected": True}, ReasonCode.MR_STRUCTURAL_BREAK, HealthState.PAUSED),
        ({"realized_friction": 0.0016}, ReasonCode.MR_FRICTION_OVERRUN, HealthState.DEGRADED),
        ({"realized_friction": 0.0040}, ReasonCode.MR_FRICTION_EXTREME, HealthState.PAUSED),
    ],
)
def test_mean_reversion_reason_codes_and_states(overrides, code, state):
    snap = _instant(healthy_mr(ts(1), **overrides))
    assert code in snap.reason_codes
    assert snap.state is state
    assert snap.instantaneous_state is state


def test_structural_break_causes_pause_and_zero_multiplier():
    snap = _instant(healthy_mr(ts(1), structural_break_detected=True))
    assert snap.state is HealthState.PAUSED
    assert ReasonCode.MR_STRUCTURAL_BREAK in snap.reason_codes
    assert snap.recommended_risk_multiplier == 0.0
    assert snap.may_mutate_positions is False


def test_thesis_broken_is_research_retire_candidate():
    snap = _instant(
        healthy_mr(
            ts(1),
            structural_break_detected=True,
            half_life=None,
            residual_volatility=0.10,
        )
    )
    assert snap.state is HealthState.RESEARCH_RETIRE_CANDIDATE
    assert ReasonCode.MR_THESIS_BROKEN in snap.reason_codes
    assert ReasonCode.MR_STRUCTURAL_BREAK in snap.reason_codes
    assert ReasonCode.MR_HALF_LIFE_UNDEFINED in snap.reason_codes
    assert ReasonCode.MR_RESIDUAL_VOL_EXTREME in snap.reason_codes
    assert snap.recommended_risk_multiplier == 0.0


def test_degraded_multiplier_is_reduced_not_zero():
    snap = _instant(healthy_mr(ts(1), half_life=16.0))
    assert snap.state is HealthState.DEGRADED
    assert snap.recommended_risk_multiplier == 0.5
