"""Advisory risk-multiplier recommendations.

Health may recommend a bounded multiplier. It cannot:
- create an order
- mutate positions
- bypass or loosen a RiskGovernor bound
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableSequence, Protocol, Sequence

from northstar_edge_health.config import AdvisoryRiskConfig
from northstar_edge_health.schema import HealthSnapshot
from northstar_edge_health.states import HealthState


class RiskGovernorPort(Protocol):
    """Narrow port for a hard risk control.

    Stage 4 never implements a production RiskGovernor. Callers may pass any
    object that exposes ``authorize_multiplier``. Health cannot skip this call
    or raise the authorized value.
    """

    def authorize_multiplier(
        self, requested_multiplier: float, *, context: Mapping[str, Any]
    ) -> float: ...


@dataclass(frozen=True)
class AdvisoryRiskRecommendation:
    schema_version: str
    health_state: HealthState
    health_recommended_multiplier: float
    authorized_multiplier: float
    governor_applied: bool
    may_create_order: bool = field(default=False, init=False)
    may_mutate_positions: bool = field(default=False, init=False)
    bypasses_risk_governor: bool = field(default=False, init=False)
    subordinate_to_risk_governor: bool = field(default=True, init=False)
    positions_mutated: bool = field(default=False, init=False)
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "health_state": self.health_state.value,
            "health_recommended_multiplier": self.health_recommended_multiplier,
            "authorized_multiplier": self.authorized_multiplier,
            "governor_applied": self.governor_applied,
            "may_create_order": False,
            "may_mutate_positions": False,
            "bypasses_risk_governor": False,
            "subordinate_to_risk_governor": True,
            "positions_mutated": False,
            "notes": list(self.notes),
        }


def multiplier_for_state(state: HealthState, config: AdvisoryRiskConfig) -> float:
    mapping = {
        HealthState.HEALTHY: config.healthy_multiplier,
        HealthState.DEGRADED: config.degraded_multiplier,
        HealthState.PAUSED: config.paused_multiplier,
        HealthState.RESEARCH_RETIRE_CANDIDATE: config.retire_multiplier,
    }
    value = mapping[state]
    return max(0.0, min(1.0, float(value)))


class NullRiskGovernor:
    """Passthrough governor used only when no governor is supplied.

    This is not a production RiskGovernor. It still refuses to raise a
    multiplier above 1.0 and records that health did not bypass hard controls
    because none were provided.
    """

    def authorize_multiplier(self, requested_multiplier: float, *, context: Mapping[str, Any]) -> float:
        _ = context
        return max(0.0, min(1.0, float(requested_multiplier)))


def apply_advisory(
    snapshot: HealthSnapshot,
    *,
    positions: Sequence[Any] | MutableSequence[Any] | None = None,
    governor: RiskGovernorPort | None = None,
) -> AdvisoryRiskRecommendation:
    """Translate a health snapshot into an advisory multiplier.

    ``positions`` is accepted only so tests can prove it is never mutated.
    This function does not read position size to change it, does not place
    orders, and cannot bypass ``governor``.
    """

    _ = positions  # explicitly unused; mutation is forbidden
    requested = snapshot.recommended_risk_multiplier
    context = {
        "snapshot_id": snapshot.snapshot_id,
        "as_of": snapshot.as_of.isoformat(),
        "state": snapshot.state.value,
        "may_create_order": False,
        "may_mutate_positions": False,
    }
    used_governor = governor is not None
    port: RiskGovernorPort = governor if governor is not None else NullRiskGovernor()
    authorized = port.authorize_multiplier(requested, context=context)
    if authorized != authorized or authorized in (float("inf"), float("-inf")):
        authorized = 0.0
    # Health cannot loosen the governor: authorized may only be <= requested.
    if authorized > requested:
        authorized = requested
    authorized = max(0.0, min(1.0, float(authorized)))
    notes = (
        "Advisory only: health never creates an order.",
        "Advisory only: health never mutates positions.",
        "Authorized multiplier is min(health recommendation, governor authorization).",
        "A missing RiskGovernor is not permission to trade; it is a research passthrough.",
    )
    return AdvisoryRiskRecommendation(
        schema_version=snapshot.schema_version,
        health_state=snapshot.state,
        health_recommended_multiplier=requested,
        authorized_multiplier=authorized,
        governor_applied=used_governor,
        notes=notes,
    )
