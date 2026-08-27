from __future__ import annotations

from northstar_promotion.quality import QualityLevel
from northstar_promotion.registry import ExperimentRegistry, trial_count_haircut
from northstar_promotion.schema import TimeWindow


def test_registry_is_append_only_and_keeps_failures():
    reg = ExperimentRegistry()
    reg.register_experiment("exp-a", strategy_family="toy")
    rec, flags = reg.record_trial(
        trial_id="t1",
        experiment_id="exp-a",
        strategy_family="toy",
        parameters={"lookback": 20},
        metrics={"sharpe": 0.1},
        outcome="fail",
        notes="negative OOS",
    )
    assert rec is not None
    assert all(f.level is not QualityLevel.FAIL for f in flags)
    rec2, flags2 = reg.record_trial(
        trial_id="t2",
        experiment_id="exp-a",
        strategy_family="toy",
        parameters={"lookback": 40},
        metrics={"sharpe": 1.2},
        outcome="pass",
        window=TimeWindow(0, 100, "research"),
    )
    assert rec2 is not None
    assert [f.level for f in flags2]
    assert reg.trial_count("exp-a") == 2
    failed = reg.failed_trials("exp-a")
    assert len(failed) == 1
    assert failed[0].trial_id == "t1"
    full = reg.winners_only_forbidden_export()
    assert {t.trial_id for t in full} == {"t1", "t2"}


def test_duplicate_trial_id_does_not_overwrite():
    reg = ExperimentRegistry()
    reg.record_trial(
        trial_id="t1",
        experiment_id="exp-a",
        strategy_family="toy",
        outcome="fail",
        metrics={"sharpe": 0.0},
    )
    rec, flags = reg.record_trial(
        trial_id="t1",
        experiment_id="exp-a",
        strategy_family="toy",
        outcome="pass",
        metrics={"sharpe": 9.9},
    )
    assert rec is None
    assert any(f.level is QualityLevel.FAIL for f in flags)
    assert reg.trials[0].outcome == "fail"
    assert reg.trials[0].metrics["sharpe"] == 0.0


def test_trial_count_haircut_falls_as_trials_increase():
    base = 1.0
    h1 = trial_count_haircut(n_trials=1, base_score=base)
    h4 = trial_count_haircut(n_trials=4, base_score=base)
    h16 = trial_count_haircut(n_trials=16, base_score=base)
    assert h1 == 1.0
    assert abs(h4 - 0.5) < 1e-12
    assert abs(h16 - 0.25) < 1e-12
    assert h16 < h4 < h1
    assert trial_count_haircut(n_trials=0, base_score=base) != trial_count_haircut(n_trials=0, base_score=base)


def test_jsonl_roundtrip_includes_failures():
    reg = ExperimentRegistry()
    reg.register_experiment("exp-a", strategy_family="toy", hypothesis="mean reversion")
    reg.record_trial(trial_id="fail1", experiment_id="exp-a", strategy_family="toy", outcome="fail")
    blob = reg.to_jsonl()
    assert "fail1" in blob
    assert "mean reversion" in blob
