from __future__ import annotations

import numpy as np

from northstar_diagnostics.johansen import johansen_cointegration
from northstar_diagnostics.quality import QualityCode

from fixtures import cointegrated_triple, independent_walks, random_walk


def test_johansen_finds_rank_on_cointegrated_triple():
    panel = cointegrated_triple(350, seed=20)
    result = johansen_cointegration(panel, k_ar_diff=1, det_order=0)
    assert result.is_usable
    rank = result.statistics["suggested_rank_trace_5pct"]
    assert rank is not None and int(rank) >= 1
    assert "rank_" in result.interpretation
    assert result.details["first_coint_vector"]
    assert result.pvalue is None  # statsmodels ships critical values, not p-values


def test_johansen_independent_pair_often_rank_zero():
    y, x = independent_walks(300, seed=21)
    panel = np.column_stack([y, x])
    result = johansen_cointegration(panel)
    assert result.is_usable
    # Independent walks should not strongly support rank >= 1; allow a weak false positive
    # by checking the trace_r0 vs 99% critical value rather than requiring rank==0 always.
    trace0 = float(result.statistics["trace_r0"])
    cv99 = float(result.critical_values["trace_r0_99pct"])
    assert trace0 < cv99


def test_johansen_requires_two_series_and_enough_rows():
    one = johansen_cointegration(random_walk(80, seed=22))
    assert not one.is_usable
    assert any(f.code == QualityCode.INVALID_INPUT for f in one.quality_flags)

    short = johansen_cointegration(np.ones((10, 2)), min_obs=40)
    assert not short.is_usable
    assert any(f.code == QualityCode.SHORT_SAMPLE for f in short.quality_flags)


def test_johansen_nan_fails():
    panel = cointegrated_triple(80, seed=23)
    panel = panel.copy()
    panel[4, 1] = np.nan
    nan_res = johansen_cointegration(panel, min_obs=40)
    assert not nan_res.is_usable


def test_johansen_fails_closed_on_exact_linear_dependence():
    walk = random_walk(80, seed=24)
    collinear = np.column_stack([walk, 2.0 * walk, 3.0 * walk])
    result = johansen_cointegration(collinear, min_obs=40)
    assert not result.is_usable
    codes = {f.code for f in result.quality_flags}
    assert QualityCode.NEAR_SINGULAR in codes or QualityCode.INSUFFICIENT_RANK in codes or QualityCode.COLLINEAR_SERIES in codes
    assert result.statistics == {}


def test_johansen_fails_closed_on_constant_column():
    walk = random_walk(80, seed=25)
    panel = np.column_stack([walk, np.ones(80)])
    result = johansen_cointegration(panel, min_obs=40)
    assert not result.is_usable
    codes = {f.code for f in result.quality_flags}
    assert QualityCode.CONSTANT_SERIES in codes or QualityCode.DEGENERATE_VARIANCE in codes
    assert result.statistics == {}


def test_johansen_fails_closed_on_duplicate_columns():
    walk = random_walk(80, seed=26)
    panel = np.column_stack([walk, walk.copy()])
    result = johansen_cointegration(panel, min_obs=40)
    assert not result.is_usable
    codes = {f.code for f in result.quality_flags}
    assert QualityCode.COLLINEAR_SERIES in codes or QualityCode.NEAR_SINGULAR in codes
    assert result.statistics == {}


def test_johansen_fails_closed_on_near_collinear_columns():
    walk = random_walk(80, seed=27)
    panel = np.column_stack([walk, walk + 1e-12])
    result = johansen_cointegration(panel, min_obs=40)
    assert not result.is_usable
    codes = {f.code for f in result.quality_flags}
    assert QualityCode.NEAR_SINGULAR in codes or QualityCode.INSUFFICIENT_RANK in codes or QualityCode.COLLINEAR_SERIES in codes
    assert result.statistics == {}
