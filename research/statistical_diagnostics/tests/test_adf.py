from __future__ import annotations

import numpy as np

from northstar_diagnostics.adf import adf_stationarity
from northstar_diagnostics.quality import QualityCode

from fixtures import daily_timestamps, random_walk, trending_rw, white_noise


def test_adf_rejects_unit_root_for_stationary_noise():
    y = white_noise(400, seed=1)
    result = adf_stationarity(y, min_obs=20)
    assert result.is_usable
    assert result.pvalue is not None and result.pvalue < 0.05
    assert "reject_unit_root" in result.interpretation
    assert result.statistics["adf_stat"] is not None
    assert result.critical_values


def test_adf_does_not_reject_for_random_walk():
    y = random_walk(500, seed=2)
    result = adf_stationarity(y)
    assert result.is_usable
    assert result.pvalue is not None and result.pvalue > 0.05
    assert "fail_to_reject_unit_root" in result.interpretation


def test_adf_does_not_treat_trend_as_stationary_by_default():
    y = trending_rw(500, drift=0.08, seed=3)
    result = adf_stationarity(y, regression="c")
    assert result.is_usable
    assert result.pvalue is not None and result.pvalue > 0.05


def test_adf_short_sample_fails():
    result = adf_stationarity([1.0, 2.0, 1.5], min_obs=20)
    assert not result.is_usable
    assert any(f.code == QualityCode.SHORT_SAMPLE for f in result.quality_flags)


def test_adf_nan_and_inf_fail():
    y = white_noise(80, seed=4)
    y[10] = np.nan
    nan_res = adf_stationarity(y)
    assert not nan_res.is_usable
    assert any(f.code == QualityCode.MISSING_DATA for f in nan_res.quality_flags)

    z = white_noise(80, seed=4)
    z[11] = np.inf
    inf_res = adf_stationarity(z)
    assert not inf_res.is_usable
    assert any(f.code == QualityCode.NON_FINITE for f in inf_res.quality_flags)


def test_adf_constant_series_fails():
    result = adf_stationarity(np.ones(80))
    assert not result.is_usable
    codes = {f.code for f in result.quality_flags}
    assert QualityCode.DEGENERATE_VARIANCE in codes or QualityCode.CONSTANT_SERIES in codes


def test_adf_point_in_time_ignores_future_inf():
    y = white_noise(120, seed=5)
    y[80:] = np.inf
    ts = daily_timestamps(120)
    as_of = ts[59]
    result = adf_stationarity(y, timestamps=ts, as_of=as_of)
    assert result.is_usable
    assert result.sample.n_obs_used == 60
    assert result.sample.end_index == 59


def test_adf_integer_as_of_is_inclusive_and_excludes_later_values():
    y = np.concatenate([white_noise(50, seed=6), np.full(50, np.inf)])
    result = adf_stationarity(y, as_of=49, min_obs=20)
    assert result.is_usable
    assert result.sample.end_index == 49
    assert result.sample.n_obs_used == 50
