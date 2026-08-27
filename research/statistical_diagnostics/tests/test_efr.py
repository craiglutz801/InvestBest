from __future__ import annotations

import math

from northstar_diagnostics.efr import FrictionInputs, edge_to_friction_ratio
from northstar_diagnostics.quality import QualityCode


def test_efr_resilient_and_fragile_bands():
    friction = FrictionInputs(commission=0.0005, spread=0.0005, slippage=0.001)
    # total = 0.002
    resilient = edge_to_friction_ratio(0.01, friction, fragile_below=2.5)
    assert resilient.is_usable
    assert abs(float(resilient.statistics["efr"]) - 5.0) < 1e-12
    assert "implementation_resilient" in resilient.interpretation

    fragile = edge_to_friction_ratio(0.004, friction, fragile_below=2.5)
    assert fragile.is_usable
    assert abs(float(fragile.statistics["efr"]) - 2.0) < 1e-12
    assert "fragile_vs_friction" in fragile.interpretation

    negative = edge_to_friction_ratio(-0.001, friction)
    assert negative.is_usable
    assert "negative_expected_edge" in negative.interpretation


def test_efr_includes_all_friction_legs():
    friction = FrictionInputs(
        commission=1,
        spread=1,
        slippage=1,
        market_impact=1,
        borrow_fees=1,
        dividend_substitute=1,
        financing=1,
        futures_roll=1,
        other=1,
    )
    result = edge_to_friction_ratio(18, friction, fragile_below=2.5)
    assert result.is_usable
    assert result.statistics["expected_round_trip_friction"] == 9
    assert result.statistics["efr"] == 2.0
    assert set(result.details["friction"]) >= {
        "commission",
        "spread",
        "slippage",
        "market_impact",
        "borrow_fees",
        "dividend_substitute",
        "financing",
        "futures_roll",
        "other",
    }


def test_efr_invalid_friction_and_edge():
    zero = edge_to_friction_ratio(0.01, FrictionInputs())
    assert not zero.is_usable
    assert any(f.code == QualityCode.INVALID_FRICTION for f in zero.quality_flags)

    negative_cost = edge_to_friction_ratio(0.01, FrictionInputs(commission=-0.1, spread=0.2))
    assert not negative_cost.is_usable

    nan_edge = edge_to_friction_ratio(float("nan"), FrictionInputs(spread=0.01))
    assert not nan_edge.is_usable
    assert any(f.code == QualityCode.INVALID_EDGE for f in nan_edge.quality_flags)

    inf_friction = edge_to_friction_ratio(0.01, FrictionInputs(market_impact=math.inf))
    assert not inf_friction.is_usable
