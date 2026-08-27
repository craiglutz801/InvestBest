"""NorthstarAlpha Stage 6 bounded research loop.

Research / paper only. This package assembles Edge Contract + proposal
schemas, adapters for Chan Stages 1–5, a deterministic evaluation pipeline,
an auditable experiment registry, and a synthetic morning harness.

It does not place orders, bypass RiskGovernor/paper-safety gates, self-merge,
self-deploy, or self-promote a candidate to live.
"""

from __future__ import annotations

__version__ = "0.1.0"

from northstar_research_loop.contracts import (
    DiagnosticBundle,
    EligibilityDecision,
    GateResult,
    HealthSnapshot,
    RobustnessDecision,
    SizingRecommendation,
    TrendCarryContext,
)
from northstar_research_loop.edge_contract import (
    CHAN_REVIEW_QUESTIONS,
    EDGE_CONTRACT_SCHEMA_VERSION,
    EdgeContract,
    ExpectedCosts,
    HoldingPeriod,
    NamedRule,
    default_mean_reversion_contract,
    validate_edge_contract,
)
from northstar_research_loop.adapters.discovery import (
    NativeStageMissingError,
    require_native_stages,
)
from northstar_research_loop.harness import run_synthetic_battery
from northstar_research_loop.pipeline import PipelineResult, ResearchLoopPipeline
from northstar_research_loop.proposal import ResearchProposal, make_proposal, validate_proposal
from northstar_research_loop.registry import ExperimentRecord, ExperimentRegistry
from northstar_research_loop.safety import (
    ALLOWED_MUTATION_TARGETS,
    RESEARCH_AGENT_CAPABILITY,
    ForbiddenAction,
    ForbiddenActionError,
    assert_action_allowed,
)
from northstar_research_loop.state_machine import CandidateStatus, decide_status, transition

__all__ = [
    "ALLOWED_MUTATION_TARGETS",
    "CHAN_REVIEW_QUESTIONS",
    "CandidateStatus",
    "DiagnosticBundle",
    "EDGE_CONTRACT_SCHEMA_VERSION",
    "EdgeContract",
    "EligibilityDecision",
    "ExperimentRecord",
    "ExperimentRegistry",
    "ExpectedCosts",
    "ForbiddenAction",
    "ForbiddenActionError",
    "GateResult",
    "HealthSnapshot",
    "HoldingPeriod",
    "NamedRule",
    "NativeStageMissingError",
    "PipelineResult",
    "RESEARCH_AGENT_CAPABILITY",
    "ResearchLoopPipeline",
    "ResearchProposal",
    "RobustnessDecision",
    "SizingRecommendation",
    "TrendCarryContext",
    "__version__",
    "assert_action_allowed",
    "decide_status",
    "default_mean_reversion_contract",
    "make_proposal",
    "require_native_stages",
    "run_synthetic_battery",
    "transition",
    "validate_edge_contract",
    "validate_proposal",
]
