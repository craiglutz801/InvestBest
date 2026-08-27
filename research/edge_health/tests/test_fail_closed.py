"""Invalid/missing evidence fails closed (pause, never assumed healthy)."""

from __future__ import annotations

from northstar_edge_health import HealthConfig, HealthMonitor, HealthState, ReasonCode
from northstar_edge_health.evidence import MeanReversionEvidence, TrendEvidence

from health_fixtures import MR_IDENTITY, TREND_IDENTITY, healthy_mr, healthy_trend, ts


def test_missing_mean_reversion_evidence_fails_closed():
    evidence = MeanReversionEvidence(as_of=ts(1))
    snap = HealthMonitor().evaluate(evidence, identity=MR_IDENTITY)
    assert snap.state is HealthState.PAUSED
    assert snap.fail_closed is True
    assert ReasonCode.MISSING_EVIDENCE in snap.reason_codes
    assert snap.recommended_risk_multiplier == 0.0


def test_non_finite_metrics_fail_closed():
    snap = HealthMonitor().evaluate(
        healthy_mr(ts(1), half_life=float("nan")),
        identity=MR_IDENTITY,
    )
    assert snap.state is HealthState.PAUSED
    assert snap.fail_closed is True
    assert ReasonCode.INVALID_EVIDENCE in snap.reason_codes


def test_unusable_flag_fails_closed():
    snap = HealthMonitor().evaluate(healthy_mr(ts(1), usable=False), identity=MR_IDENTITY)
    assert snap.state is HealthState.PAUSED
    assert ReasonCode.INVALID_EVIDENCE in snap.reason_codes


def test_missing_trend_evidence_fails_closed():
    evidence = TrendEvidence(as_of=ts(1))
    snap = HealthMonitor().evaluate(evidence, identity=TREND_IDENTITY)
    assert snap.state is HealthState.PAUSED
    assert snap.fail_closed is True
    assert ReasonCode.MISSING_EVIDENCE in snap.reason_codes


def test_negative_expected_friction_fails_closed():
    snap = HealthMonitor().evaluate(
        healthy_mr(ts(1), expected_friction=-0.01),
        identity=MR_IDENTITY,
    )
    assert snap.fail_closed is True
    assert ReasonCode.INVALID_EVIDENCE in snap.reason_codes


def test_fail_closed_can_be_disabled_for_partial_research_evidence():
    config = HealthConfig(fail_closed_on_missing=False, require_cadf=False)
    evidence = MeanReversionEvidence(
        as_of=ts(1),
        rolling_adf_pvalues=(0.01, 0.02),
        half_life=10.0,
        half_life_baseline=10.0,
        hedge_ratio=1.0,
        hedge_ratio_baseline=1.0,
        residual_volatility=0.02,
        residual_volatility_baseline=0.02,
        structural_break_detected=False,
        realized_friction=0.001,
        expected_friction=0.001,
    )
    snap = HealthMonitor(config).evaluate(evidence, identity=MR_IDENTITY)
    assert snap.state is HealthState.HEALTHY
    assert snap.fail_closed is False


def test_invalid_horizon_signs_fail_closed():
    snap = HealthMonitor().evaluate(
        healthy_trend(ts(1), horizon_signs=(1, 2, -1)),
        identity=TREND_IDENTITY,
    )
    assert snap.fail_closed is True
    assert ReasonCode.INVALID_EVIDENCE in snap.reason_codes
