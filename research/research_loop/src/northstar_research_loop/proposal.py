"""Bounded research proposal schema.

The agent may propose strategy/config experiments. Proposals that touch
broker safety, execution, RiskGovernor, live promotion, or orders fail closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from northstar_research_loop.safety import (
    ALLOWED_MUTATION_TARGETS,
    FORBIDDEN_MUTATION_KEYS,
    mutation_contains_forbidden_keys,
)

PROPOSAL_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class ResearchProposal:
    proposal_id: str
    hypothesis: str
    mutation_target: str
    config_delta: Mapping[str, Any]
    baseline_ref: str
    edge_contract_id: str
    proposed_by: str
    proposed_at: datetime
    schema_version: str = PROPOSAL_SCHEMA_VERSION
    notes: tuple[str, ...] = ()
    parent_experiment_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "proposal_id": self.proposal_id,
            "hypothesis": self.hypothesis,
            "mutation_target": self.mutation_target,
            "config_delta": dict(self.config_delta),
            "baseline_ref": self.baseline_ref,
            "edge_contract_id": self.edge_contract_id,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at.isoformat(),
            "notes": list(self.notes),
            "parent_experiment_id": self.parent_experiment_id,
        }


def validate_proposal(proposal: ResearchProposal) -> tuple[str, ...]:
    reasons: list[str] = []
    if proposal.schema_version != PROPOSAL_SCHEMA_VERSION:
        reasons.append("proposal.unsupported_schema_version")
    if not proposal.proposal_id.strip():
        reasons.append("proposal.missing_id")
    if not proposal.hypothesis.strip():
        reasons.append("proposal.missing_hypothesis")
    if proposal.mutation_target not in ALLOWED_MUTATION_TARGETS:
        reasons.append("proposal.mutation_target_not_allowed")
    if not proposal.edge_contract_id.strip():
        reasons.append("proposal.missing_edge_contract_id")
    if not proposal.baseline_ref.strip():
        reasons.append("proposal.missing_baseline_ref")
    forbidden = mutation_contains_forbidden_keys(proposal.config_delta)
    if forbidden:
        reasons.append("proposal.forbidden_mutation_keys:" + ",".join(forbidden))
    for key in proposal.config_delta:
        if str(key).strip().lower() in FORBIDDEN_MUTATION_KEYS:
            reasons.append(f"proposal.forbidden_key:{key}")
    return tuple(reasons)


def make_proposal(
    *,
    hypothesis: str,
    mutation_target: str,
    config_delta: Mapping[str, Any],
    baseline_ref: str,
    edge_contract_id: str,
    proposed_by: str = "research_agent",
    notes: tuple[str, ...] = (),
    parent_experiment_id: str | None = None,
    proposal_id: str | None = None,
    proposed_at: datetime | None = None,
) -> ResearchProposal:
    return ResearchProposal(
        proposal_id=proposal_id or str(uuid4()),
        hypothesis=hypothesis,
        mutation_target=mutation_target,
        config_delta=dict(config_delta),
        baseline_ref=baseline_ref,
        edge_contract_id=edge_contract_id,
        proposed_by=proposed_by,
        proposed_at=proposed_at or datetime.now(timezone.utc),
        notes=notes,
        parent_experiment_id=parent_experiment_id,
    )
