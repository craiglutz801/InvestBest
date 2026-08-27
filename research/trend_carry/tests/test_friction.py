"""Stage 1-compatible EFR hook with local fallback (no hard Stage 1 import)."""

from __future__ import annotations

from datetime import datetime, timezone

from northstar_trend_carry.fixtures import synthetic_futures_chain, two_leg_chain
from northstar_trend_carry.friction import FrictionInputs, merge_roll_friction, research_edge_to_friction
from northstar_trend_carry.futures import evaluate_carry


def test_local_efr_matches_definition():
    friction = FrictionInputs(commission=0.001, spread=0.0005, futures_roll=0.0005)
    result = research_edge_to_friction(0.01, friction, prefer_stage1=False)
    assert result["is_usable"] is True
    assert result["is_order"] is False
    assert result["statistics"]["efr"] == 0.01 / 0.002
    assert result["parameters"]["efr_implementation"] == "local_stage3_fallback"
    assert "not a trade" in result["interpretation"]


def test_fragile_band_is_research_only():
    friction = FrictionInputs(commission=0.01)
    low = research_edge_to_friction(0.012, friction, prefer_stage1=False)
    assert "fragile" in low["interpretation"]
    high = research_edge_to_friction(0.05, friction, prefer_stage1=False)
    assert "implementation_resilient" in high["interpretation"]


def test_invalid_friction_and_edge_fail_closed():
    bad = research_edge_to_friction(0.01, FrictionInputs(commission=-0.1), prefer_stage1=False)
    assert bad["is_usable"] is False
    zero = research_edge_to_friction(0.01, FrictionInputs(), prefer_stage1=False)
    assert zero["is_usable"] is False
    nan = research_edge_to_friction(float("nan"), FrictionInputs(commission=0.01), prefer_stage1=False)
    assert nan["is_usable"] is False


def test_five_percent_curve_gap_with_zero_fees_is_not_five_percent_efr_friction():
    """A 5% contract curve gap with no bid/ask/fees is carry, not 5% execution friction."""

    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    chain = two_leg_chain(front_price=100.0, next_price=105.0, as_of=as_of)
    carry = evaluate_carry(chain, as_of=as_of)
    assert carry.curve_gap == 0.05
    assert carry.execution_roll_friction is None

    base = FrictionInputs()  # all zeros: no bid/ask, commissions, or fees
    merged = merge_roll_friction(base, carry)
    assert merged.futures_roll == 0.0
    assert merged.as_dict() == base.as_dict()

    # Caller-supplied tiny execution cost must stay tiny; must not become ~5%.
    with_fee = merge_roll_friction(FrictionInputs(commission=0.001), carry)
    assert with_fee.futures_roll == 0.0
    assert with_fee.commission == 0.001
    result = research_edge_to_friction(0.02, with_fee, prefer_stage1=False)
    assert result["is_usable"] is True
    assert result["statistics"]["efr"] == 0.02 / 0.001
    assert result["statistics"]["friction_futures_roll"] == 0.0
    assert abs(result["statistics"]["expected_round_trip_friction"] - 0.05) > 0.01


def test_bid_ask_execution_friction_is_not_the_curve_gap():
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    chain = two_leg_chain(
        front_price=100.0,
        next_price=105.0,
        as_of=as_of,
        front_bid=99.5,
        front_ask=100.5,
        next_bid=104.5,
        next_ask=105.5,
    )
    carry = evaluate_carry(chain, as_of=as_of)
    assert carry.curve_gap == 0.05
    assert carry.execution_roll_friction is not None
    assert carry.execution_roll_friction_source == "bid_ask_half_spreads"
    # Half-spreads: 0.5/100 + 0.5/105 ≈ 0.00976, not 0.05.
    expected = (0.5 / 100.0) + (0.5 / 105.0)
    assert carry.execution_roll_friction == expected
    assert abs(carry.execution_roll_friction - 0.05) > 0.03

    merged = merge_roll_friction(FrictionInputs(), carry)
    assert merged.futures_roll == expected
    result = research_edge_to_friction(0.05, merged, prefer_stage1=False)
    assert result["statistics"]["friction_futures_roll"] == expected
    assert result["statistics"]["efr"] == 0.05 / expected


def test_merge_does_not_infer_friction_from_synthetic_contango_chain():
    chain = synthetic_futures_chain(root="ES", curve="contango")
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of)
    assert carry.is_usable
    assert carry.curve_gap is not None and carry.curve_gap > 0
    merged = merge_roll_friction(FrictionInputs(commission=0.001), carry)
    assert merged.futures_roll == 0.0


def test_stage1_delegation_is_optional():
    """If Stage 1 is absent, the local fallback still works. If present, either is fine."""

    friction = FrictionInputs(commission=0.002)
    result = research_edge_to_friction(0.01, friction, prefer_stage1=True)
    impl = result.get("efr_implementation") or result.get("parameters", {}).get("efr_implementation")
    assert impl in {
        "local_stage3_fallback",
        "stage1_northstar_diagnostics",
        None,
    }
    if result.get("is_usable") is False:
        return
    stats = result.get("statistics") or {}
    if "efr" in stats:
        assert stats["efr"] == 0.01 / 0.002
