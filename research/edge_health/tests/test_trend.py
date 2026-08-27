"""Unit tests for each trend state transition and reason code."""

from __future__ import annotations

import pytest

from northstar_edge_health import HealthMonitor, HealthState, ReasonCode

from health_fixtures import TREND_IDENTITY, healthy_trend, instant_config, ts


def _instant(evidence):
    return HealthMonitor(instant_config()).evaluate(evidence, identity=TREND_IDENTITY)


def test_healthy_trend():
    snap = _instant(healthy_trend(ts(1)))
    assert snap.state is HealthState.HEALTHY
    assert snap.recommended_risk_multiplier == 1.0
    assert snap.identity.strategy_family == "trend"


@pytest.mark.parametrize(
    "overrides,code,state",
    [
        ({"horizon_signs": (1, 1, -1, 0)}, ReasonCode.TREND_HORIZON_DISAGREEMENT, HealthState.DEGRADED),
        ({"horizon_signs": (1, -1, 0, 0)}, ReasonCode.TREND_HORIZON_DISAGREEMENT_SEVERE, HealthState.PAUSED),
        ({"persistence": 0.30}, ReasonCode.TREND_PERSISTENCE_COLLAPSE, HealthState.DEGRADED),
        ({"persistence": 0.05}, ReasonCode.TREND_PERSISTENCE_EXTREME, HealthState.PAUSED),
        ({"whipsaw_rate": 0.40}, ReasonCode.TREND_WHIPSAW_ELEVATED, HealthState.DEGRADED),
        ({"whipsaw_rate": 0.80}, ReasonCode.TREND_WHIPSAW_EXTREME, HealthState.PAUSED),
        ({"volatility_shock": True}, ReasonCode.TREND_VOLATILITY_SHOCK, HealthState.PAUSED),
        ({"realized_implementation_cost": 0.0013}, ReasonCode.TREND_FRICTION_OVERRUN, HealthState.DEGRADED),
        ({"realized_implementation_cost": 0.0030}, ReasonCode.TREND_FRICTION_EXTREME, HealthState.PAUSED),
        ({"cross_market_breadth": 0.25}, ReasonCode.TREND_BREADTH_COLLAPSE, HealthState.DEGRADED),
        ({"cross_market_breadth": 0.05}, ReasonCode.TREND_BREADTH_EXTREME, HealthState.PAUSED),
    ],
)
def test_trend_reason_codes_and_states(overrides, code, state):
    snap = _instant(healthy_trend(ts(1), **overrides))
    assert code in snap.reason_codes
    assert snap.state is state


def test_trend_thesis_broken_retire():
    snap = _instant(
        healthy_trend(
            ts(1),
            volatility_shock=True,
            whipsaw_rate=0.85,
            cross_market_breadth=0.05,
        )
    )
    assert snap.state is HealthState.RESEARCH_RETIRE_CANDIDATE
    assert ReasonCode.TREND_THESIS_BROKEN in snap.reason_codes
    assert ReasonCode.TREND_VOLATILITY_SHOCK in snap.reason_codes
    assert snap.recommended_risk_multiplier == 0.0
