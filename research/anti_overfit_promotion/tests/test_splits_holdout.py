from __future__ import annotations

from northstar_promotion.holdout import audit_holdout, seal_holdout
from northstar_promotion.quality import QualityLevel
from northstar_promotion.registry import ExperimentRegistry
from northstar_promotion.splits import formation_windows, walk_forward_splits


def test_walk_forward_rolling_does_not_enter_holdout():
    contract = seal_holdout(200, holdout_size=40, embargo_bars=5, min_research_bars=20, min_holdout_bars=10)
    assert contract.sealed
    splits, flags = walk_forward_splits(
        200, train_size=40, test_size=10, step=10, embargo=2, holdout=contract, min_folds=3
    )
    assert not any(f.level is QualityLevel.FAIL for f in flags)
    assert splits
    for sp in splits:
        assert sp.test.end_index <= contract.research.end_index
        assert sp.train.end_index <= sp.test.start_index
        if sp.embargo is not None:
            assert sp.embargo.end_index == sp.test.start_index


def test_expanding_walk_forward_grows_train_from_zero():
    splits, flags = walk_forward_splits(80, train_size=20, test_size=10, mode="expanding", step=10)
    assert not any(f.level is QualityLevel.FAIL for f in flags)
    assert splits[0].train.start_index == 0
    assert splits[-1].train.start_index == 0
    assert splits[-1].train.length > splits[0].train.length


def test_formation_windows_are_point_in_time():
    windows, flags = formation_windows(100, lengths=(20, 40, 60), as_of_index=70)
    assert not any(f.level is QualityLevel.FAIL for f in flags)
    assert [w.length for w in windows] == [20, 40, 60]
    assert all(w.end_index == 70 for w in windows)


def test_formation_windows_reject_as_of_in_holdout():
    contract = seal_holdout(100, holdout_size=20, embargo_bars=0, min_research_bars=20, min_holdout_bars=10)
    windows, flags = formation_windows(100, lengths=(20,), as_of_index=contract.holdout.start_index + 1, holdout=contract)
    assert windows == ()
    assert any(f.level is QualityLevel.FAIL for f in flags)


def test_holdout_contamination_is_flagged():
    contract = seal_holdout(100, holdout_size=20, embargo_bars=2, min_research_bars=20, min_holdout_bars=10)
    reg = ExperimentRegistry()
    # Clean trial inside research.
    reg.record_trial(
        trial_id="clean",
        experiment_id="e",
        strategy_family="toy",
        outcome="pass",
        window=contract.research,
        as_of_index=contract.research.end_index,
    )
    # Contaminating trial whose window overlaps holdout.
    reg.record_trial(
        trial_id="dirty",
        experiment_id="e",
        strategy_family="toy",
        outcome="pass",
        window=contract.holdout,
        used_holdout=True,
        as_of_index=contract.holdout.end_index,
    )
    audit = audit_holdout(contract, reg.trials_for("e"), holdout_score=0.2, min_holdout_score=0.0)
    assert audit.is_contaminated
    assert "dirty" in audit.contaminated_trial_ids
    assert "clean" not in audit.contaminated_trial_ids
    assert not audit.is_usable


def test_clean_holdout_audit_passes():
    contract = seal_holdout(120, holdout_size=24, embargo_bars=2, min_research_bars=20, min_holdout_bars=10)
    reg = ExperimentRegistry()
    reg.record_trial(
        trial_id="only-research",
        experiment_id="e",
        strategy_family="toy",
        outcome="fail",
        window=contract.research,
        as_of_index=contract.research.end_index - 1,
    )
    audit = audit_holdout(contract, reg.trials_for("e"), holdout_score=0.4, min_holdout_score=0.0)
    assert not audit.is_contaminated
    assert audit.is_usable
    assert audit.holdout_passed is True


def test_unsealed_holdout_fails_closed():
    contract = seal_holdout(12, holdout_size=2, min_research_bars=30, min_holdout_bars=10)
    assert not contract.sealed
    audit = audit_holdout(contract, [])
    assert not audit.is_usable
