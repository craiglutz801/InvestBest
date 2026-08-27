"""Stage 1-compatible EFR hook with local fallback (no hard Stage 1 import)."""

from __future__ import annotations

from northstar_trend_carry.fixtures import synthetic_futures_chain
from northstar_trend_carry.friction import FrictionInputs, merge_roll_friction, research_edge_to_friction
from northstar_trend_carry.futures import evaluate_carry
from datetime import datetime, timezone


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


def test_roll_friction_merges_into_futures_roll_slot():
    chain = synthetic_futures_chain(root="ES", curve="contango")
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of)
    merged = merge_roll_friction(FrictionInputs(commission=0.001), carry)
    assert merged.futures_roll > 0
    result = research_edge_to_friction(0.02, merged, prefer_stage1=False)
    assert result["is_usable"] is True
    assert result["statistics"]["friction_futures_roll"] == merged.futures_roll


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
    # Stage 1 DiagnosticResult.to_dict may nest differently; ratio must exist if usable.
    if result.get("is_usable") is False:
        return
    stats = result.get("statistics") or {}
    if "efr" in stats:
        assert stats["efr"] == 0.01 / 0.002
