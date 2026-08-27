"""Append-only experiment / trial registry.

Stores **failed experiments as well as winners**. Trial count is an explicit
input to multiple-testing metrics (DSR) and to the promotion haircut.

This is an in-memory research ledger with optional JSONL serialization. It is
not a production database and does not activate strategies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag
from northstar_promotion.schema import TimeWindow, isoformat, jsonable, make_meta, utcnow


@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    experiment_id: str
    strategy_family: str
    parameters: Mapping[str, Any]
    window: TimeWindow | None
    metrics: Mapping[str, float | int | None]
    outcome: str
    created_at: datetime
    notes: str = ""
    used_holdout: bool = False
    as_of_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "experiment_id": self.experiment_id,
            "strategy_family": self.strategy_family,
            "parameters": jsonable(self.parameters),
            "window": None if self.window is None else self.window.to_dict(),
            "metrics": jsonable(self.metrics),
            "outcome": self.outcome,
            "created_at": isoformat(self.created_at),
            "notes": self.notes,
            "used_holdout": self.used_holdout,
            "as_of_index": self.as_of_index,
        }


@dataclass
class ExperimentRegistry:
    """Append-only trial ledger. Failures are first-class records."""

    experiments: dict[str, dict[str, Any]] = field(default_factory=dict)
    trials: list[TrialRecord] = field(default_factory=list)
    _ids: set[str] = field(default_factory=set, repr=False)

    def register_experiment(
        self,
        experiment_id: str,
        *,
        strategy_family: str,
        hypothesis: str = "",
        notes: str = "",
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        if not experiment_id:
            raise ValueError("experiment_id is required")
        if experiment_id in self.experiments:
            return self.experiments[experiment_id]
        rec = {
            "experiment_id": experiment_id,
            "strategy_family": strategy_family,
            "hypothesis": hypothesis,
            "notes": notes,
            "created_at": isoformat(created_at or utcnow()),
        }
        self.experiments[experiment_id] = rec
        return rec

    def record_trial(
        self,
        *,
        trial_id: str,
        experiment_id: str,
        strategy_family: str,
        parameters: Mapping[str, Any] | None = None,
        window: TimeWindow | None = None,
        metrics: Mapping[str, float | int | None] | None = None,
        outcome: str,
        notes: str = "",
        used_holdout: bool = False,
        as_of_index: int | None = None,
        created_at: datetime | None = None,
    ) -> tuple[TrialRecord | None, tuple[QualityFlag, ...]]:
        flags: list[QualityFlag] = []
        if not trial_id or not experiment_id:
            flags.append(fail_flag(QualityCode.INVALID_INPUT, "trial_id and experiment_id are required."))
            return None, tuple(flags)
        if trial_id in self._ids:
            flags.append(
                fail_flag(
                    QualityCode.INVALID_INPUT,
                    f"trial_id {trial_id!r} already exists; registry is append-only and will not overwrite.",
                )
            )
            return None, tuple(flags)
        if experiment_id not in self.experiments:
            self.register_experiment(experiment_id, strategy_family=strategy_family)
        rec = TrialRecord(
            trial_id=trial_id,
            experiment_id=experiment_id,
            strategy_family=strategy_family,
            parameters=dict(parameters or {}),
            window=window,
            metrics=dict(metrics or {}),
            outcome=str(outcome),
            created_at=created_at or utcnow(),
            notes=notes,
            used_holdout=bool(used_holdout),
            as_of_index=as_of_index,
        )
        self.trials.append(rec)
        self._ids.add(trial_id)
        return rec, (ok_flag("Trial recorded (including failures)."),)

    def trial_count(self, experiment_id: str | None = None) -> int:
        if experiment_id is None:
            return len(self.trials)
        return sum(1 for t in self.trials if t.experiment_id == experiment_id)

    def trials_for(self, experiment_id: str) -> tuple[TrialRecord, ...]:
        return tuple(t for t in self.trials if t.experiment_id == experiment_id)

    def failed_trials(self, experiment_id: str | None = None) -> tuple[TrialRecord, ...]:
        rows = self.trials if experiment_id is None else self.trials_for(experiment_id)
        return tuple(t for t in rows if t.outcome.lower() in {"fail", "failed", "reject", "rejected", "invalid"})

    def winners_only_forbidden_export(self) -> tuple[TrialRecord, ...]:
        """Always returns the full ledger. Winners-only export is not provided."""
        return tuple(self.trials)

    def to_jsonl(self) -> str:
        lines = []
        for exp in self.experiments.values():
            lines.append(json.dumps({"kind": "experiment", **exp}, sort_keys=True))
        for trial in self.trials:
            lines.append(json.dumps({"kind": "trial", **trial.to_dict()}, sort_keys=True))
        return "\n".join(lines) + ("\n" if lines else "")

    @classmethod
    def from_records(cls, records: Iterable[TrialRecord], experiments: Mapping[str, Mapping[str, Any]] | None = None) -> ExperimentRegistry:
        reg = cls()
        if experiments:
            for k, v in experiments.items():
                reg.experiments[k] = dict(v)
        for rec in records:
            if rec.trial_id in reg._ids:
                continue
            if rec.experiment_id not in reg.experiments:
                reg.register_experiment(rec.experiment_id, strategy_family=rec.strategy_family)
            reg.trials.append(rec)
            reg._ids.add(rec.trial_id)
        return reg


def trial_count_haircut(*, n_trials: int, base_score: float, reference_trials: int = 1) -> float:
    """Simple multiple-testing haircut: score / sqrt(n_trials / reference).

    Used as a transparent confidence reduction alongside DSR. ``n_trials < 1``
    returns NaN (fail-closed).
    """
    if n_trials < 1 or reference_trials < 1 or not np_finite(base_score):
        return float("nan")
    return float(base_score / np_sqrt(n_trials / float(reference_trials)))


def np_finite(x: float) -> bool:
    return x == x and x not in (float("inf"), float("-inf"))


def np_sqrt(x: float) -> float:
    import math

    return math.sqrt(x)


def registry_meta(registry: ExperimentRegistry, experiment_id: str) -> dict[str, Any]:
    meta = make_meta(
        method="append_only_trial_registry",
        parameters={"experiment_id": experiment_id},
        assumptions=(
            "Every recorded trial, including failures, remains in the ledger.",
            "Trial count is the number of distinct trial_id values for the experiment.",
            "The registry does not promote or activate strategies.",
        ),
        quality_flags=(ok_flag("Registry is append-only."),),
        details={
            "trial_count": registry.trial_count(experiment_id),
            "failed_trial_count": len(registry.failed_trials(experiment_id)),
        },
    )
    return meta.to_dict()


def require_positive_trial_count(n_trials: int) -> tuple[QualityFlag, ...]:
    if n_trials < 1:
        return (
            fail_flag(
                QualityCode.INSUFFICIENT_TRIALS,
                "Trial count must be >= 1. Unknown search breadth is treated as fail-closed.",
            ),
        )
    return ()
