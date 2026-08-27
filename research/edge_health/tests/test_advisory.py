"""Recommended risk multiplier is advisory and never mutates positions."""

from __future__ import annotations

from typing import Any, Mapping

from northstar_edge_health import (
    HealthMonitor,
    HealthState,
    apply_advisory,
)
from northstar_edge_health.advisory import AdvisoryRiskRecommendation

from health_fixtures import MR_IDENTITY, healthy_mr, instant_config, ts


class RecordingGovernor:
    def __init__(self, cap: float) -> None:
        self.cap = cap
        self.calls: list[float] = []

    def authorize_multiplier(self, requested_multiplier: float, *, context: Mapping[str, Any]) -> float:
        self.calls.append(requested_multiplier)
        assert context["may_create_order"] is False
        assert context["may_mutate_positions"] is False
        return min(requested_multiplier, self.cap)


class TighteningGovernor:
    def authorize_multiplier(self, requested_multiplier: float, *, context: Mapping[str, Any]) -> float:
        _ = requested_multiplier, context
        return 0.0


class LooseningGovernor:
    """A misbehaving governor that tries to raise the multiplier. Health must clamp it."""

    def authorize_multiplier(self, requested_multiplier: float, *, context: Mapping[str, Any]) -> float:
        _ = context
        return requested_multiplier + 1.0


def test_apply_advisory_does_not_mutate_positions():
    snap = HealthMonitor(instant_config()).evaluate(healthy_mr(ts(1), half_life=16.0), identity=MR_IDENTITY)
    assert snap.state is HealthState.DEGRADED
    positions = [{"id": "p1", "qty": 10.0}, {"id": "p2", "qty": -4.0}]
    original = [dict(item) for item in positions]
    rec = apply_advisory(snap, positions=positions, governor=RecordingGovernor(1.0))
    assert positions == original
    assert rec.positions_mutated is False
    assert rec.may_mutate_positions is False
    assert rec.may_create_order is False
    assert rec.bypasses_risk_governor is False
    assert rec.subordinate_to_risk_governor is True
    assert rec.health_recommended_multiplier == 0.5
    assert rec.authorized_multiplier == 0.5


def test_governor_can_tighten_but_health_cannot_loosen():
    monitor = HealthMonitor()
    snap = monitor.evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY)
    assert snap.recommended_risk_multiplier == 1.0
    tight = apply_advisory(snap, positions=[{"qty": 1}], governor=TighteningGovernor())
    assert tight.health_recommended_multiplier == 1.0
    assert tight.authorized_multiplier == 0.0
    assert tight.governor_applied is True
    loose = apply_advisory(snap, governor=LooseningGovernor())
    assert loose.authorized_multiplier == 1.0
    assert loose.authorized_multiplier <= loose.health_recommended_multiplier


def test_paused_recommendation_is_zero_and_still_not_an_order():
    snap = HealthMonitor(instant_config()).evaluate(
        healthy_mr(ts(1), structural_break_detected=True), identity=MR_IDENTITY
    )
    rec = apply_advisory(snap, positions={"this": "is not mutated"})
    assert rec.health_recommended_multiplier == 0.0
    assert rec.authorized_multiplier == 0.0
    assert rec.may_create_order is False
    assert isinstance(rec, AdvisoryRiskRecommendation)


def test_snapshot_flags_cannot_be_set_to_allow_orders():
    snap = HealthMonitor().evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY)
    payload = snap.to_dict()
    payload["may_create_order"] = True
    payload["may_mutate_positions"] = True
    payload["subordinate_to_risk_governor"] = False
    restored = type(snap).from_dict(payload)
    assert restored.may_create_order is False
    assert restored.may_mutate_positions is False
    assert restored.subordinate_to_risk_governor is True
