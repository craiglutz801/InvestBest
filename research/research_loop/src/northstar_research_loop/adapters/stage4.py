"""Stage 4 health adapter — wrap native health snapshots or explicit evidence."""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.adapters.discovery import native_module
from northstar_research_loop.contracts import HealthSnapshot, HealthStateName

VALID_STATES = {"healthy", "degraded", "paused", "research_retire"}


def _clip_multiplier(value: float) -> float:
    if value != value or value < 0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


class Stage4HealthAdapter:
    def __init__(self) -> None:
        self.module = native_module(4)

    def evaluate(self, evidence: Mapping[str, Any]) -> HealthSnapshot:
        explicit = evidence.get("health")
        native = self.module
        if native is not None:
            for attr in ("evaluate_health", "health_snapshot", "evaluate"):
                fn = getattr(native, attr, None)
                if callable(fn):
                    return self._wrap(fn(evidence), native.__name__)
        if explicit is None:
            if evidence.get("break_detected"):
                return HealthSnapshot(
                    state="paused",
                    reason_codes=("health.structural_break_fail_closed",),
                    advisory_risk_multiplier=0.0,
                    break_detected=True,
                    source_package=None,
                )
            return HealthSnapshot(
                state="paused",
                reason_codes=("health.missing_stage4_fail_closed",),
                advisory_risk_multiplier=0.0,
                break_detected=False,
                source_package=None,
            )
        return self._wrap(explicit, native.__name__ if native else "explicit_evidence")

    @staticmethod
    def _wrap(payload: Any, source: str | None) -> HealthSnapshot:
        if isinstance(payload, HealthSnapshot):
            multiplier = _clip_multiplier(payload.advisory_risk_multiplier)
            if multiplier != payload.advisory_risk_multiplier:
                return HealthSnapshot(
                    state=payload.state,
                    reason_codes=tuple(
                        dict.fromkeys((*payload.reason_codes, "health.multiplier_clipped"))
                    ),
                    advisory_risk_multiplier=multiplier,
                    break_detected=payload.break_detected,
                    source_package=payload.source_package or source,
                    family=payload.family,
                    details=payload.details,
                )
            return payload
        data = dict(payload) if isinstance(payload, Mapping) else {}
        state = str(data.get("state") or "paused")
        if state not in VALID_STATES:
            state = "paused"
            reasons = tuple(
                dict.fromkeys((*(data.get("reason_codes") or ()), "health.invalid_state_fail_closed"))
            )
            multiplier = 0.0
        else:
            reasons = tuple(data.get("reason_codes") or ("health.ok",))
            multiplier = _clip_multiplier(float(data.get("advisory_risk_multiplier", 0.0)))
        break_detected = bool(data.get("break_detected"))
        if break_detected and state == "healthy":
            state = "paused"
            reasons = tuple(dict.fromkeys((*reasons, "health.break_overrides_healthy")))
            multiplier = 0.0
        return HealthSnapshot(
            state=state,  # type: ignore[arg-type]
            reason_codes=reasons,
            advisory_risk_multiplier=multiplier,
            break_detected=break_detected,
            source_package=source,
            family=data.get("family"),
            details=dict(data.get("details") or {}),
        )

    def assert_advisory_only(self, snapshot: HealthSnapshot) -> None:
        """Health never mutates positions; multiplier is subordinate advice."""

        if snapshot.details.get("mutates_positions"):
            raise AssertionError("Health snapshot must not mutate positions")
