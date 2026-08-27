from __future__ import annotations

import math

import numpy as np

from fixtures import iid_normal, noisy_edge_matrix, overfit_spike_matrix
from northstar_promotion.dsr import deflated_sharpe_ratio, expected_max_sharpe
from northstar_promotion.pbo import probability_of_backtest_overfitting
from northstar_promotion.quality import QualityLevel


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
    dsr_many = deflated_sharpe_ratio(rets, n_trials=250)
    assert dsr1.is_usable and dsr_many.is_usable
    assert dsr_many.expected_max_sharpe > dsr1.expected_max_sharpe
    assert dsr_many.deflated_sharpe < dsr1.deflated_sharpe
    assert dsr1.deflated_sharpe > 0.9


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
    short = deflated_sharpe_ratio([0.01, 0.02, 0.03], n_trials=2, min_obs=10)
    assert not short.is_usable
    none = deflated_sharpe_ratio(iid_normal(50, 0.01, 0.01), n_trials=0)
    assert not none.is_usable


def test_pbo_low_when_one_column_has_genuine_edge():
    mat = noisy_edge_matrix(240, n_noise=5, edge_mu=0.03, edge_sigma=0.01, noise_sigma=0.02, seed=9)
    result = probability_of_backtest_overfitting(mat, n_slices=6)
    assert result.is_usable
    assert result.pbo < 0.25


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
