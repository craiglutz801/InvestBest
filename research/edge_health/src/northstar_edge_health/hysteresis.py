"""Hysteresis / cooldown so one noisy observation does not flap states."""

from __future__ import annotations

from dataclasses import dataclass

from northstar_edge_health.config import HysteresisConfig
from northstar_edge_health.schema import HysteresisState, ReasonDetail
from northstar_edge_health.scoring import InstantaneousAssessment
from northstar_edge_health.states import HealthState, ReasonCode, STATE_SEVERITY, is_worse_or_equal


@dataclass(frozen=True)
class HysteresisDecision:
    state: HealthState
    hysteresis: HysteresisState
    extra_findings: tuple[ReasonDetail, ...]


def _hold(code: str, message: str) -> ReasonDetail:
    return ReasonDetail(code=code, state=HealthState.HEALTHY, message=message, hard=False)


def apply_hysteresis(
    *,
    previous_state: HealthState | None,
    previous_hysteresis: HysteresisState | None,
    assessment: InstantaneousAssessment,
    config: HysteresisConfig,
    family_chronic_code: str,
) -> HysteresisDecision:
    prev_state = previous_state if previous_state is not None else HealthState.HEALTHY
    prev = previous_hysteresis or HysteresisState()
    inst = assessment.state

    if prev.last_instantaneous is inst:
        consecutive_inst = prev.consecutive_instantaneous + 1
    else:
        consecutive_inst = 1
    consecutive_healthy = prev.consecutive_healthy_instantaneous + 1 if inst is HealthState.HEALTHY else 0

    extra: list[ReasonDetail] = []
    confirmed = _confirmed_target(
        assessment=assessment,
        consecutive_inst=consecutive_inst,
        previous_state=prev_state,
        config=config,
        extra=extra,
    )

    cooldown_remaining = prev.cooldown_remaining
    entering_pause = confirmed in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE} and prev_state not in {
        HealthState.PAUSED,
        HealthState.RESEARCH_RETIRE_CANDIDATE,
    }
    if entering_pause:
        cooldown_remaining = config.cooldown_observations
    elif prev_state in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE}:
        still_pause_level = inst in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE} or assessment.hard_pause
        if still_pause_level:
            cooldown_remaining = max(cooldown_remaining, 1)
        else:
            cooldown_remaining = max(0, cooldown_remaining - 1)

    emitted, extra = _apply_recovery(
        previous_state=prev_state,
        confirmed=confirmed,
        consecutive_healthy=consecutive_healthy,
        cooldown_remaining=cooldown_remaining,
        config=config,
        extra=extra,
    )

    consecutive_pause_emitted = (
        prev.consecutive_pause_emitted + 1
        if emitted in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE}
        else 0
    )
    if (
        emitted is HealthState.PAUSED
        and consecutive_pause_emitted >= config.retire_confirmations
        and previous_state in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE}
    ):
        emitted = HealthState.RESEARCH_RETIRE_CANDIDATE
        extra.append(
            ReasonDetail(
                code=family_chronic_code,
                state=HealthState.RESEARCH_RETIRE_CANDIDATE,
                message="Emitted pause persisted through retire_confirmations; research/retire candidate",
                hard=False,
            )
        )
    if emitted is HealthState.RESEARCH_RETIRE_CANDIDATE:
        retire_codes = {
            family_chronic_code,
            ReasonCode.MR_THESIS_BROKEN,
            ReasonCode.TREND_THESIS_BROKEN,
        }
        present = {item.code for item in tuple(assessment.findings) + tuple(extra)}
        if not present.intersection(retire_codes) and consecutive_pause_emitted >= config.retire_confirmations:
            extra.append(
                ReasonDetail(
                    code=family_chronic_code,
                    state=HealthState.RESEARCH_RETIRE_CANDIDATE,
                    message="Research/retire candidate held after persistent pause",
                    hard=False,
                )
            )

    held = emitted is not confirmed or any(item.code == ReasonCode.HYSTERESIS_HOLD for item in extra)
    hysteresis = HysteresisState(
        consecutive_instantaneous=consecutive_inst,
        last_instantaneous=inst,
        consecutive_healthy_instantaneous=consecutive_healthy,
        consecutive_pause_emitted=consecutive_pause_emitted,
        cooldown_remaining=cooldown_remaining
        if emitted in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE}
        else (0 if emitted is HealthState.HEALTHY else cooldown_remaining),
        held=held,
    )
    return HysteresisDecision(state=emitted, hysteresis=hysteresis, extra_findings=tuple(extra))


