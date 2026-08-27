"""Deterministic evaluation pipeline.

Order: diagnostics -> eligibility -> after-friction -> robustness/promotion
-> health -> conservative sizing recommendation -> state transition.

Every run is recorded, including failures. The pipeline cannot place a trade,
bypass risk, or promote to live.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from uuid import uuid4

from northstar_research_loop.adapters import (
    Stage1DiagnosticsAdapter,
    Stage2EligibilityAdapter,
    Stage3TrendCarryAdapter,
    Stage4HealthAdapter,
    Stage5RobustnessAdapter,
    Stage5SizingAdapter,
    discover_all,
    require_native_stages,
)
from northstar_research_loop.contracts import (
    DiagnosticBundle,
    EligibilityDecision,
    GateResult,
    HealthSnapshot,
    RobustnessDecision,
    SizingRecommendation,
    TrendCarryContext,
    fail_closed_gate,
)
from northstar_research_loop.edge_contract import EdgeContract, validate_edge_contract
from northstar_research_loop.proposal import ResearchProposal, validate_proposal
from northstar_research_loop.registry import ExperimentRegistry, make_record
from northstar_research_loop.safety import (
    RESEARCH_AGENT_CAPABILITY,
    ForbiddenActionError,
    assert_action_allowed,
)
from northstar_research_loop.state_machine import (
    CandidateStatus,
    decide_status,
    transition,
)


@dataclass(frozen=True)
class PipelineResult:
    experiment_id: str
    status: CandidateStatus
    reason_codes: tuple[str, ...]
    gates: tuple[GateResult, ...]
    diagnostics: DiagnosticBundle | None
    eligibility: EligibilityDecision | None
    trend: TrendCarryContext | None
    after_friction: GateResult
    robustness: RobustnessDecision | None
    health: HealthSnapshot | None
    sizing: SizingRecommendation | None
    discovered: Mapping[int, Mapping[str, object]]
    recorded: bool
    capability: Mapping[str, bool] = field(default_factory=lambda: RESEARCH_AGENT_CAPABILITY.as_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "gates": [g.to_dict() for g in self.gates],
            "diagnostics": None if self.diagnostics is None else self.diagnostics.to_dict(),
            "eligibility": None if self.eligibility is None else self.eligibility.to_dict(),
            "trend": None if self.trend is None else self.trend.to_dict(),
            "after_friction": self.after_friction.to_dict(),
            "robustness": None if self.robustness is None else self.robustness.to_dict(),
            "health": None if self.health is None else self.health.to_dict(),
            "sizing": None if self.sizing is None else self.sizing.to_dict(),
            "discovered": {str(k): dict(v) for k, v in self.discovered.items()},
            "recorded": self.recorded,
            "capability": dict(self.capability),
            "places_trade": False,
            "promotes_to_live": False,
        }


class ResearchLoopPipeline:
    def __init__(
        self,
        *,
        registry: ExperimentRegistry | None = None,
        fragile_below: float = 2.5,
        require_cost_stress: bool = True,
        require_native: bool = False,
    ) -> None:
        self.registry = registry if registry is not None else ExperimentRegistry()
        self.fragile_below = fragile_below
        self.require_cost_stress = require_cost_stress
        self.require_native = require_native
        self.stage1 = Stage1DiagnosticsAdapter()
        self.stage2 = Stage2EligibilityAdapter()
        self.stage3 = Stage3TrendCarryAdapter()
        self.stage4 = Stage4HealthAdapter()
        self.stage5_rob = Stage5RobustnessAdapter()
        self.stage5_size = Stage5SizingAdapter()

    def evaluate(
        self,
        *,
        contract: EdgeContract,
        proposal: ResearchProposal,
        evidence: Mapping[str, Any],
        experiment_id: str | None = None,
        currently: CandidateStatus = CandidateStatus.PROPOSED,
    ) -> PipelineResult:
        experiment_id = experiment_id or str(uuid4())
        if self.require_native:
            require_native_stages()
        gates: list[GateResult] = []
        discovered = {k: v.to_dict() for k, v in discover_all().items()}

        contract_reasons = validate_edge_contract(contract)
        gates.append(
            GateResult(
                gate="edge_contract",
                passed=not contract_reasons,
                reason_codes=contract_reasons or ("edge.ok",),
                source_package="northstar_research_loop",
            )
        )
        proposal_reasons = validate_proposal(proposal)
        gates.append(
            GateResult(
                gate="proposal",
                passed=not proposal_reasons,
                reason_codes=proposal_reasons or ("proposal.ok",),
                source_package="northstar_research_loop",
            )
        )

        safety_passed = True
        try:
            # Explicitly refuse forbidden actions even if a caller stuffed them into evidence.
            for action in evidence.get("requested_actions") or ():
                assert_action_allowed(str(action))
        except ForbiddenActionError as exc:
            safety_passed = False
            gates.append(
                fail_closed_gate("safety", (f"safety.{exc.__class__.__name__}",), details={"error": str(exc)})
            )
        else:
            if RESEARCH_AGENT_CAPABILITY.can_place_trade or RESEARCH_AGENT_CAPABILITY.can_self_promote_to_live:
                safety_passed = False
                gates.append(fail_closed_gate("safety", ("safety.capability_bitmap_compromised",)))
            else:
                gates.append(
                    GateResult(
                        gate="safety",
                        passed=True,
                        reason_codes=("safety.research_only",),
                        details=RESEARCH_AGENT_CAPABILITY.as_dict(),
                    )
                )

        diagnostics = self.stage1.evaluate(evidence)
        diag_pass = (
            diagnostics.usable
            and diagnostics.required_property_present
            and not diagnostics.break_detected
        )
        gates.append(
            GateResult(
                gate="diagnostics",
                passed=diag_pass,
                reason_codes=diagnostics.reason_codes,
                source_package=diagnostics.source_package,
                details=diagnostics.to_dict(),
            )
        )

        eligibility = self.stage2.evaluate(diagnostics, evidence)
        # Oversold z-score cannot rescue failed formation/eligibility.
        elig_pass = bool(eligibility.eligible) and diag_pass
        if eligibility.eligible and not diag_pass:
            eligibility = EligibilityDecision(
                eligible=False,
                family=eligibility.family,
                reason_codes=tuple(
                    dict.fromkeys((*eligibility.reason_codes, "elig.blocked_by_failed_diagnostics"))
                ),
                source_package=eligibility.source_package,
                evidence=eligibility.evidence,
                zscore_after_eligibility=None,
            )
            elig_pass = False
        gates.append(
            GateResult(
                gate="eligibility",
                passed=elig_pass,
                reason_codes=eligibility.reason_codes,
                source_package=eligibility.source_package,
                details=eligibility.to_dict(),
            )
        )

        trend = self.stage3.evaluate({**dict(evidence), "family": contract.strategy_family})
        trend_required = contract.strategy_family in {"trend", "futures_carry", "trend_carry"}
        trend_pass = trend.usable and not trend.chose_single_optimized_horizon
        gates.append(
            GateResult(
                gate="trend_context",
                passed=trend_pass,
                reason_codes=trend.reason_codes,
                source_package=trend.source_package,
                details=trend.to_dict(),
                advisory_only=not trend_required,
            )
        )

        after_friction = self._after_friction_gate(diagnostics, evidence)
        gates.append(after_friction)

        robustness = self.stage5_rob.evaluate(evidence)
        rob_pass = robustness.passed
        gates.append(
            GateResult(
                gate="robustness",
                passed=rob_pass,
                reason_codes=robustness.reason_codes,
                source_package=robustness.source_package,
                details=robustness.to_dict(),
            )
        )

        health_evidence = dict(evidence)
        health_evidence.setdefault("break_detected", diagnostics.break_detected)
        health = self.stage4.evaluate(health_evidence)
        health_pass = health.state in {"healthy", "degraded"} and not health.break_detected
        gates.append(
            GateResult(
                gate="health",
                passed=health_pass,
                reason_codes=health.reason_codes,
                source_package=health.source_package,
                details=health.to_dict(),
                advisory_only=True,
            )
        )

        sizing_evidence = dict(evidence)
        caps = dict(evidence.get("sizing_caps") or {})
        caps["health_advisory_multiplier"] = health.advisory_risk_multiplier
        sizing_evidence["sizing_caps"] = caps
        sizing = self.stage5_size.evaluate(sizing_evidence)
        size_pass = sizing.subordinate_to_risk_governor and sizing.fractional_kelly_ceiling >= 0
        gates.append(
            GateResult(
                gate="sizing",
                passed=size_pass,
                reason_codes=sizing.reason_codes,
                source_package=sizing.source_package,
                details=sizing.to_dict(),
                advisory_only=True,
            )
        )

        structural_ok = not contract_reasons and not proposal_reasons
        next_status, state_reasons = decide_status(
            currently=currently,
            diagnostics_passed=diag_pass and structural_ok,
            eligibility_passed=elig_pass and (trend_pass if trend_required else True),
            after_friction_passed=after_friction.passed,
            robustness_passed=rob_pass,
            health_state=health.state,
            safety_passed=safety_passed,
        )
        moved = transition(currently, next_status, reason_codes=state_reasons)
        all_reasons = tuple(
            dict.fromkeys(
                [
                    *state_reasons,
                    *[code for gate in gates if not gate.passed for code in gate.reason_codes],
                ]
            )
        )
        record = make_record(
            experiment_id=experiment_id,
            proposal_id=proposal.proposal_id,
            edge_contract_id=contract.contract_id,
            status=moved.to_status.value,
            reason_codes=all_reasons,
            gates=[g.to_dict() for g in gates],
            details={
                "identity_key": contract.identity_key(),
                "hypothesis": proposal.hypothesis,
                "transition": moved.to_dict(),
                "discovered": discovered,
            },
        )
        self.registry.record(record)
        return PipelineResult(
            experiment_id=experiment_id,
            status=moved.to_status,
            reason_codes=all_reasons,
            gates=tuple(gates),
            diagnostics=diagnostics,
            eligibility=eligibility,
            trend=trend,
            after_friction=after_friction,
            robustness=robustness,
            health=health,
            sizing=sizing,
            discovered=discovered,
            recorded=True,
        )

    def _after_friction_gate(
        self, diagnostics: DiagnosticBundle, evidence: Mapping[str, Any]
    ) -> GateResult:
        reasons: list[str] = []
        efr = diagnostics.efr
        if efr is None:
            reasons.append("efr.missing")
        elif diagnostics.efr_fragile or efr < self.fragile_below:
            reasons.append("efr.fragile_below_band")
        stress = evidence.get("friction_stress") or {}
        efr_plus_50 = stress.get("efr_plus_50")
        efr_plus_100 = stress.get("efr_plus_100")
        if efr is not None and efr_plus_50 is None:
            efr_plus_50 = efr / 1.5
        if efr is not None and efr_plus_100 is None:
            efr_plus_100 = efr / 2.0
        if self.require_cost_stress:
            if efr_plus_50 is None or float(efr_plus_50) < self.fragile_below:
                reasons.append("efr.plus_50_stress_failed")
            if efr_plus_100 is None or float(efr_plus_100) < self.fragile_below:
                reasons.append("efr.plus_100_stress_failed")
        passed = not reasons and efr is not None
        if passed:
            reasons.append("efr.ok")
        return GateResult(
            gate="after_friction",
            passed=passed,
            reason_codes=tuple(reasons),
            source_package=diagnostics.source_package,
            details={
                "efr": efr,
                "fragile_below": self.fragile_below,
                "efr_plus_50": efr_plus_50,
                "efr_plus_100": efr_plus_100,
            },
        )
