"""Explicit research-candidate state machine.

Legal statuses: proposed, rejected, research-qualified, shadow-ready,
paused, retired. There is no 'live' state. Winners and failures both remain
auditable; rejected is a retained outcome, not a delete.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping

from northstar_research_loop.safety import ForbiddenActionError, assert_not_live_status


class CandidateStatus(str, Enum):
    PROPOSED = "proposed"
    REJECTED = "rejected"
    RESEARCH_QUALIFIED = "research-qualified"
    SHADOW_READY = "shadow-ready"
    PAUSED = "paused"
    RETIRED = "retired"


TERMINAL_STATUSES = frozenset({CandidateStatus.REJECTED, CandidateStatus.RETIRED})

# From -> allowed to. Safety: nothing transitions to live.
ALLOWED_TRANSITIONS: dict[CandidateStatus, frozenset[CandidateStatus]] = {
    CandidateStatus.PROPOSED: frozenset(
        {
            CandidateStatus.REJECTED,
            CandidateStatus.RESEARCH_QUALIFIED,
            CandidateStatus.SHADOW_READY,
            CandidateStatus.PAUSED,
            CandidateStatus.RETIRED,
        }
    ),
    CandidateStatus.RESEARCH_QUALIFIED: frozenset(
        {
            CandidateStatus.SHADOW_READY,
            CandidateStatus.PAUSED,
            CandidateStatus.RETIRED,
            CandidateStatus.REJECTED,
        }
    ),
    CandidateStatus.SHADOW_READY: frozenset(
        {
            CandidateStatus.PAUSED,
            CandidateStatus.RETIRED,
            CandidateStatus.RESEARCH_QUALIFIED,
        }
    ),
    CandidateStatus.PAUSED: frozenset(
        {
            CandidateStatus.RESEARCH_QUALIFIED,
            CandidateStatus.RETIRED,
        }
    ),
    CandidateStatus.REJECTED: frozenset(),
    CandidateStatus.RETIRED: frozenset(),
}


@dataclass(frozen=True)
class Transition:
    from_status: CandidateStatus
    to_status: CandidateStatus
    reason_codes: tuple[str, ...]
    at: datetime
    note: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "reason_codes": list(self.reason_codes),
            "at": self.at.isoformat(),
            "note": self.note,
        }


class IllegalTransitionError(ValueError):
    pass


def parse_status(value: str | CandidateStatus) -> CandidateStatus:
    if isinstance(value, CandidateStatus):
        assert_not_live_status(value.value)
        return value
    assert_not_live_status(value)
    try:
        return CandidateStatus(value)
    except ValueError as exc:
        raise IllegalTransitionError(f"Unknown candidate status '{value}'") from exc


def can_transition(current: CandidateStatus, target: CandidateStatus) -> bool:
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def transition(
    current: CandidateStatus | str,
    target: CandidateStatus | str,
    reason_codes: tuple[str, ...] = (),
    *,
    note: str = "",
    at: datetime | None = None,
) -> Transition:
    src = parse_status(current)
    dst = parse_status(target)
    if dst.value == "live" or src.value == "live":
        raise ForbiddenActionError("live is not a legal research-loop status")
    if src != dst and not can_transition(src, dst):
        raise IllegalTransitionError(
            f"Illegal transition {src.value} -> {dst.value}. "
            f"Allowed: {sorted(s.value for s in ALLOWED_TRANSITIONS.get(src, frozenset()))}"
        )
    return Transition(
        from_status=src,
        to_status=dst,
        reason_codes=reason_codes,
        at=at or datetime.now(timezone.utc),
        note=note,
    )


def decide_status(
    *,
    currently: CandidateStatus,
    diagnostics_passed: bool,
    eligibility_passed: bool,
    after_friction_passed: bool,
    robustness_passed: bool,
    health_state: str,
    safety_passed: bool,
) -> tuple[CandidateStatus, tuple[str, ...]]:
    """Deterministic next status from pipeline gates. Never returns live."""

    reasons: list[str] = []
    if not safety_passed:
        return CandidateStatus.REJECTED, ("safety.forbidden_or_invalid",)
    if not diagnostics_passed:
        reasons.append("state.diagnostics_failed")
        return CandidateStatus.REJECTED, tuple(reasons)
    if not eligibility_passed:
        reasons.append("state.eligibility_failed")
        return CandidateStatus.REJECTED, tuple(reasons)
    if not after_friction_passed:
        reasons.append("state.after_friction_failed")
        return CandidateStatus.REJECTED, tuple(reasons)
    if not robustness_passed:
        reasons.append("state.robustness_failed")
        return CandidateStatus.REJECTED, tuple(reasons)

    health = health_state.strip().lower()
    if health in {"paused"}:
        return CandidateStatus.PAUSED, ("state.health_paused",)
    if health in {"research_retire", "research_retire_candidate", "retire", "retired"}:
        return CandidateStatus.RETIRED, ("state.health_retire",)

    if currently in {CandidateStatus.PROPOSED, CandidateStatus.PAUSED}:
        if health == "degraded":
            return CandidateStatus.RESEARCH_QUALIFIED, ("state.research_qualified_degraded",)
        return CandidateStatus.SHADOW_READY, ("state.shadow_ready",)

    if currently == CandidateStatus.RESEARCH_QUALIFIED:
        if health == "degraded":
            return CandidateStatus.RESEARCH_QUALIFIED, ("state.remain_qualified_degraded",)
        return CandidateStatus.SHADOW_READY, ("state.shadow_ready",)

    if currently == CandidateStatus.SHADOW_READY:
        if health == "degraded":
            return CandidateStatus.RESEARCH_QUALIFIED, ("state.demote_degraded",)
        return CandidateStatus.SHADOW_READY, ("state.remain_shadow_ready",)

    return CandidateStatus.REJECTED, ("state.unhandled_current_status",)


def status_is_success(status: CandidateStatus) -> bool:
    return status in {CandidateStatus.RESEARCH_QUALIFIED, CandidateStatus.SHADOW_READY}


def audit_fields(status: CandidateStatus) -> Mapping[str, bool]:
    return {
        "retain_record": True,
        "is_failure": status in {CandidateStatus.REJECTED, CandidateStatus.RETIRED, CandidateStatus.PAUSED},
        "is_winner": status == CandidateStatus.SHADOW_READY,
        "is_live": False,
        "self_promoted": False,
    }
