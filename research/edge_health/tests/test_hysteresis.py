"""Hysteresis: no flap from one noisy observation; recovery only after cooldown."""

from __future__ import annotations

from northstar_edge_health import HealthConfig, HealthMonitor, HealthState, ReasonCode
from northstar_edge_health.config import HysteresisConfig

from health_fixtures import MR_IDENTITY, healthy_mr, later, ts


def _monitor() -> HealthMonitor:
    return HealthMonitor(
        HealthConfig(
            hysteresis=HysteresisConfig(
                degraded_confirmations=2,
                paused_confirmations=2,
                retire_confirmations=4,
                recovery_confirmations=3,
                cooldown_observations=2,
            )
        )
    )


def test_one_noisy_degraded_observation_does_not_flap():
    monitor = _monitor()
    first = monitor.evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY)
    noisy = monitor.evaluate(
        healthy_mr(ts(2), half_life=16.0),
        identity=MR_IDENTITY,
        history=(first,),
    )
    assert first.state is HealthState.HEALTHY
    assert noisy.instantaneous_state is HealthState.DEGRADED
    assert noisy.state is HealthState.HEALTHY
    assert ReasonCode.HYSTERESIS_HOLD in noisy.reason_codes
    assert noisy.recommended_risk_multiplier == 1.0


def test_gradual_degradation_after_confirmations():
    monitor = _monitor()
    snaps = monitor.evaluate_sequence(
        (
            healthy_mr(ts(1)),
            healthy_mr(ts(2), half_life=16.0),
            healthy_mr(ts(3), half_life=16.5),
        ),
        identity=MR_IDENTITY,
    )
    assert [s.state for s in snaps] == [
        HealthState.HEALTHY,
        HealthState.HEALTHY,
        HealthState.DEGRADED,
    ]
    assert ReasonCode.MR_HALF_LIFE_DRIFT in snaps[2].reason_codes
    assert snaps[2].recommended_risk_multiplier == 0.5


def test_soft_pause_requires_confirmations():
    monitor = _monitor()
    snaps = monitor.evaluate_sequence(
        (
            healthy_mr(ts(1)),
            healthy_mr(ts(2), residual_volatility=0.08),
            healthy_mr(ts(3), residual_volatility=0.09),
        ),
        identity=MR_IDENTITY,
    )
    assert snaps[1].instantaneous_state is HealthState.PAUSED
    assert snaps[1].state is HealthState.HEALTHY
    assert snaps[2].state is HealthState.PAUSED
    assert snaps[2].recommended_risk_multiplier == 0.0


def test_structural_break_pauses_immediately_without_waiting_for_soft_confirmations():
    monitor = _monitor()
    healthy = monitor.evaluate(healthy_mr(ts(1)), identity=MR_IDENTITY)
    paused = monitor.evaluate(
        healthy_mr(ts(2), structural_break_detected=True),
        identity=MR_IDENTITY,
        history=(healthy,),
    )
    assert paused.state is HealthState.PAUSED
    assert ReasonCode.MR_STRUCTURAL_BREAK in paused.reason_codes
    assert paused.hysteresis.cooldown_remaining == 2


def test_recovery_only_after_hysteresis_and_cooldown():
    monitor = _monitor()
    t0 = ts(1)
    rows = [
        healthy_mr(t0, structural_break_detected=True),
    ]
    # Break clears starting day 2.
    for day in range(2, 8):
        rows.append(healthy_mr(later(t0, day - 1)))
    snaps = monitor.evaluate_sequence(tuple(rows), identity=MR_IDENTITY)
    assert snaps[0].state is HealthState.PAUSED
    # Cooldown holds pause while remaining > 0.
    assert snaps[1].state is HealthState.PAUSED
    assert ReasonCode.COOLDOWN_ACTIVE in snaps[1].reason_codes
    # After cooldown, step down then require recovery confirmations.
    assert HealthState.HEALTHY not in {snaps[1].state, snaps[2].state}
    healthy_states = [i for i, snap in enumerate(snaps) if snap.state is HealthState.HEALTHY]
    assert healthy_states, "should eventually recover"
    assert healthy_states[0] >= 3
    assert snaps[-1].state is HealthState.HEALTHY
    assert snaps[-1].recommended_risk_multiplier == 1.0


def test_chronic_pause_becomes_research_retire_candidate():
    monitor = _monitor()
    rows = tuple(healthy_mr(ts(day), structural_break_detected=True) for day in range(1, 6))
    snaps = monitor.evaluate_sequence(rows, identity=MR_IDENTITY)
    assert snaps[0].state is HealthState.PAUSED
    assert snaps[-1].state is HealthState.RESEARCH_RETIRE_CANDIDATE
    assert ReasonCode.MR_CHRONIC_PAUSE in snaps[-1].reason_codes
    assert snaps[-1].recommended_risk_multiplier == 0.0


def test_degraded_recovery_requires_consecutive_healthy_observations():
    monitor = _monitor()
    rows = (
        healthy_mr(ts(1), half_life=16.0),
        healthy_mr(ts(2), half_life=16.0),
        healthy_mr(ts(3)),
        healthy_mr(ts(4)),
        healthy_mr(ts(5)),
    )
    snaps = monitor.evaluate_sequence(rows, identity=MR_IDENTITY)
    assert snaps[1].state is HealthState.DEGRADED
    assert snaps[2].state is HealthState.DEGRADED
    assert ReasonCode.RECOVERY_PENDING in snaps[2].reason_codes
    assert snaps[3].state is HealthState.DEGRADED
    assert snaps[4].state is HealthState.HEALTHY
