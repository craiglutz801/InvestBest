"""Failed-experiment retention. Winners and failures both remain auditable."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Sequence

from northstar_research_loop.safety import ForbiddenAction, ForbiddenActionError


@dataclass(frozen=True)
class ExperimentRecord:
    experiment_id: str
    proposal_id: str
    edge_contract_id: str
    status: str
    outcome: str  # winner | failure | in_progress
    reason_codes: tuple[str, ...]
    gates: tuple[Mapping[str, Any], ...]
    recorded_at: datetime
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "proposal_id": self.proposal_id,
            "edge_contract_id": self.edge_contract_id,
            "status": self.status,
            "outcome": self.outcome,
            "reason_codes": list(self.reason_codes),
            "gates": [dict(g) for g in self.gates],
            "recorded_at": self.recorded_at.isoformat(),
            "details": dict(self.details),
            "retained": True,
        }


class ExperimentRegistry:
    """Append-only registry. Delete/hide is a forbidden action."""

    def __init__(self) -> None:
        self._records: list[ExperimentRecord] = []

    def record(self, item: ExperimentRecord) -> ExperimentRecord:
        self._records.append(item)
        return item

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[ExperimentRecord]:
        return iter(self._records)

    def all(self) -> tuple[ExperimentRecord, ...]:
        return tuple(self._records)

    def by_status(self, status: str) -> tuple[ExperimentRecord, ...]:
        return tuple(r for r in self._records if r.status == status)

    def failures(self) -> tuple[ExperimentRecord, ...]:
        return tuple(r for r in self._records if r.outcome == "failure")

    def winners(self) -> tuple[ExperimentRecord, ...]:
        return tuple(r for r in self._records if r.outcome == "winner")

    def hide(self, experiment_id: str) -> None:  # noqa: ARG002
        raise ForbiddenActionError(
            f"{ForbiddenAction.HIDE_FAILED_EXPERIMENT.value} is forbidden; "
            "winners and failures must both remain auditable."
        )

    def delete(self, experiment_id: str) -> None:  # noqa: ARG002
        self.hide(experiment_id)

    def dump_jsonl(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for record in self._records:
                handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
        return path

    @classmethod
    def load_jsonl(cls, path: Path) -> "ExperimentRegistry":
        registry = cls()
        if not path.exists():
            return registry
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            registry.record(
                ExperimentRecord(
                    experiment_id=payload["experiment_id"],
                    proposal_id=payload["proposal_id"],
                    edge_contract_id=payload["edge_contract_id"],
                    status=payload["status"],
                    outcome=payload["outcome"],
                    reason_codes=tuple(payload.get("reason_codes") or ()),
                    gates=tuple(payload.get("gates") or ()),
                    recorded_at=datetime.fromisoformat(payload["recorded_at"]),
                    details=payload.get("details") or {},
                )
            )
        return registry


def outcome_for_status(status: str) -> str:
    if status == "shadow-ready":
        return "winner"
    if status in {"rejected", "retired", "paused"}:
        return "failure"
    return "in_progress"


def make_record(
    *,
    experiment_id: str,
    proposal_id: str,
    edge_contract_id: str,
    status: str,
    reason_codes: Sequence[str],
    gates: Iterable[Mapping[str, Any]],
    details: Mapping[str, Any] | None = None,
    recorded_at: datetime | None = None,
) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=experiment_id,
        proposal_id=proposal_id,
        edge_contract_id=edge_contract_id,
        status=status,
        outcome=outcome_for_status(status),
        reason_codes=tuple(reason_codes),
        gates=tuple(dict(g) for g in gates),
        recorded_at=recorded_at or datetime.now(timezone.utc),
        details=dict(details or {}),
    )
