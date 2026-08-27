from __future__ import annotations

import math

import numpy as np

from fixtures import iid_normal, noisy_edge_matrix, overfit_spike_matrix
from northstar_promotion.dsr import deflated_sharpe_ratio, expected_max_sharpe
from northstar_promotion.pbo import probability_of_backtest_overfitting
from northstar_promotion.quality import QualityCode, QualityLevel
from northstar_promotion.registry import ExperimentRegistry


def _dispersed_sharpes(n: int, *, loc: float = 0.05, scale: float = 0.08, seed: int = 1) -> np.ndarray:
    return np.random.default_rng(seed).normal(loc, scale, size=n)


def test_expected_max_sharpe_zero_for_one_trial():
    sr0, flags = expected_max_sharpe(1, 0.01)
    assert sr0 == 0.0
    assert not any(f.level is QualityLevel.FAIL for f in flags)


def test_expected_max_sharpe_increases_with_trials():
    v = 1.0
    a, _ = expected_max_sharpe(2, v)
    b, _ = expected_max_sharpe(10, v)
    c, _ = expected_max_sharpe(100, v)
    assert a < b < c
    # Small-N approximation vs exact E[max of 2 N(0,1)] = 1/sqrt(pi) ≈ 0.5642.
    exact_n2 = 1.0 / math.sqrt(math.pi)
    assert abs(a - exact_n2) < 0.08


def test_more_trials_reduce_dsr():
    rets = iid_normal(400, mu=0.004, sigma=0.01, seed=3)
    dsr1 = deflated_sharpe_ratio(rets, n_trials=1)
    sharpes = _dispersed_sharpes(250, scale=0.08, seed=3)
    dsr_many = deflated_sharpe_ratio(rets, n_trials=250, trial_sharpes=sharpes)
    assert dsr1.is_usable and dsr_many.is_usable
    assert dsr_many.expected_max_sharpe > dsr1.expected_max_sharpe
    assert dsr_many.deflated_sharpe < dsr1.deflated_sharpe
    assert dsr1.deflated_sharpe > 0.9
    sampling = dsr_many.meta["details"]["selected_sampling_variance_not_used_for_sr0"]
    assert abs(dsr_many.trial_sharpe_variance - sampling) > 1e-12


def test_same_n_different_trial_dispersion_changes_sr0_and_dsr():
    """SR0 uses cross-sectional V[{SR_n}], not the selected series' sampling variance."""
    rets = iid_normal(400, mu=0.004, sigma=0.01, seed=3)
    n = 20
    tight = 0.10 + np.linspace(-0.002, 0.002, n)
    wide = np.linspace(-0.25, 0.55, n)
    a = deflated_sharpe_ratio(rets, n_trials=n, trial_sharpes=tight)
    b = deflated_sharpe_ratio(rets, n_trials=n, trial_sharpes=wide)
    assert a.is_usable and b.is_usable
    assert a.period_sharpe == b.period_sharpe
    assert a.n_trials == b.n_trials
    assert a.sampling_denominator == b.sampling_denominator
    assert b.trial_sharpe_variance > a.trial_sharpe_variance
    assert b.expected_max_sharpe > a.expected_max_sharpe
    assert b.deflated_sharpe < a.deflated_sharpe


def test_dsr_requires_trial_dispersion_when_n_trials_gt_1():
    rets = iid_normal(80, mu=0.004, sigma=0.01, seed=3)
    missing = deflated_sharpe_ratio(rets, n_trials=5)
    assert not missing.is_usable
    assert any(f.code == QualityCode.MISSING_TRIAL_SHARPE_DISPERSION for f in missing.quality_flags)


def test_dsr_rejects_trial_sharpe_length_mismatch_and_nans():
    rets = iid_normal(80, mu=0.004, sigma=0.01, seed=3)
    short = deflated_sharpe_ratio(rets, n_trials=4, trial_sharpes=[0.1, 0.2, 0.3])
    assert not short.is_usable
    nan = deflated_sharpe_ratio(rets, n_trials=3, trial_sharpes=[0.1, float("nan"), 0.2])
    assert not nan.is_usable
    both = deflated_sharpe_ratio(
        rets, n_trials=3, trial_sharpes=[0.1, 0.2, 0.3], sharpe_trials_variance=0.01
    )
    assert not both.is_usable


