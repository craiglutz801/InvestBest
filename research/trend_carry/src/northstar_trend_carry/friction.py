"""Edge-to-friction hook compatible with Stage 1, without a hard dependency.

If ``northstar_diagnostics`` is importable (Stage 1 draft package), EFR
delegates to that implementation. Otherwise a local fallback computes
EFR = expected_gross_edge / expected_round_trip_friction using the same
component names, including ``futures_roll``.

This hook never places an order.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from datetime import datetime
from typing import Any

from northstar_trend_carry.futures import CarrySnapshot
from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import (
    QualityFlag,
    RESEARCH_ONLY_NOTE,
    SampleWindow,
    empty_sample,
    jsonable,
    library_versions,
    result_envelope,
    utcnow,
)

EFR_ASSUMPTIONS = (
    "EFR = expected_gross_edge / expected_round_trip_friction in identical units.",
    "Friction may include commission, spread, slippage, impact, borrow, dividend substitute, financing, and futures roll.",
    "Research bands (fragile below ~2.5) are configurable and must not create trades.",
    "Stage 1 northstar_diagnostics is used when installed; otherwise a local fallback is used.",
)


@dataclass(frozen=True)
class FrictionInputs:
    """Component names match Stage 1 ``northstar_diagnostics.efr.FrictionInputs``."""

    commission: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    borrow_fees: float = 0.0
    dividend_substitute: float = 0.0
    financing: float = 0.0
    futures_roll: float = 0.0
    other: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {f.name: float(getattr(self, f.name)) for f in fields(self)}

    def total(self) -> float:
        return float(sum(self.as_dict().values()))


def merge_roll_friction(base: FrictionInputs, carry: CarrySnapshot) -> FrictionInputs:
    """Add estimated listed-contract roll friction into the futures_roll slot."""

    extra = carry.estimated_roll_friction or 0.0
    if extra != extra or extra in (float("inf"), float("-inf")):
        extra = 0.0
    return replace(base, futures_roll=float(base.futures_roll) + abs(float(extra)))


def _try_stage1_efr(
    expected_gross_edge: float,
    friction: FrictionInputs,
    *,
    fragile_below: float,
    as_of: datetime | None,
    computed_at: datetime | None,
    sample: SampleWindow | None,
) -> dict[str, Any] | None:
    try:
        from northstar_diagnostics.efr import FrictionInputs as Stage1Friction
        from northstar_diagnostics.efr import edge_to_friction_ratio
    except ImportError:
        return None

    stage1 = Stage1Friction(**friction.as_dict())
    result = edge_to_friction_ratio(
        expected_gross_edge,
        stage1,
        fragile_below=fragile_below,
        as_of=as_of,
        computed_at=computed_at,
        sample=sample,
    )
    payload = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    payload["efr_implementation"] = "stage1_northstar_diagnostics"
    payload["is_order"] = False
    payload["activates_production_signal"] = False
    return payload


def research_edge_to_friction(
    expected_gross_edge: float,
    friction: FrictionInputs,
    *,
    fragile_below: float = 2.5,
    as_of: datetime | None = None,
    computed_at: datetime | None = None,
    sample: SampleWindow | None = None,
    prefer_stage1: bool = True,
) -> dict[str, Any]:
    """Compute EFR. Optional Stage 1 delegation; always fail-closed on bad inputs."""

    used_sample = sample or empty_sample(0)
    if prefer_stage1:
        delegated = _try_stage1_efr(
            expected_gross_edge,
            friction,
            fragile_below=fragile_below,
            as_of=as_of,
            computed_at=computed_at,
            sample=used_sample,
        )
        if delegated is not None:
            return delegated

    flags: list[QualityFlag] = []
    components = friction.as_dict()
    if any(v != v or v in (float("inf"), float("-inf")) for v in components.values()):
        flags.append(flag(QualityCode.INVALID_FRICTION, QualityLevel.FAIL, "Friction components must be finite"))
    if any(v < 0 for v in components.values() if v == v):
        flags.append(
            flag(
                QualityCode.INVALID_FRICTION,
                QualityLevel.FAIL,
                "Friction components must be >= 0 (costs cannot be negative)",
            )
        )
    total = friction.total()
    if total != total or total in (float("inf"), float("-inf")) or total <= 0:
        flags.append(
            flag(
                QualityCode.INVALID_FRICTION,
                QualityLevel.FAIL,
                "Round-trip friction must be finite and strictly positive",
            )
        )
    if expected_gross_edge != expected_gross_edge or expected_gross_edge in (
        float("inf"),
        float("-inf"),
    ):
        flags.append(flag(QualityCode.INVALID_EDGE, QualityLevel.FAIL, "expected_gross_edge must be finite"))

    params = {"fragile_below": fragile_below, "friction": components, "efr_implementation": "local_stage3_fallback"}
    if flags:
        return result_envelope(
            result_id="efr",
            name="Edge-to-Friction Ratio (Stage 3 local fallback)",
            sample=used_sample,
            method="expected_gross_edge / expected_round_trip_friction",
            parameters=params,
            statistics={},
            quality_flags=flags,
            interpretation="not_computed",
            assumptions=EFR_ASSUMPTIONS,
            notes=(RESEARCH_ONLY_NOTE,),
            as_of=as_of,
            computed_at=computed_at,
        )

    efr = float(expected_gross_edge) / float(total)
    if expected_gross_edge < 0:
        interpretation = "negative_expected_edge (not a trade signal)"
    elif efr < fragile_below:
        interpretation = f"fragile_vs_friction_below_{fragile_below:g} (research band only; not a trade signal)"
    else:
        interpretation = (
            f"implementation_resilient_vs_friction_at_or_above_{fragile_below:g} "
            "(research band only; not a trade signal)"
        )
    return result_envelope(
        result_id="efr",
        name="Edge-to-Friction Ratio (Stage 3 local fallback)",
        sample=used_sample,
        method="expected_gross_edge / expected_round_trip_friction",
        parameters=params,
        statistics={
            "efr": efr,
            "expected_gross_edge": float(expected_gross_edge),
            "expected_round_trip_friction": float(total),
            "fragile_below": float(fragile_below),
            **{f"friction_{k}": v for k, v in components.items()},
        },
        quality_flags=(),
        interpretation=interpretation,
        assumptions=EFR_ASSUMPTIONS,
        notes=(RESEARCH_ONLY_NOTE, "Thresholds are research defaults and must remain configurable."),
        details={"friction": components, "library_versions": library_versions()},
        as_of=as_of,
        computed_at=computed_at,
    )
