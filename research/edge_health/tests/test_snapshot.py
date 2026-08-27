"""Persistable snapshot schema round-trip."""

from __future__ import annotations

from northstar_edge_health import HealthMonitor, HealthSnapshot

from health_fixtures import MR_IDENTITY, healthy_mr, ts


def test_snapshot_json_roundtrip():
    snap = HealthMonitor().evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY)
    restored = HealthSnapshot.from_json(snap.to_json())
    assert restored.snapshot_id == snap.snapshot_id
    assert restored.state is snap.state
    assert restored.identity.strategy_id == "mr_cadf_residual"
    assert restored.recommended_risk_multiplier == snap.recommended_risk_multiplier
    assert restored.may_create_order is False
    assert restored.subordinate_to_risk_governor is True
    assert restored.evidence_digest["structural_break_detected"] is False


def test_snapshot_id_is_deterministic():
    a = HealthMonitor().evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY, computed_at=ts(1))
    b = HealthMonitor().evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY, computed_at=ts(2))
    assert a.snapshot_id == b.snapshot_id
