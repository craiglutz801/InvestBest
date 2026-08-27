"""Point-in-time: future observations cannot change emitted health."""

from __future__ import annotations

from northstar_edge_health import HealthMonitor, HealthState, ReasonCode

from health_fixtures import MR_IDENTITY, healthy_mr, ts


def test_evaluate_sequence_ignores_evidence_after_cutoff():
    monitor = HealthMonitor()
    rows = (
        healthy_mr(ts(1)),
        healthy_mr(ts(2)),
        healthy_mr(ts(3), structural_break_detected=True),
    )
    as_of_day2 = monitor.evaluate_sequence(rows, identity=MR_IDENTITY, as_of=ts(2))
    as_of_day3 = monitor.evaluate_sequence(rows, identity=MR_IDENTITY, as_of=ts(3))
    assert len(as_of_day2) == 2
    assert as_of_day2[-1].state is HealthState.HEALTHY
    assert as_of_day2[-1].as_of == ts(2)
    assert as_of_day3[-1].state is HealthState.PAUSED
    assert ReasonCode.MR_STRUCTURAL_BREAK in as_of_day3[-1].reason_codes


def test_history_with_future_snapshots_is_ignored():
    monitor = HealthMonitor()
    past = monitor.evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY)
    future_break = monitor.evaluate(
        healthy_mr(ts(3), structural_break_detected=True),
        identity=MR_IDENTITY,
    )
    now = monitor.evaluate(
        healthy_mr(ts(2)),
        identity=MR_IDENTITY,
        history=(past, future_break),
        as_of=ts(2),
    )
    assert now.state is HealthState.HEALTHY
    assert now.previous_state is HealthState.HEALTHY
    assert ReasonCode.MR_STRUCTURAL_BREAK not in now.reason_codes


def test_evidence_after_cutoff_fails_closed_rather_than_using_future_bar():
    monitor = HealthMonitor()
    snap = monitor.evaluate(healthy_mr(ts(3)), identity=MR_IDENTITY, as_of=ts(2))
    assert snap.fail_closed is True
    assert snap.state is HealthState.PAUSED
    assert ReasonCode.FUTURE_OBSERVATION in snap.reason_codes
    assert snap.recommended_risk_multiplier == 0.0


def test_non_monotonic_sequence_fails_closed():
    monitor = HealthMonitor()
    snaps = monitor.evaluate_sequence(
        (healthy_mr(ts(3)), healthy_mr(ts(1))),
        identity=MR_IDENTITY,
    )
    assert len(snaps) == 1
    assert snaps[0].fail_closed is True
    assert ReasonCode.NON_MONOTONIC_HISTORY in snaps[0].reason_codes
