from __future__ import annotations

import numpy as np

from northstar_promotion.dsr import deflated_sharpe_ratio
from northstar_promotion.kelly import kelly_ceiling
from northstar_promotion.neighborhood import evaluate_plateau
from northstar_promotion.pbo import probability_of_backtest_overfitting
from northstar_promotion.quality import QualityLevel
from northstar_promotion.splits import walk_forward_splits
from northstar_promotion.stress import cost_stress


def test_nan_returns_fail_closed_across_modules():
    nan_series = [0.01, float("nan"), 0.02]
    assert not deflated_sharpe_ratio(nan_series, n_trials=2).is_usable
    assert not kelly_ceiling(nan_series, min_obs=2).is_usable
    assert not cost_stress(nan_series, [0.0, 0.0, 0.0]).is_usable
    inf_series = [0.01, float("inf")]
    assert not deflated_sharpe_ratio(inf_series, n_trials=1, min_obs=2).is_usable


def test_empty_and_short_samples_fail_closed():
    assert not deflated_sharpe_ratio([], n_trials=1).is_usable
    assert not deflated_sharpe_ratio(np.ones(80), n_trials=4).is_usable
    assert not kelly_ceiling([0.01], min_obs=30).is_usable
    splits, flags = walk_forward_splits(10, train_size=8, test_size=5, min_folds=2)
    assert splits == ()
    assert any(f.level is QualityLevel.FAIL for f in flags)


def test_pbo_odd_slices_fail_closed():
    mat = np.ones((40, 3))
    result = probability_of_backtest_overfitting(mat, n_slices=5)
    assert not result.is_usable


def test_plateau_missing_selected_id_fails_closed():
    from northstar_promotion.neighborhood import ParameterPoint

    report = evaluate_plateau(
        [ParameterPoint("a", {"x": 1.0}, 1.0)],
        selected_trial_id="missing",
    )
    assert not report.is_usable
    assert report.plateau_pass is False
