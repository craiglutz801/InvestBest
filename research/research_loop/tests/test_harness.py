from __future__ import annotations

from northstar_research_loop.adapters.discovery import NATIVE_MODULES
from northstar_research_loop.harness import NATIVE_GATES, run_synthetic_battery
from northstar_research_loop.registry import ExperimentRegistry


def test_synthetic_battery_uses_native_stages_and_retains_failures():
    registry = ExperimentRegistry()
    report = run_synthetic_battery(registry, require_native=True)
    assert report.error is None
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
    for stage, name in NATIVE_MODULES.items():
        assert report.discovered[stage]["available"] is True
        assert report.discovered[stage]["adapter_mode"] == "native"
        assert report.discovered[stage]["module_name"] == name
        assert report.discovered[stage]["adapter_mode"] != "synthetic_fail_closed"
    for outcome in report.outcomes:
        for gate, expected in NATIVE_GATES.items():
            assert outcome.native_sources[gate] == expected, (outcome.name, gate, outcome.native_sources)
