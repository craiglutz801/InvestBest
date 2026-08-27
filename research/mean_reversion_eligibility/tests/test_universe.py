"""Universe interface: declared economic relationships only; no LLM discovery."""

from __future__ import annotations

from northstar_mean_reversion.reasons import EligibilityReasonCode
from northstar_mean_reversion.universe import (
    EconomicCandidate,
    EconomicCandidateUniverse,
    RelationshipKind,
    validate_economic_candidate,
)

from fixtures import ar1, pair_candidate, random_walk, make_config
from northstar_mean_reversion.engine import evaluate_candidate


def test_declared_sector_peers_pass_universe_gate():
    y, x = random_walk(80), random_walk(80, seed=3)
    candidate = pair_candidate(y, x)
    issues = validate_economic_candidate(candidate)
    assert issues == ()


def test_missing_rationale_is_rejected_as_llm_style_list():
    y, x = random_walk(80), random_walk(80, seed=3)
    candidate = EconomicCandidate(
        candidate_id="LLM-LIST",
        symbols=("AAA", "BBB"),
        relationship_kind=None,
        relationship_rationale="   ",
        legs={"AAA": y, "BBB": x},
        holding_horizon=5.0,
    )
    issues = validate_economic_candidate(candidate)
    codes = {issue.reason_code for issue in issues}
    assert EligibilityReasonCode.MISSING_ECONOMIC_RELATIONSHIP in codes
    decision = evaluate_candidate(candidate, config=make_config(require_efr=False))
    assert not decision.eligible
    assert EligibilityReasonCode.MISSING_ECONOMIC_RELATIONSHIP in decision.reason_codes


def test_single_leg_is_not_a_candidate():
    y = ar1(80, phi=0.2)
    candidate = EconomicCandidate(
        candidate_id="UNIVARIATE",
        symbols=("AAA",),
        relationship_kind=RelationshipKind.OTHER_DECLARED,
        relationship_rationale="none",
        legs={"AAA": y},
        holding_horizon=5.0,
    )
    issues = validate_economic_candidate(candidate)
    assert any(issue.reason_code is EligibilityReasonCode.INSUFFICIENT_LEGS for issue in issues)


def test_universe_container_returns_candidates_in_order():
    y, x = random_walk(50), random_walk(50, seed=1)
    a = pair_candidate(y, x, candidate_id="A")
    b = pair_candidate(x, y, candidate_id="B")
    universe = EconomicCandidateUniverse(name="declared-peers", candidates=(a, b))
    assert universe.get("B").candidate_id == "B"
    assert [c.candidate_id for c in universe.candidates] == ["A", "B"]
