"""Edge-to-Friction Ratio (research default; never a trade trigger)."""

from __future__ import annotations

from dataclasses import dataclass, fields
from datetime import datetime

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, SampleWindow, failed_result, make_result
from northstar_diagnostics.series import flag, empty_sample

EFR_ASSUMPTIONS = (
    "EFR = expected_gross_edge / expected_round_trip_friction in identical units (e.g. return or bps).",
    "Friction may include commission, spread, slippage, market impact, borrow/dividend substitute, financing, and futures roll.",
    "Research bands (fragile below ~2.5) are configurable and must not create trades by themselves.",
    "Garbage-in / garbage-out: the ratio is only as honest as the edge and friction estimates.",
    "A high EFR does not prove the statistical property required by the strategy still exists.",
)


@dataclass(frozen=True)
class FrictionInputs:
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


def edge_to_friction_ratio(
    expected_gross_edge: float,
    friction: FrictionInputs,
    *,
    fragile_below: float = 2.5,
    as_of: datetime | None = None,
    computed_at: datetime | None = None,
    sample: SampleWindow | None = None,
) -> DiagnosticResult:
    """Compute EFR. Invalid friction/edge inputs fail closed (no ratio treated as a signal)."""

    params = {"fragile_below": fragile_below, "friction": friction.as_dict()}
    used_sample = sample or empty_sample(0)
    flags = []

    components = friction.as_dict()
    if any(v != v or v in (float("inf"), float("-inf")) for v in components.values()):
        flags.append(
            flag(
                QualityCode.INVALID_FRICTION,
                QualityLevel.FAIL,
                "Friction components must be finite",
            )
        )
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
        flags.append(
            flag(
                QualityCode.INVALID_EDGE,
                QualityLevel.FAIL,
                "expected_gross_edge must be finite",
            )
        )

    if flags:
        return failed_result(
            diagnostic_id="efr",
            name="Edge-to-Friction Ratio",
            sample=used_sample,
            method="expected_gross_edge / expected_round_trip_friction",
            parameters=params,
            quality_flags=flags,
            assumptions=EFR_ASSUMPTIONS,
            as_of=as_of,
            computed_at=computed_at,
        )

    efr = float(expected_gross_edge) / float(total)
    if expected_gross_edge < 0:
        interpretation = "negative_expected_edge (not a trade signal)"
    elif efr < fragile_below:
        interpretation = (
            f"fragile_vs_friction_below_{fragile_below:g} (research band only; not a trade signal)"
        )
    else:
        interpretation = (
            f"implementation_resilient_vs_friction_at_or_above_{fragile_below:g} "
            "(research band only; not a trade signal)"
        )

    return make_result(
        diagnostic_id="efr",
        name="Edge-to-Friction Ratio",
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
        pvalue=None,
        hypotheses={
            "definition": "EFR = expected_gross_edge / expected_round_trip_friction",
            "research_fragile_band": f"EFR < {fragile_below:g} is labeled fragile in research defaults",
        },
        assumptions=EFR_ASSUMPTIONS,
        quality_flags=(),
        interpretation=interpretation,
        notes=(
            "Thresholds are research defaults and must remain configurable.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=as_of,
        computed_at=computed_at,
        details={"friction": components},
    )
