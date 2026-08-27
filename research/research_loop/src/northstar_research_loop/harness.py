"""Integrated synthetic end-to-end harness for morning review.

Proves a good candidate can pass while overfit, high-friction, structurally
broken, and statistically invalid candidates fail. Research/paper only.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from northstar_research_loop.adapters.discovery import discover_all
from northstar_research_loop.contracts import (
    EligibilityDecision,
    HealthSnapshot,
    RobustnessDecision,
    SizingRecommendation,
)
from northstar_research_loop.edge_contract import default_mean_reversion_contract
from northstar_research_loop.pipeline import PipelineResult, ResearchLoopPipeline
from northstar_research_loop.proposal import make_proposal
from northstar_research_loop.registry import ExperimentRegistry
from northstar_research_loop.state_machine import CandidateStatus

PASSING_STATUSES = {CandidateStatus.SHADOW_READY, CandidateStatus.RESEARCH_QUALIFIED}


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    expect_status: CandidateStatus
    evidence_builder: Callable[[], Mapping[str, Any]]
    notes: str


def _good_robustness() -> RobustnessDecision:
    return RobustnessDecision(
        passed=True,
        reason_codes=("rob.ok",),
        trial_count=8,
        plateau_stable=True,
        holdout_contaminated=False,
        cost_stress_failed=False,
        delay_stress_failed=False,
        concentration_flag=False,
        deflated_sharpe=0.9,
        pbo=0.18,
        details={"concentration_veto": False},
    )


def _good_health() -> HealthSnapshot:
    return HealthSnapshot(
        state="healthy",
        reason_codes=("health.ok",),
        advisory_risk_multiplier=1.0,
        break_detected=False,
        family="mean_reversion",
    )


def _good_sizing() -> SizingRecommendation:
    return SizingRecommendation(
        fractional_kelly_ceiling=0.12,
        applied_caps={
            "hard_risk_cap": 0.15,
            "vol_target_cap": 0.20,
            "drawdown_cap": 0.10,
            "exposure_cap": 0.25,
            "liquidity_cap": 0.20,
        },
        reason_codes=("size.ok",),
        subordinate_to_risk_governor=True,
    )


def _good_eligibility() -> EligibilityDecision:
    return EligibilityDecision(
        eligible=True,
        family="mean_reversion",
        reason_codes=("elig.ok",),
        source_package="explicit_evidence",
        evidence={"note": "Formation gates passed; z-score is not used as eligibility."},
        zscore_after_eligibility=2.1,
    )


def _try_stage1_pair(kind: str) -> Mapping[str, Any]:
    """Use Stage 1 native diagnostics when installed; otherwise explicit bundle."""

    try:
        import numpy as np
        from northstar_diagnostics import FrictionInputs
        from northstar_diagnostics.efr import edge_to_friction_ratio

        # Match Stage 1 unit-test fixtures so CADF accept/reject is deterministic.
        n = 500
        rng = np.random.default_rng(11)
        x = np.cumsum(rng.normal(0.0, 1.0, size=n))
        if kind == "invalid":
            rng_i = np.random.default_rng(12)
            y = np.cumsum(rng_i.normal(0.0, 1.0, size=400))
            x = np.cumsum(np.random.default_rng(19).normal(0.0, 1.0, size=400))
            edge, friction = 0.02, FrictionInputs(commission=0.0005, spread=0.001, slippage=0.0005)
        else:
            resid = np.zeros(n)
            e = np.random.default_rng(12).normal(0.0, 0.2, size=n)
            for t in range(1, n):
                resid[t] = 0.2 * resid[t - 1] + e[t]
            y = 2.0 * x + resid
            if kind == "high_friction":
                edge, friction = 0.004, FrictionInputs(commission=0.002, spread=0.003, slippage=0.002)
            else:
                edge, friction = 0.02, FrictionInputs(commission=0.0005, spread=0.001, slippage=0.0005)
            if kind == "broken":
                y = y.copy()
                y[n // 2 :] += 8.0
        payload: dict[str, Any] = {
            "y": y,
            "x": x,
            "expected_gross_edge": edge,
            "friction": friction.as_dict(),
        }
        payload["precomputed_efr"] = edge_to_friction_ratio(edge, friction)
        return payload
    except Exception:
        from northstar_research_loop.contracts import DiagnosticBundle

        if kind == "good":
            bundle = DiagnosticBundle(
                usable=True,
                required_property_present=True,
                reason_codes=("diag.ok",),
                diagnostic_ids=("cadf", "adf", "half_life", "efr"),
                efr=5.0,
                efr_fragile=False,
                break_detected=False,
                statistics={"efr": {"efr": 5.0}, "cadf": {"pvalue": 0.001}},
                source_package="synthetic_fail_closed",
            )
        elif kind == "invalid":
            bundle = DiagnosticBundle(
                usable=True,
                required_property_present=False,
                reason_codes=("diag.required_property_absent",),
                diagnostic_ids=("cadf", "adf", "efr"),
                efr=5.0,
                efr_fragile=False,
                break_detected=False,
                statistics={"cadf": {"pvalue": 0.8}},
                source_package="synthetic_fail_closed",
            )
        elif kind == "high_friction":
            bundle = DiagnosticBundle(
                usable=True,
                required_property_present=True,
                reason_codes=("diag.efr_fragile",),
                diagnostic_ids=("cadf", "efr"),
                efr=1.1,
                efr_fragile=True,
                break_detected=False,
                statistics={"efr": {"efr": 1.1}},
                source_package="synthetic_fail_closed",
            )
        else:
            bundle = DiagnosticBundle(
                usable=True,
                required_property_present=True,
                reason_codes=("diag.structural_break",),
                diagnostic_ids=("cadf", "efr", "chow_ols"),
                efr=5.0,
                efr_fragile=False,
                break_detected=True,
                statistics={"efr": {"efr": 5.0}},
                source_package="synthetic_fail_closed",
            )
        return {"diagnostic_bundle": bundle}


def good_candidate_evidence() -> Mapping[str, Any]:
    series = dict(_try_stage1_pair("good"))
    series.pop("diagnostic_results", None)
    return {
        **series,
        "eligibility": _good_eligibility(),
        "robustness": _good_robustness(),
        "health": _good_health(),
        "sizing": _good_sizing(),
        "friction_stress": {"efr_plus_50": 3.3, "efr_plus_100": 2.6},
    }


def overfit_candidate_evidence() -> Mapping[str, Any]:
    base = dict(good_candidate_evidence())
    base["robustness"] = RobustnessDecision(
        passed=True,  # looks attractive until adapter/pipeline apply overfit vetoes
        reason_codes=("rob.in_sample_peak",),
        trial_count=240,
        plateau_stable=False,
        holdout_contaminated=True,
        cost_stress_failed=False,
        delay_stress_failed=False,
        concentration_flag=True,
        deflated_sharpe=-0.4,
        pbo=0.86,
        details={"concentration_veto": True, "isolated_sharp_optimum": True},
    )
    return base


def high_friction_candidate_evidence() -> Mapping[str, Any]:
    series = dict(_try_stage1_pair("high_friction"))
    series.pop("diagnostic_results", None)
    return {
        **series,
        "eligibility": _good_eligibility(),
        "robustness": _good_robustness(),
        "health": _good_health(),
        "sizing": _good_sizing(),
        "friction_stress": {"efr_plus_50": 0.7, "efr_plus_100": 0.5},
    }


def structurally_broken_candidate_evidence() -> Mapping[str, Any]:
    series = dict(_try_stage1_pair("broken"))
    series.pop("diagnostic_results", None)
    series["break_detected"] = True
    return {
        **series,
        "eligibility": _good_eligibility(),
        "robustness": _good_robustness(),
        "health": HealthSnapshot(
            state="paused",
            reason_codes=("health.structural_break",),
            advisory_risk_multiplier=0.0,
            break_detected=True,
            family="mean_reversion",
        ),
        "sizing": _good_sizing(),
        "friction_stress": {"efr_plus_50": 3.3, "efr_plus_100": 2.6},
    }


def statistically_invalid_candidate_evidence() -> Mapping[str, Any]:
    series = dict(_try_stage1_pair("invalid"))
    series.pop("diagnostic_results", None)
    return {
        **series,
        "eligibility": EligibilityDecision(
            eligible=True,  # oversold-but-invalid must still fail diagnostics/eligibility gates
            family="mean_reversion",
            reason_codes=("elig.would_trade_zscore_alone",),
            zscore_after_eligibility=-3.4,
        ),
        "robustness": _good_robustness(),
        "health": _good_health(),
        "sizing": _good_sizing(),
        "friction_stress": {"efr_plus_50": 3.3, "efr_plus_100": 2.6},
    }


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec("good_candidate", CandidateStatus.SHADOW_READY, good_candidate_evidence, "Cointegrated residual, EFR cushion, plateau, healthy."),
    ScenarioSpec("overfit_candidate", CandidateStatus.REJECTED, overfit_candidate_evidence, "Isolated peak, high PBO, holdout contamination."),
    ScenarioSpec("high_friction_candidate", CandidateStatus.REJECTED, high_friction_candidate_evidence, "EFR below research band and cost-stress fail."),
    ScenarioSpec("structurally_broken_candidate", CandidateStatus.PAUSED, structurally_broken_candidate_evidence, "Structural break pauses new risk."),
    ScenarioSpec("statistically_invalid_candidate", CandidateStatus.REJECTED, statistically_invalid_candidate_evidence, "Independent walks / missing required property."),
)


@dataclass(frozen=True)
class ScenarioOutcome:
    name: str
    expected: str
    actual: str
    passed: bool
    reason_codes: tuple[str, ...]
    notes: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "reason_codes": list(self.reason_codes),
            "notes": self.notes,
        }


@dataclass(frozen=True)
class HarnessReport:
    all_passed: bool
    outcomes: tuple[ScenarioOutcome, ...]
    retained_failures: int
    retained_winners: int
    discovered: Mapping[int, Mapping[str, object]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "all_passed": self.all_passed,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "retained_failures": self.retained_failures,
            "retained_winners": self.retained_winners,
            "discovered": {str(k): dict(v) for k, v in self.discovered.items()},
            "places_trade": False,
            "promotes_to_live": False,
        }


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
        evidence=spec.evidence_builder(),
        experiment_id=f"harness.{spec.name}",
    )
    # Structurally broken may be rejected if diagnostics fail-closed on break;
    # both paused (health) and rejected (diagnostics break) are acceptable
    # fail-closed outcomes for that scenario.
    actual = result.status
    expected = spec.expect_status
    if spec.name == "structurally_broken_candidate":
        ok = actual in {CandidateStatus.PAUSED, CandidateStatus.REJECTED, CandidateStatus.RETIRED}
    elif spec.name == "good_candidate":
        ok = actual in PASSING_STATUSES
    else:
        ok = actual == expected and actual not in PASSING_STATUSES
    return (
        ScenarioOutcome(
            name=spec.name,
            expected=expected.value,
            actual=actual.value,
            passed=ok,
            reason_codes=result.reason_codes,
            notes=spec.notes,
        ),
        result,
    )


def run_synthetic_battery(registry: ExperimentRegistry | None = None) -> HarnessReport:
    pipeline = ResearchLoopPipeline(registry=registry if registry is not None else ExperimentRegistry())
    outcomes: list[ScenarioOutcome] = []
    for spec in SCENARIOS:
        outcome, _ = run_scenario(spec, pipeline)
        outcomes.append(outcome)
    report = HarnessReport(
        all_passed=all(item.passed for item in outcomes),
        outcomes=tuple(outcomes),
        retained_failures=len(pipeline.registry.failures()),
        retained_winners=len(pipeline.registry.winners()),
        discovered={k: v.to_dict() for k, v in discover_all().items()},
    )
    return report


def main(argv: list[str] | None = None) -> int:
    _ = argv
    report = run_synthetic_battery()
    json.dump(report.to_dict(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    if not report.all_passed:
        sys.stderr.write("CHAN_HARNESS_FAIL: one or more synthetic scenarios missed expected status\n")
        return 1
    sys.stderr.write("CHAN_HARNESS_OK: good candidate passed; overfit/high-friction/broken/invalid failed closed\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
