"""Happy-path cointegrated pairs/baskets vs false candidates."""

from __future__ import annotations

from northstar_mean_reversion.engine import evaluate_candidate, evaluate_universe
from northstar_mean_reversion.reasons import EligibilityReasonCode
from northstar_mean_reversion.universe import EconomicCandidateUniverse

from fixtures import (
    basket_candidate,
    cointegrated_pair,
    cointegrated_triple,
    independent_triple,
    independent_walks,
    pair_candidate,
    make_config,
)


N = 240


def test_genuine_cointegrated_pair_is_eligible():
    y, x = cointegrated_pair(N, seed=1)
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config())
    assert decision.eligible is True
    assert decision.status == "eligible"
    assert decision.reason_codes == (EligibilityReasonCode.ELIGIBLE,)
    assert decision.hedge_ratio is not None
    assert "cadf" in decision.diagnostics
    assert "spread_adf" in decision.diagnostics
    assert "half_life" in decision.diagnostics
    assert "efr" in decision.diagnostics
    assert not decision.to_dict()["is_trade"]


def test_independent_walks_are_not_eligible():
    y, x = independent_walks(N, seed=2)
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config())
    assert decision.eligible is False
    assert decision.status == "ineligible"
    false_candidate_codes = {
        EligibilityReasonCode.CADF_NOT_COINTEGRATED,
        EligibilityReasonCode.SPREAD_NOT_STATIONARY,
        EligibilityReasonCode.UNSTABLE_HEDGE_RATIO,
        EligibilityReasonCode.STRUCTURAL_BREAK_VETO,
        EligibilityReasonCode.BROKEN_COINTEGRATION,
        EligibilityReasonCode.HALF_LIFE_UNDEFINED,
    }
    assert false_candidate_codes.intersection(decision.reason_codes)
    assert all(code is not EligibilityReasonCode.ELIGIBLE for code in decision.reason_codes)


def test_genuine_cointegrated_basket_is_eligible():
    panel = cointegrated_triple(N, seed=4)
    decision = evaluate_candidate(basket_candidate(panel), config=make_config())
    assert decision.eligible is True
    assert decision.candidate_kind == "basket"
    assert "johansen" in decision.diagnostics


def test_false_basket_is_not_eligible():
    panel = independent_triple(N, seed=5)
    decision = evaluate_candidate(basket_candidate(panel), config=make_config())
    assert decision.eligible is False
    assert (
        EligibilityReasonCode.JOHANSEN_RANK_ZERO in decision.reason_codes
        or EligibilityReasonCode.SPREAD_NOT_STATIONARY in decision.reason_codes
    )


def test_evaluate_universe_keeps_per_candidate_reason_codes():
    good_y, good_x = cointegrated_pair(N, seed=6)
    bad_y, bad_x = independent_walks(N, seed=7)
    universe = EconomicCandidateUniverse(
        name="research-shadow",
        candidates=(
            pair_candidate(good_y, good_x, candidate_id="GOOD"),
            pair_candidate(bad_y, bad_x, candidate_id="BAD"),
        ),
    )
    decisions = evaluate_universe(universe, config=make_config())
    by_id = {item.candidate_id: item for item in decisions}
    assert by_id["GOOD"].eligible is True
    assert by_id["BAD"].eligible is False
    assert by_id["BAD"].reason_codes