def _confirmed_target(
    *,
    assessment: InstantaneousAssessment,
    consecutive_inst: int,
    previous_state: HealthState,
    config: HysteresisConfig,
    extra: list[ReasonDetail],
) -> HealthState:
    inst = assessment.state
    if assessment.hard_retire:
        return HealthState.RESEARCH_RETIRE_CANDIDATE
    if assessment.hard_pause:
        return HealthState.PAUSED if inst is not HealthState.RESEARCH_RETIRE_CANDIDATE else inst
    if inst is HealthState.RESEARCH_RETIRE_CANDIDATE:
        if consecutive_inst >= config.retire_confirmations:
            return HealthState.RESEARCH_RETIRE_CANDIDATE
        return HealthState.PAUSED
    if inst is HealthState.PAUSED:
        if consecutive_inst >= config.paused_confirmations:
            return HealthState.PAUSED
        extra.append(
            _hold(
                ReasonCode.HYSTERESIS_HOLD,
                "Soft pause not confirmed; one noisy observation does not flap to paused",
            )
        )
        if consecutive_inst >= config.degraded_confirmations:
            return HealthState.DEGRADED
        return previous_state if previous_state is HealthState.HEALTHY else worse_hold(previous_state, HealthState.DEGRADED)
    if inst is HealthState.DEGRADED:
        if consecutive_inst >= config.degraded_confirmations:
            return HealthState.DEGRADED
        extra.append(
            _hold(
                ReasonCode.HYSTERESIS_HOLD,
                "Degraded metric not confirmed; one noisy observation does not flap to degraded",
            )
        )
        return previous_state if STATE_SEVERITY[previous_state] <= STATE_SEVERITY[HealthState.DEGRADED] else previous_state
    return HealthState.HEALTHY


def worse_hold(previous: HealthState, floor: HealthState) -> HealthState:
    return previous if is_worse_or_equal(previous, floor) else floor


def _apply_recovery(
    *,
    previous_state: HealthState,
    confirmed: HealthState,
    consecutive_healthy: int,
    cooldown_remaining: int,
    config: HysteresisConfig,
    extra: list[ReasonDetail],
) -> tuple[HealthState, list[ReasonDetail]]:
    if is_worse_or_equal(confirmed, previous_state):
        return confirmed, extra
    # Confirmed is better than previous: recovery path.
    if previous_state in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE} and cooldown_remaining > 0:
        extra.append(
            ReasonDetail(
                code=ReasonCode.COOLDOWN_ACTIVE,
                state=previous_state,
                message="Recovery blocked by pause/retire cooldown",
                hard=False,
                metric="cooldown_remaining",
                value=float(cooldown_remaining),
            )
        )
        return previous_state, extra
    if confirmed is HealthState.HEALTHY and consecutive_healthy < config.recovery_confirmations:
        extra.append(
            ReasonDetail(
                code=ReasonCode.RECOVERY_PENDING,
                state=previous_state,
                message="Recovery requires consecutive healthy observations",
                hard=False,
                metric="consecutive_healthy_instantaneous",
                value=float(consecutive_healthy),
                threshold=float(config.recovery_confirmations),
            )
        )
        # After cooldown, allow a step-down to degraded while waiting for full recovery.
        if previous_state in {HealthState.PAUSED, HealthState.RESEARCH_RETIRE_CANDIDATE}:
            return HealthState.DEGRADED, extra
        return previous_state, extra
    return confirmed, extra
