"""Deterministic Stage 4 health monitor (research/shadow only)."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from northstar_edge_health.advisory import multiplier_for_state
from northstar_edge_health.config import HealthConfig
from northstar_edge_health.evidence import Evidence, MeanReversionEvidence, TrendEvidence
from northstar_edge_health.hysteresis import apply_hysteresis
from northstar_edge_health.schema import (
    SCHEMA_VERSION,
    HealthSnapshot,
    HysteresisState,
    ReasonDetail,
    StrategyIdentity,
    make_snapshot_id,
    utcnow,
)
from northstar_edge_health.scoring import InstantaneousAssessment, score_evidence
from northstar_edge_health.states import HealthState, ReasonCode


class HealthMonitor:
    """Evaluate strategy-family health from point-in-time evidence.

    The monitor never places an order, never mutates positions, and never
    bypasses a RiskGovernor. Output is a persistable advisory snapshot.
    """

    def __init__(self, config: HealthConfig | None = None) -> None:
        self.config = config or HealthConfig()

    def evaluate(
        self,
        evidence: Evidence,
        *,
        identity: StrategyIdentity,
        history: Sequence[HealthSnapshot] = (),
        as_of: datetime | None = None,
        computed_at: datetime | None = None,
    ) -> HealthSnapshot:
        cutoff = as_of or evidence.as_of
        extra: list[ReasonDetail] = []
        fail_closed = False

        if evidence.as_of > cutoff:
            extra.append(
                ReasonDetail(
                    code=ReasonCode.FUTURE_OBSERVATION,
                    state=HealthState.PAUSED,
                    message="Evidence as_of is after the evaluation cutoff; fail closed",
                    hard=True,
                    metric="as_of",
                )
            )
            fail_closed = True

        prior = tuple(item for item in history if item.as_of <= cutoff and item.as_of < evidence.as_of)
        if any(item.as_of > cutoff for item in history):
            # Presence of future snapshots is ignored (point-in-time), not an error.
            pass
        if prior and any(prior[i].as_of > prior[i + 1].as_of for i in range(len(prior) - 1)):
            extra.append(
                ReasonDetail(
                    code=ReasonCode.NON_MONOTONIC_HISTORY,
                    state=HealthState.PAUSED,
                    message="Point-in-time history is not monotonic in as_of; fail closed",
                    hard=True,
                )
            )
            fail_closed = True
        if prior and evidence.as_of <= prior[-1].as_of:
            extra.append(
                ReasonDetail(
                    code=ReasonCode.NON_MONOTONIC_HISTORY,
                    state=HealthState.PAUSED,
                    message="Evidence as_of does not move strictly forward; fail closed",
                    hard=True,
                )
            )
            fail_closed = True

        if fail_closed:
            assessment = InstantaneousAssessment(
                state=HealthState.PAUSED,
                findings=tuple(extra),
                hard_pause=True,
                hard_retire=False,
                fail_closed=True,
                missing_fields=(),
                invalid_fields=(),
            )
        else:
            assessment = score_evidence(evidence, self.config)
            if extra:
                assessment = InstantaneousAssessment(
                    state=assessment.state,
                    findings=tuple(extra) + assessment.findings,
                    hard_pause=assessment.hard_pause,
                    hard_retire=assessment.hard_retire,
                    fail_closed=assessment.fail_closed,
                    missing_fields=assessment.missing_fields,
                    invalid_fields=assessment.invalid_fields,
                )

        previous = prior[-1] if prior else None
        family_code = (
            ReasonCode.MR_CHRONIC_PAUSE
            if isinstance(evidence, MeanReversionEvidence)
            else ReasonCode.TREND_CHRONIC_PAUSE
        )
        decision = apply_hysteresis(
            previous_state=None if previous is None else previous.state,
            previous_hysteresis=None if previous is None else previous.hysteresis,
            assessment=assessment,
            config=self.config.hysteresis,
            family_chronic_code=family_code,
        )
        details = assessment.findings + decision.extra_findings
        reason_codes = tuple(dict.fromkeys(item.code for item in details))
        multiplier = multiplier_for_state(decision.state, self.config.advisory)
        stamp = computed_at or utcnow()
        notes = (
            "Research/shadow health snapshot only.",
            "Recommended risk multiplier is advisory and subordinate to the RiskGovernor.",
            "This snapshot cannot create an order or mutate positions.",
        )
        return HealthSnapshot(
            schema_version=self.config.schema_version or SCHEMA_VERSION,
            snapshot_id=make_snapshot_id(
                identity=identity,
                as_of=evidence.as_of,
                state=decision.state,
                instantaneous_state=assessment.state,
                reason_codes=reason_codes,
                multiplier=multiplier,
            ),
            identity=identity,
            as_of=evidence.as_of,
            computed_at=stamp,
            state=decision.state,
            instantaneous_state=assessment.state,
            previous_state=None if previous is None else previous.state,
            reason_codes=reason_codes,
            reason_details=details,
            recommended_risk_multiplier=multiplier,
            hysteresis=decision.hysteresis,
            evidence_digest=evidence.to_digest(),
            fail_closed=assessment.fail_closed,
            notes=notes,
        )

    def evaluate_sequence(
        self,
        evidence_rows: Sequence[Evidence],
        *,
        identity: StrategyIdentity,
        as_of: datetime | None = None,
        computed_at: datetime | None = None,
    ) -> tuple[HealthSnapshot, ...]:
        """Fold evidence in as_of order, ignoring anything after ``as_of``."""

        if not evidence_rows:
            return ()
        rows = tuple(evidence_rows)
        if any(rows[i].as_of > rows[i + 1].as_of for i in range(len(rows) - 1)):
            return (
                self._non_monotonic_sequence_snapshot(
                    rows[0], identity=identity, computed_at=computed_at
                ),
            )
        cutoff = as_of
        selected = rows if cutoff is None else tuple(item for item in rows if item.as_of <= cutoff)
        snapshots: list[HealthSnapshot] = []
        for item in selected:
            snapshots.append(
                self.evaluate(
                    item,
                    identity=identity,
                    history=tuple(snapshots),
                    as_of=cutoff,
                    computed_at=computed_at,
                )
            )
        return tuple(snapshots)

    def _non_monotonic_sequence_snapshot(
        self,
        evidence: Evidence,
        *,
        identity: StrategyIdentity,
        computed_at: datetime | None,
    ) -> HealthSnapshot:
        details = (
            ReasonDetail(
                code=ReasonCode.NON_MONOTONIC_HISTORY,
                state=HealthState.PAUSED,
                message="Evidence sequence is not point-in-time ordered; fail closed",
                hard=True,
            ),
        )
        multiplier = multiplier_for_state(HealthState.PAUSED, self.config.advisory)
        return HealthSnapshot(
            schema_version=self.config.schema_version,
            snapshot_id=make_snapshot_id(
                identity=identity,
                as_of=evidence.as_of,
                state=HealthState.PAUSED,
                instantaneous_state=HealthState.PAUSED,
                reason_codes=(ReasonCode.NON_MONOTONIC_HISTORY,),
                multiplier=multiplier,
            ),
            identity=identity,
            as_of=evidence.as_of,
            computed_at=computed_at or utcnow(),
            state=HealthState.PAUSED,
            instantaneous_state=HealthState.PAUSED,
            previous_state=None,
            reason_codes=(ReasonCode.NON_MONOTONIC_HISTORY,),
            reason_details=details,
            recommended_risk_multiplier=multiplier,
            hysteresis=HysteresisState(
                consecutive_instantaneous=1,
                last_instantaneous=HealthState.PAUSED,
                consecutive_healthy_instantaneous=0,
                consecutive_pause_emitted=1,
                cooldown_remaining=self.config.hysteresis.cooldown_observations,
                held=False,
            ),
            evidence_digest=evidence.to_digest(),
            fail_closed=True,
            notes=("Evidence sequence was not monotonic in as_of.",),
        )


def family_identity(
    evidence: Evidence,
    *,
    strategy_id: str,
    instrument_id: str,
    horizon: str | None = None,
) -> StrategyIdentity:
    family = "mean_reversion" if isinstance(evidence, MeanReversionEvidence) else "trend"
    return StrategyIdentity(
        strategy_family=family,
        strategy_id=strategy_id,
        instrument_id=instrument_id,
        horizon=horizon,
    )
