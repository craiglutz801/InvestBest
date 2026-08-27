from __future__ import annotations

import pytest

from northstar_research_loop.safety import ForbiddenActionError
from northstar_research_loop.state_machine import (
    CandidateStatus,
    IllegalTransitionError,
    can_transition,
    decide_status,
    transition,
)


def test_no_path_to_live():
    for status in CandidateStatus:
        allowed = {s.value for s in __import__(
            "northstar_research_loop.state_machine", fromlist=["ALLOWED_TRANSITIONS"]
        ).ALLOWED_TRANSITIONS[status]}
        assert "live" not in allowed
        with pytest.raises(ForbiddenActionError):
            transition(status, "live")


def test_rejected_and_retired_are_terminal():
    assert not can_transition(CandidateStatus.REJECTED, CandidateStatus.SHADOW_READY)
    assert not can_transition(CandidateStatus.RETIRED, CandidateStatus.PROPOSED)
    with pytest.raises(IllegalTransitionError):
        transition(CandidateStatus.REJECTED, CandidateStatus.RESEARCH_QUALIFIED)


def test_proposed_can_become_shadow_ready_via_healthy_gates():
    status, reasons = decide_status(
        currently=CandidateStatus.PROPOSED,
        diagnostics_passed=True,
        eligibility_passed=True,
        after_friction_passed=True,
        robustness_passed=True,
        health_state="healthy",
        safety_passed=True,
    )
    assert status == CandidateStatus.SHADOW_READY
    assert "state.shadow_ready" in reasons
    moved = transition(CandidateStatus.PROPOSED, status, reason_codes=reasons)
    assert moved.to_status == CandidateStatus.SHADOW_READY


def test_break_and_overfit_fail_closed():
    paused, _ = decide_status(
        currently=CandidateStatus.PROPOSED,
        diagnostics_passed=True,
        eligibility_passed=True,
        after_friction_passed=True,
        robustness_passed=True,
        health_state="paused",
        safety_passed=True,
    )
    assert paused == CandidateStatus.PAUSED
    rejected, reasons = decide_status(
        currently=CandidateStatus.PROPOSED,
        diagnostics_passed=True,
        eligibility_passed=True,
        after_friction_passed=True,
        robustness_passed=False,
        health_state="healthy",
        safety_passed=True,
    )
    assert rejected == CandidateStatus.REJECTED
    assert "state.robustness_failed" in reasons
