from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from northstar_research_loop.registry import ExperimentRegistry, make_record
from northstar_research_loop.safety import ForbiddenActionError


def _record(status: str, experiment_id: str) -> object:
    return make_record(
        experiment_id=experiment_id,
        proposal_id="p1",
        edge_contract_id="c1",
        status=status,
        reason_codes=("example",),
        gates=({"gate": "diagnostics", "passed": status == "shadow-ready"},),
        recorded_at=datetime(2026, 8, 27, tzinfo=timezone.utc),
    )


def test_winners_and_failures_are_both_retained(tmp_path: Path):
    registry = ExperimentRegistry()
    registry.record(_record("shadow-ready", "win-1"))
    registry.record(_record("rejected", "fail-1"))
    registry.record(_record("paused", "fail-2"))
    assert len(registry) == 3
    assert len(registry.winners()) == 1
    assert len(registry.failures()) == 2
    path = tmp_path / "experiments.jsonl"
    registry.dump_jsonl(path)
    loaded = ExperimentRegistry.load_jsonl(path)
    assert len(loaded) == 3
    assert {r.experiment_id for r in loaded.failures()} == {"fail-1", "fail-2"}
    with pytest.raises(ForbiddenActionError):
        loaded.hide("fail-1")
    with pytest.raises(ForbiddenActionError):
        loaded.delete("fail-1")
    assert len(loaded) == 3
