from __future__ import annotations

import numpy as np

from northstar_diagnostics.quality import QualityCode
from northstar_diagnostics.variance_ratio import variance_ratio_diagnostic

from fixtures import ar1, persistent_levels, random_walk, white_noise


def test_vr_near_one_for_random_walk():
    y = random_walk(800, seed=50)
    result = variance_ratio_diagnostic(y, q=2)
    assert result.is_usable
    vr = float(result.statistics["vr"])
    assert 0.8 < vr < 1.2


def test_vr_below_one_for_mean_reverting_levels():
    y = ar1(800, phi=0.3, seed=51)
    result = variance_ratio_diagnostic(y, q=5)
    assert result.is_usable
    assert float(result.statistics["vr"]) < 0.9


def test_vr_above_one_for_persistent_increments():
    y = persistent_levels(800, phi=0.45, seed=52)
    result = variance_ratio_diagnostic(y, q=5)
    assert result.is_usable
    assert float(result.statistics["vr"]) > 1.05


def test_vr_edge_cases():
    assert not variance_ratio_diagnostic(white_noise(10, seed=53), q=2, min_obs=40).is_usable
    assert not variance_ratio_diagnostic(random_walk(80, seed=54), q=1).is_usable
    const = variance_ratio_diagnostic(np.full(80, 3.0), q=2, min_obs=40)
    assert not const.is_usable
    codes = {f.code for f in const.quality_flags}
    assert QualityCode.DEGENERATE_VARIANCE in codes or QualityCode.CONSTANT_SERIES in codes

    y = random_walk(80, seed=55)
    y[9] = np.nan
    assert not variance_ratio_diagnostic(y, q=2, min_obs=40).is_usable
