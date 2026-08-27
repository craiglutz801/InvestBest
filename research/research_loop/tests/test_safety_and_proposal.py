from __future__ import annotations

import pytest

from northstar_research_loop.proposal import make_proposal, validate_proposal
from northstar_research_loop.safety import (
    ALLOWED_MUTATION_TARGETS,
    ForbiddenAction,
    ForbiddenActionError,
    RESEARCH_AGENT_CAPABILITY,
    assert_action_allowed,
)


def test_capability_bitmap_is_research_only():
    cap = RESEARCH_AGENT_CAPABILITY.as_dict()
    assert cap["can_propose_bounded_experiments"] is True
    assert cap["can_place_trade"] is False
    assert cap["can_bypass_risk"] is False
    assert cap["can_self_merge"] is False
    assert cap["can_self_deploy"] is False
    assert cap["can_self_promote_to_live"] is False
    assert cap["can_modify_broker_safety"] is False
    assert cap["can_hide_failed_experiments"] is False


@pytest.mark.parametrize("action", list(ForbiddenAction))
def test_forbidden_actions_raise(action: ForbiddenAction):
    with pytest.raises(ForbiddenActionError):
        assert_action_allowed(action)


def test_bounded_proposal_is_valid():
    proposal = make_proposal(
        hypothesis="Widen formation window one step",
        mutation_target="formation_window",
        config_delta={"lookback_bars": 150},
        baseline_ref="baseline.v1",
        edge_contract_id="edge.mr.synthetic.v1",
    )
    assert proposal.mutation_target in ALLOWED_MUTATION_TARGETS
    assert validate_proposal(proposal) == ()


def test_proposal_rejects_broker_and_live_keys():
    proposal = make_proposal(
        hypothesis="secretly enable live trading",
        mutation_target="strategy_config",
        config_delta={"buy_threshold": 0.2, "live_trading": True, "broker_api_key": "x"},
        baseline_ref="baseline.v1",
        edge_contract_id="edge.mr.synthetic.v1",
    )
    reasons = validate_proposal(proposal)
    assert any(code.startswith("proposal.forbidden") for code in reasons)


def test_disallowed_mutation_target():
    proposal = make_proposal(
        hypothesis="change execution",
        mutation_target="execution_code",
        config_delta={"foo": 1},
        baseline_ref="baseline.v1",
        edge_contract_id="edge.mr.synthetic.v1",
    )
    assert "proposal.mutation_target_not_allowed" in validate_proposal(proposal)
