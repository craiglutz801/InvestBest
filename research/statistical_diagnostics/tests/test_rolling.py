from __future__ import annotations

import numpy as np

from northstar_diagnostics.quality import QualityCode
from northstar_diagnostics.rolling import rolling_parameter_stability, rolling_stationarity

from fixtures import ar1, cointegrated_pair, random_walk, white_noise


def test_rolling_stationarity_on_stationary_series():
    y = white_noise(200, seed=60)
    result = rolling_stationarity(y, window=40, step=10, min_obs=20)
    assert result.is_usable
    frac = result.statistics["fraction_reject_unit_root_5pct"]
    assert frac is not None and frac > 0.7
    windows = result.details["windows"]
    assert windows
    assert windows[-1]["end_index"] == 199
    # Windows never extend past the series end
    assert all(row["end_index"] < 200 for row in windows)


def test_rolling_stationarity_on_random_walk():
    y = random_walk(220, seed=61)
    result = rolling_stationarity(y, window=50, step=10, min_obs=20)
    assert result.is_usable
    frac = result.statistics["fraction_reject_unit_root_5pct"]
    assert frac is not None and frac < 0.4


def test_rolling_does_not_consume_future_observations():
    y = np.concatenate([white_noise(80, seed=62), np.full(40, np.inf)])
    result = rolling_stationarity(y, as_of=79, window=40, step=10, min_obs=20)
    assert result.is_usable
    assert result.sample.end_index == 79
    assert all(row["end_index"] <= 79 for row in result.details["windows"])


def test_rolling_parameter_stability_recovers_stable_beta():
    y, x = cointegrated_pair(240, beta=1.5, phi=0.3, seed=63, residual_scale=0.2)
    result = rolling_parameter_stability(y, x, window=60, step=15, min_obs=30)
    assert result.is_usable
    assert abs(float(result.statistics["beta_mean"]) - 1.5) < 0.25
    rel = result.statistics["beta_relative_std"]
    assert rel is not None and rel < 0.35


def test_rolling_short_and_nan():
    short = rolling_stationarity(ar1(25, 0.4, seed=64), window=40, min_obs=20)
    assert not short.is_usable
    assert any(f.code == QualityCode.SHORT_SAMPLE for f in short.quality_flags)

    y = white_noise(80, seed=65)
    y[10] = np.nan
    nan_res = rolling_stationarity(y, window=40, min_obs=20)
    assert not nan_res.is_usable


def test_rolling_parameter_stability_rejects_unequal_lengths():
    y, x = cointegrated_pair(120, seed=66)
    result = rolling_parameter_stability(y, x[:80], window=40, step=10, min_obs=30)
    assert not result.is_usable
    assert any(f.code == QualityCode.LENGTH_MISMATCH for f in result.quality_flags)
    assert result.statistics == {}