def test_explicit_sharpe_trials_variance_is_accepted():
    rets = iid_normal(80, mu=0.004, sigma=0.01, seed=3)
    result = deflated_sharpe_ratio(rets, n_trials=10, sharpe_trials_variance=0.04)
    assert result.is_usable
    assert abs(result.trial_sharpe_variance - 0.04) < 1e-12
    assert result.expected_max_sharpe > 0


def test_registry_trial_sharpes_feed_dsr():
    rets = iid_normal(80, mu=0.004, sigma=0.01, seed=3)
    reg = ExperimentRegistry()
    sharpes = [0.02, 0.05, 0.40]
    for i, sr in enumerate(sharpes):
        reg.record_trial(
            trial_id=f"t{i}",
            experiment_id="exp",
            strategy_family="toy",
            outcome="pass",
            metrics={"sharpe": sr},
        )
    collected, flags = reg.trial_sharpes("exp")
    assert collected == tuple(sharpes)
    assert not any(f.level is QualityLevel.FAIL for f in flags)
    dsr = deflated_sharpe_ratio(rets, n_trials=3, trial_sharpes=collected)
    assert dsr.is_usable
    missing = ExperimentRegistry()
    missing.record_trial(trial_id="x", experiment_id="e", strategy_family="toy", outcome="fail")
    none, fail_flags = missing.trial_sharpes("e")
    assert none is None
    assert any(f.level is QualityLevel.FAIL for f in fail_flags)


def test_zero_mean_dsr_near_half_for_one_trial():
    rets = iid_normal(2000, mu=0.0, sigma=0.01, seed=5)
    rets = rets - rets.mean()
    dsr = deflated_sharpe_ratio(rets, n_trials=1)
    assert dsr.is_usable
    # Exact-zero mean ⇒ period SR ≈ 0 ⇒ DSR = PSR(0) ≈ Φ(0) = 0.5.
    assert abs(dsr.deflated_sharpe - 0.5) < 0.02


def test_dsr_invalid_inputs_fail_closed():
    bad = deflated_sharpe_ratio([0.01, np.nan, 0.02], n_trials=2)
    assert not bad.is_usable
    short = deflated_sharpe_ratio(
        [0.01, 0.02, 0.03], n_trials=2, trial_sharpes=[0.1, 0.2], min_obs=10
    )
    assert not short.is_usable
    none = deflated_sharpe_ratio(iid_normal(50, 0.01, 0.01), n_trials=0)
    assert not none.is_usable


def test_pbo_low_when_one_column_has_genuine_edge():
    mat = noisy_edge_matrix(240, n_noise=5, edge_mu=0.03, edge_sigma=0.01, noise_sigma=0.02, seed=9)
    result = probability_of_backtest_overfitting(mat, n_slices=6)
    assert result.is_usable
    assert result.pbo < 0.25
    assert result.n_strategies == result.n_strategies_input == 6
    assert result.excluded_column_indices == ()


def test_pbo_high_for_slice_specific_overfit():
    mat = overfit_spike_matrix(n_slices=6, slice_len=40, seed=13)
    result = probability_of_backtest_overfitting(mat, n_slices=6)
    assert result.is_usable
    assert result.pbo > 0.6


def test_pbo_noise_is_around_one_half():
    g = np.random.default_rng(21)
    mat = g.normal(0.0, 0.02, size=(400, 8))
    result = probability_of_backtest_overfitting(mat, n_slices=8)
    assert result.is_usable
    assert 0.2 < result.pbo < 0.8


def test_pbo_requires_multiple_strategies():
    mat = iid_normal(80, 0.01, 0.02).reshape(-1, 1)
    result = probability_of_backtest_overfitting(mat, n_slices=4)
    assert not result.is_usable
    assert result.pbo != result.pbo


def test_pbo_degenerate_column_is_excluded_once_not_dropped_per_combo():
    g = np.random.default_rng(21)
    good = g.normal(0.0, 0.02, size=(400, 4))
    degenerate = np.zeros((400, 1))
    mat = np.hstack([good, degenerate])
    result = probability_of_backtest_overfitting(mat, n_slices=8)
    assert result.is_usable
    assert result.n_strategies_input == 5
    assert result.n_strategies == 4
    assert result.excluded_column_indices == (4,)
    assert result.n_combinations == math.comb(8, 4)
    assert any(f.code == QualityCode.DEGENERATE_STRATEGY for f in result.quality_flags)
    # Universe is fixed: combinations are not skipped to dodge the constant column.
    assert "skipped_combinations" not in result.meta["parameters"]
