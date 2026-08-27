from __future__ import annotations

from math import log

import numpy as np

from northstar_diagnostics.half_life import mean_reversion_half_life
from northstar_diagnostics.quality import QualityCode

from fixtures import ar1, random_walk, white_noise


def test_half_life_recovers_ar1_scale():
    phi = 0.9
    y = ar1(800, phi=phi, seed=30, scale=1.0)
    result = mean_reversion_half_life(y)
    assert result.is_usable
    hl = result.statistics["half_life"]
    assert hl is not None
    expected = -log(2.0) / log(phi)
    # Discrete Δy regression is close to -ln(2)/θ with θ=φ-1; allow a wide but informative band
    assert 3.0 < float(hl) < 14.0
    assert abs(float(hl) - expected) < 5.0
    assert result.statistics["theta"] < 0


def test_half_life_undefined_for_random_walk():
    y = random_walk(300, seed=31)
    result = mean_reversion_half_life(y)
    assert result.is_usable or any(f.code == QualityCode.HALF_LIFE_UNDEFINED for f in result.quality_flags)
    hl = result.statistics.get("half_life") if result.statistics else None
    # RW should not yield a small, confident half-life
    if hl is not None:
        assert float(hl) > 20


def test_half_life_fast_for_white_noise():
    y = white_noise(200, seed=32)
    result = mean_reversion_half_life(y)
    assert result.is_usable
    hl = result.statistics["half_life"]
    assert hl is not None
    assert 0 < float(hl) < 3


def test_half_life_rejects_short_nan_constant():
    assert not mean_reversion_half_life([1.0, 1.1], min_obs=20).is_usable
    y = ar1(40, 0.5, seed=33)
    y[3] = np.nan
    assert not mean_reversion_half_life(y).is_usable
    const = mean_reversion_half_life(np.ones(40))
    assert not const.is_usable
    assert any(
        f.code in {QualityCode.DEGENERATE_VARIANCE, QualityCode.CONSTANT_SERIES, QualityCode.NEAR_SINGULAR}
        for f in const.quality_flags
    )
