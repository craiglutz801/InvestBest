"""Integrated synthetic end-to-end harness for morning review.

Runs against native Stage 1–5 APIs. A silent synthetic_fail_closed fallback
is a harness failure when those packages are installed.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Mapping

from northstar_research_loop.adapters.discovery import (
    NativeStageMissingError,
    discover_all,
    require_native_stages,
)
from northstar_research_loop.edge_contract import default_mean_reversion_contract
from northstar_research_loop.native_evidence import evidence_for
from northstar_research_loop.pipeline import PipelineResult, ResearchLoopPipeline
from northstar_research_loop.proposal import make_proposal
from northstar_research_loop.registry import ExperimentRegistry
from northstar_research_loop.state_machine import CandidateStatus

PASSING_STATUSES = {CandidateStatus.SHADOW_READY, CandidateStatus.RESEARCH_QUALIFIED}

NATIVE_GATES = {
    "diagnostics": "northstar_diagnostics",
    "eligibility": "northstar_mean_reversion",
    "trend_context": "northstar_trend_carry",
    "health": "northstar_edge_health",
    "robustness": "northstar_promotion",
    "sizing": "northstar_promotion",
}


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    kind: str
    expect_status: CandidateStatus
    notes: str


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec("good_candidate", "good", CandidateStatus.SHADOW_READY, "Native cointegrated pair, EFR cushion, plateau, healthy."),
    ScenarioSpec("overfit_candidate", "overfit", CandidateStatus.REJECTED, "Native promotion rejects isolated peak / holdout peek / high trial count."),
    ScenarioSpec("high_friction_candidate", "high_friction", CandidateStatus.REJECTED, "Native EFR below research band."),
    ScenarioSpec("structurally_broken_candidate", "broken", CandidateStatus.PAUSED, "Native Stage 4 structural-break pause."),
    ScenarioSpec("statistically_invalid_candidate", "invalid", CandidateStatus.REJECTED, "Native Stage 2 rejects independent walks."),
)


@dataclass(frozen=True)
class ScenarioOutcome:
    name: str
    expected: str
    actual: str
    passed: bool
    reason_codes: tuple[str, ...]
    native_sources: Mapping[str, str | None]
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "native_sources": dict(self.native_sources),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class HarnessReport:
    all_passed: bool
    outcomes: tuple[ScenarioOutcome, ...]
    retained_failures: int
    retained_winners: int
    discovered: Mapping[int, Mapping[str, object]]
    native_required: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "retained_failures": self.retained_failures,
            "retained_winners": self.retained_winners,
            "discovered": {str(k): dict(v) for k, v in self.discovered.items()},
            "native_required": self.native_required,
            "error": self.error,
            "places_trade": False,
            "promotes_to_live": False,
        }


def _native_sources(result: PipelineResult) -> dict[str, str | None]:
    by_gate = {g.gate: g.source_package for g in result.gates}
    return {gate: by_gate.get(gate) for gate in NATIVE_GATES}


def _native_ok(sources: Mapping[str, str | None]) -> bool:
    for gate, expected in NATIVE_GATES.items():
        if sources.get(gate) != expected:
            return False
    return True


def run_scenario(spec: ScenarioSpec, pipeline: ResearchLoopPipeline) -> tuple[ScenarioOutcome, PipelineResult]:
    contract = default_mean_reversion_contract()
    proposal = make_proposal(
        hypothesis=spec.notes,
        mutation_target="thresholds",
        config_delta={"entry_zscore": 2.0, "formation_window": 120},
        baseline_ref="synthetic.baseline",
        edge_contract_id=contract.contract_id,
        notes=(spec.name,),
    )
    result = pipeline.evaluate(
        contract=contract,
        proposal=proposal,
        evidence=evidence_for(spec.kind, f"harness.{spec.name}"),  # type: ignore[arg-type]
        experiment_id=f"harness.{spec.name}",
    )
    actual = result.status
    expected = spec.expect_status
    sources = _native_sources(result)
    if spec.name == "structurally_broken_candidate":
        status_ok = actual in {CandidateStatus.PAUSED, CandidateStatus.REJECTED, CandidateStatus.RETIRED}
    elif spec.name == "good_candidate":
        status_ok = actual in PASSING_STATUSES
    else:
        status_ok = actual == expected and actual not in PASSING_STATUSES
    ok = status_ok and _native_ok(sources)
    return (
        ScenarioOutcome(
            name=spec.name,
            expected=expected.value,
            actual=actual.value,
            passed=ok,
            reason_codes=result.reason_codes,
            native_sources=sources,
            notes=spec.notes,
        ),
        result,
    )


def run_synthetic_battery(
    registry: ExperimentRegistry | None = None,
    *,
    require_native: bool = True,
) -> HarnessReport:
    discovered = {k: v.to_dict() for k, v in discover_all().items()}
    if require_native:
        try:
            require_native_stages()
        except NativeStageMissingError as exc:
            return HarnessReport(
                all_passed=False,
                outcomes=(),
                retained_failures=0,
                retained_winners=0,
                discovered=discovered,
                native_required=True,
                error=str(exc),
            )
    pipeline = ResearchLoopPipeline(
        registry=registry if registry is not None else ExperimentRegistry(),
        require_native=require_native,
    )
    outcomes: list[ScenarioOutcome] = []
    for spec in SCENARIOS:
        outcome, _ = run_scenario(spec, pipeline)
        outcomes.append(outcome)
    return HarnessReport(
        all_passed=all(item.passed for item in outcomes),
        outcomes=tuple(outcomes),
        retained_failures=len(pipeline.registry.failures()),
        retained_winners=len(pipeline.registry.winners()),
        discovered=discovered,
        native_required=require_native,
    )


def main(argv: list[str] | None = None) -> int:
    _ = argv
    report = run_synthetic_battery(require_native=True)
    json.dump(report.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if report.error:
        sys.stderr.write(f"CHAN_HARNESS_FAIL: {report.error}\n")
        return 1
    if not report.all_passed:
        sys.stderr.write("CHAN_HARNESS_FAIL: scenario missed expected status or native source\n")
        return 1
    sys.stderr.write(
        "CHAN_HARNESS_OK: native Stages 1–5 used; good candidate passed; "
        "overfit/high-friction/broken/invalid failed closed\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
