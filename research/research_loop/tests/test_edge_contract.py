from __future__ import annotations

import pytest

from northstar_research_loop.edge_contract import (
    CHAN_REVIEW_QUESTIONS,
    EDGE_CONTRACT_SCHEMA_VERSION,
    EdgeContract,
    EdgeContractError,
    ExpectedCosts,
    HoldingPeriod,
    NamedRule,
    default_mean_reversion_contract,
    require_valid_edge_contract,
    validate_edge_contract,
)


def test_default_contract_is_valid_and_versioned():
    contract = default_mean_reversion_contract()
    assert contract.schema_version == EDGE_CONTRACT_SCHEMA_VERSION
    assert validate_edge_contract(contract) == ()
    payload = contract.to_dict()
    assert payload["identity_key"] == contract.identity_key()
    assert "mean_reversion" in payload["identity_key"]
    assert payload["expected_costs"]["total"] > 0
    assert payload["formation_tests"]
    assert payload["live_health_tests"]
    assert payload["break_conditions"]
    assert payload["retirement_rules"]
    assert payload["chan_review_questions"] == list(CHAN_REVIEW_QUESTIONS)


def test_missing_mechanism_and_family_fail_closed():
    contract = default_mean_reversion_contract()
    broken = EdgeContract(
        contract_id="",
        name="",
        strategy_family="not-a-family",
        mechanism="",
        required_statistical_property="",
        instruments=(),
        horizon="",
        expected_holding_period=HoldingPeriod(amount=0, unit="days"),
        expected_costs=ExpectedCosts(),
        good_regimes=(),
        bad_regimes=(),
        formation_tests=(),
        live_health_tests=(),
        break_conditions=(),
        retirement_rules=(),
        throttle_rules=(),
    )
    reasons = validate_edge_contract(broken)
    assert "edge.missing_contract_id" in reasons
    assert "edge.unknown_strategy_family" in reasons
    assert "edge.missing_mechanism" in reasons
    assert "edge.missing_instruments" in reasons
    with pytest.raises(EdgeContractError):
        require_valid_edge_contract(broken)
    # original fixture still valid
    assert validate_edge_contract(contract) == ()
