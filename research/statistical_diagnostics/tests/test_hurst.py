from __future__ import annotations

import numpy as np

from northstar_diagnostics.hurst import hurst_diagnostic
from northstar_diagnostics.quality import QualityCode

from fixtures import ar1, persistent_levels, random_walk, white_noise


def test_hurst_stationary_below_half():
    y = ar1(1500, phi=0.2, seed=40)
    result = hurst_diagnostic(y, min_lag=2, max_lag=40)
    assert result.is_usable
    assert result.statistics["hurst"] < 0.45


def test_hurst_random_walk_near_half():
    y = random_walk(2000, seed=41)
    result = hurst_diagnostic(y, min_lag=2, max_lag=50)
    assert result.is_usable
    h = float(result.statistics["hurst"])
    assert 0.40 < h < 0.62


def test_hurst_persistent_increments_above_half():
    y = persistent_levels(2000, phi=0.5, seed=42)
    result = hurst_diagnostic(y, min_lag=2, max_lag=50)
    assert result.is_usable
    assert float(result.statistics["hurst"]) > 0.55


def test_hurst_edge_cases():
    short = hurst_diagnostic(white_noise(20, seed=43), min_obs=50)
    assert not short.is_usable
    assert any(f.code == QualityCode.SHORT_SAMPLE for f in short.quality_flags)

    const = hurst_diagnostic(np.ones(80), min_obs=50)
    assert not const.is_usable

    y = white_noise(80, seed=44)
    y[2] = np.inf
    inf_res = hurst_diagnostic(y, min_obs=50)
    assert not inf_res.is_usable
