from __future__ import annotations

from northstar_research_loop.harness import run_synthetic_battery
from northstar_research_loop.registry import ExperimentRegistry


def test_synthetic_battery_good_passes_others_fail_and_all_are_retained():
    registry = ExperimentRegistry()
    report = run_synthetic_battery(registry)
    by_name = {row.name: row for row in report.outcomes}
    assert by_name["good_candidate"].passed
    assert by_name["good_candidate"].actual in {"shadow-ready", "research-qualified"}
    assert by_name["overfit_candidate"].actual == "rejected"
    assert by_name["high_friction_candidate"].actual == "rejected"
    assert by_name["statistically_invalid_candidate"].actual == "rejected"
    assert by_name["structurally_broken_candidate"].actual in {"paused", "rejected", "retired"}
    assert report.all_passed
    assert report.retained_winners >= 1
    assert report.retained_failures >= 3
    assert len(registry) == 5
    assert report.to_dict()["places_trade"] is False
    assert report.to_dict()["promotes_to_live"] is False
    assert report.discovered[1]["available"] is True
