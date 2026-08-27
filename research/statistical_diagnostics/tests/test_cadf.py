from __future__ import annotations

from datetime import timedelta

import numpy as np

from northstar_diagnostics.cadf import cadf_cointegration
from northstar_diagnostics.quality import QualityCode

from fixtures import cointegrated_pair, daily_timestamps, independent_walks, random_walk


def test_cadf_detects_cointegrated_pair_and_recovers_beta():
    y, x = cointegrated_pair(500, beta=2.0, phi=0.2, seed=11, residual_scale=0.2)
    result = cadf_cointegration(y, x)
    assert result.is_usable
    assert result.pvalue is not None and result.pvalue < 0.05
    assert "reject_no_cointegration" in result.interpretation
    assert abs(float(result.statistics["beta_0"]) - 2.0) < 0.2
    assert result.sample.n_obs_used == 500


def test_cadf_independent_walks_do_not_look_cointegrated():
    y, x = independent_walks(400, seed=12)
    result = cadf_cointegration(y, x)
    assert result.is_usable
    assert result.pvalue is not None and result.pvalue > 0.05


def test_cadf_short_sample_and_identical_series():
    short = cadf_cointegration([1.0, 2.0, 3.0], [1.1, 2.1, 3.2], min_obs=30)
    assert not short.is_usable
    assert any(f.code == QualityCode.SHORT_SAMPLE for f in short.quality_flags)

    walk = random_walk(80, seed=13)
    identical = cadf_cointegration(walk, walk)
    assert not identical.is_usable
    codes = {f.code for f in identical.quality_flags}
    assert QualityCode.DEGENERATE_VARIANCE in codes or QualityCode.NEAR_SINGULAR in codes


def test_cadf_nan_fails():
    y, x = cointegrated_pair(80, seed=14)
    y = y.copy()
    y[5] = np.nan
    result = cadf_cointegration(y, x)
    assert not result.is_usable
    assert any(f.code == QualityCode.MISSING_DATA for f in result.quality_flags)


def test_cadf_rejects_unequal_lengths_without_truncating():
    y, x = cointegrated_pair(120, seed=15)
    result = cadf_cointegration(y, x[:90], min_obs=30)
    assert not result.is_usable
    assert any(f.code == QualityCode.LENGTH_MISMATCH for f in result.quality_flags)
    assert result.pvalue is None
    assert result.statistics == {}


def test_cadf_rejects_timestamp_mismatch():
    y, x = cointegrated_pair(80, seed=16)
    ts_y = daily_timestamps(80)
    ts_x = daily_timestamps(80, start=ts_y[0] + timedelta(days=3))
    result = cadf_cointegration(y, x, timestamps=ts_y, x_timestamps=ts_x, min_obs=30)
    assert not result.is_usable
    assert any(f.code == QualityCode.TIMESTAMP_MISMATCH for f in result.quality_flags)
    assert result.pvalue is None


def test_cadf_rejects_timestamps_on_only_one_leg():
    y, x = cointegrated_pair(80, seed=17)
    ts = daily_timestamps(80)
    result = cadf_cointegration(y, x, x_timestamps=ts, min_obs=30)
    assert not result.is_usable
    assert any(f.code == QualityCode.TIMESTAMP_MISMATCH for f in result.quality_flags)


def test_cadf_accepts_shared_aligned_timestamps():
    y, x = cointegrated_pair(120, seed=18)
    ts = daily_timestamps(120)
    result = cadf_cointegration(y, x, timestamps=ts, x_timestamps=ts, min_obs=30)
    assert result.is_usable

