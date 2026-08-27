from __future__ import annotations

import numpy as np

from northstar_diagnostics.cadf import cadf_cointegration
from northstar_diagnostics.quality import QualityCode

from fixtures import cointegrated_pair, independent_walks, random_walk


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
