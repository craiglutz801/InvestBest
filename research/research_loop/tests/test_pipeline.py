from __future__ import annotations

from northstar_research_loop.edge_contract import default_mean_reversion_contract
from northstar_research_loop.native_evidence import evidence_for
from northstar_research_loop.pipeline import ResearchLoopPipeline
from northstar_research_loop.proposal import make_proposal
from northstar_research_loop.state_machine import CandidateStatus


def _run(kind: str, experiment_id: str):
    pipeline = ResearchLoopPipeline(require_native=True)
    contract = default_mean_reversion_contract()
    proposal = make_proposal(
        hypothesis="pipeline unit",
        mutation_target="thresholds",
        config_delta={"entry_zscore": 2.0},
        baseline_ref="baseline",
        edge_contract_id=contract.contract_id,
    )
    return pipeline.evaluate(
        contract=contract,
        proposal=proposal,
        evidence=evidence_for(kind, experiment_id),  # type: ignore[arg-type]
        experiment_id=experiment_id,
    )


def test_pipeline_records_failures_and_does_not_promote_to_live():
    result = _run("overfit", "pipe.overfit")
    assert result.status == CandidateStatus.REJECTED
    assert result.recorded is True
    assert result.to_dict()["places_trade"] is False
    assert result.to_dict()["promotes_to_live"] is False
    assert result.robustness is not None
    assert result.robustness.source_package == "northstar_promotion"


def test_high_friction_fails_after_friction_gate():
    result = _run("high_friction", "pipe.friction")
    assert result.status == CandidateStatus.REJECTED
    assert result.after_friction.passed is False
    assert any(code.startswith("efr.") for code in result.after_friction.reason_codes)


def test_invalid_stats_cannot_be_rescued_by_zscore_eligibility():
    result = _run("invalid", "pipe.invalid")
    assert result.status == CandidateStatus.REJECTED
    assert result.diagnostics is not None
    assert result.eligibility is not None
    assert result.diagnostics.required_property_present is False or result.eligibility.eligible is False
    elig = next(g for g in result.gates if g.gate == "eligibility")
    assert elig.passed is False
    assert elig.source_package == "northstar_mean_reversion"


def test_good_candidate_reaches_shadow_ready_not_live():
    result = _run("good", "pipe.good")
    assert result.status in {CandidateStatus.SHADOW_READY, CandidateStatus.RESEARCH_QUALIFIED}
    assert result.sizing is not None
    assert result.sizing.subordinate_to_risk_governor is True
    assert result.sizing.fractional_kelly_ceiling < 1.0
    assert result.health is not None
    assert result.health.advisory_risk_multiplier <= 1.0
    assert result.health.source_package == "northstar_edge_health"
    assert result.eligibility.source_package == "northstar_mean_reversion"


def test_structural_break_does_not_stay_healthy():
    result = _run("broken", "pipe.break")
    assert result.status in {
        CandidateStatus.PAUSED,
        CandidateStatus.REJECTED,
        CandidateStatus.RETIRED,
    }
    assert result.status not in {
        CandidateStatus.SHADOW_READY,
        CandidateStatus.RESEARCH_QUALIFIED,
    }
    assert result.health is not None
    assert result.health.source_package == "northstar_edge_health"
    assert result.health.state != "healthy"
