"""Stage 4 health adapter — explicit northstar_edge_health API.

Calls ``HealthMonitor.evaluate(evidence, *, identity=...)``. Maps
``research_retire_candidate`` onto the Stage 6 ``research_retire`` label.
"""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.contracts import HealthSnapshot, HealthStateName

_STATE_MAP = {
    "healthy": "healthy",
    "degraded": "degraded",
    "paused": "paused",
    "research_retire_candidate": "research_retire",
    "research_retire": "research_retire",
}


class Stage4HealthAdapter:
    def __init__(self) -> None:
        try:
            from northstar_edge_health import HealthMonitor
            from northstar_edge_health.evidence import MeanReversionEvidence, TrendEvidence
            from northstar_edge_health.schema import StrategyIdentity
            from northstar_edge_health.states import ReasonCode
        except ImportError:
            self.HealthMonitor = None
            self.MeanReversionEvidence = None
            self.TrendEvidence = None
            self.StrategyIdentity = None
            self.ReasonCode = None
            self.source_package = None
        else:
            self.HealthMonitor = HealthMonitor
            self.MeanReversionEvidence = MeanReversionEvidence
            self.TrendEvidence = TrendEvidence
            self.StrategyIdentity = StrategyIdentity
            self.ReasonCode = ReasonCode
            self.source_package = "northstar_edge_health"

    def evaluate(self, evidence: Mapping[str, Any]) -> HealthSnapshot:
        if self.HealthMonitor is None:
            return HealthSnapshot(
                state="paused",
                reason_codes=("health.stage4_unavailable_fail_closed",),
                advisory_risk_multiplier=0.0,
                break_detected=bool(evidence.get("break_detected")),
                source_package=None,
            )

        native_evidence = evidence.get("health_evidence")
        identity = evidence.get("health_identity")
        if native_evidence is None or identity is None:
            return HealthSnapshot(
                state="paused",
                reason_codes=("health.missing_native_evidence_fail_closed",),
                advisory_risk_multiplier=0.0,
                break_detected=bool(evidence.get("break_detected")),
                source_package=self.source_package,
            )

        config = evidence.get("health_config")
        monitor = self.HealthMonitor(config) if config is not None else self.HealthMonitor()
        snapshot = monitor.evaluate(
            native_evidence,
            identity=identity,
            history=tuple(evidence.get("health_history") or ()),
            as_of=evidence.get("as_of"),
        )
        raw_state = snapshot.state.value if hasattr(snapshot.state, "value") else str(snapshot.state)
        mapped: HealthStateName = _STATE_MAP.get(raw_state, "paused")  # type: ignore[assignment]
        codes = tuple(
            item.value if hasattr(item, "value") else str(item) for item in snapshot.reason_codes
        )
        break_token = (
            self.ReasonCode.MR_STRUCTURAL_BREAK
            if self.ReasonCode is not None
            else "mr.structural_break"
        )
        break_value = break_token.value if hasattr(break_token, "value") else str(break_token)
        break_detected = break_value in codes or bool(
            getattr(native_evidence, "structural_break_detected", False)
        )
        if mapped == "healthy" and break_detected:
            mapped = "paused"
            codes = tuple(dict.fromkeys((*codes, "health.break_overrides_healthy")))
        details = snapshot.to_dict() if hasattr(snapshot, "to_dict") else {}
        details["mutates_positions"] = False
        details["may_create_order"] = False
        return HealthSnapshot(
            state=mapped,
            reason_codes=codes or ("health.ok",),
            advisory_risk_multiplier=float(snapshot.recommended_risk_multiplier),
            break_detected=break_detected,
            source_package=self.source_package,
            family=getattr(getattr(snapshot, "identity", None), "strategy_family", None),
            details=details,
        )

    def assert_advisory_only(self, snapshot: HealthSnapshot) -> None:
        if snapshot.details.get("mutates_positions"):
            raise AssertionError("Health snapshot must not mutate positions")
