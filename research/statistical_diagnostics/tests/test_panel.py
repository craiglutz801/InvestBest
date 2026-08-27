from __future__ import annotations

import numpy as np

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.series import panel_rank_flags, prepare_panel

from fixtures import cointegrated_triple, independent_walks, random_walk


def _codes(flags) -> set[str]:
    return {f.code for f in flags}


def test_prepare_panel_full_rank_independent_walks_usable():
    y, x = independent_walks(80, seed=90)
    panel, prepared = prepare_panel(np.column_stack([y, x]), min_obs=40)
    assert prepared.usable
    assert panel is not None
    assert not any(f.level is QualityLevel.FAIL for f in prepared.flags)


def test_prepare_panel_cointegrated_triple_remains_usable():
    panel, prepared = prepare_panel(cointegrated_triple(120, seed=91), min_obs=40)
    assert prepared.usable
    assert panel is not None


def test_prepare_panel_fails_closed_on_constant_column():
    walk = random_walk(80, seed=92)
    _, prepared = prepare_panel(np.column_stack([walk, np.full(80, 4.0)]), min_obs=40)
    assert not prepared.usable
    assert QualityCode.CONSTANT_SERIES in _codes(prepared.flags)


def test_prepare_panel_fails_closed_on_duplicate_columns():
    walk = random_walk(80, seed=93)
    _, prepared = prepare_panel(np.column_stack([walk, walk.copy()]), min_obs=40)
    assert not prepared.usable
    assert QualityCode.COLLINEAR_SERIES in _codes(prepared.flags)
    assert QualityCode.NEAR_SINGULAR in _codes(prepared.flags)


def test_prepare_panel_fails_closed_on_scaled_duplicate():
    walk = random_walk(80, seed=94)
    flags = panel_rank_flags(np.column_stack([walk, 2.0 * walk]))
    codes = _codes(flags)
    assert QualityCode.NEAR_SINGULAR in codes or QualityCode.COLLINEAR_SERIES in codes
    assert QualityCode.INSUFFICIENT_RANK in codes
    assert all(f.level is QualityLevel.FAIL for f in flags if f.code in codes)


def test_prepare_panel_fails_closed_on_near_collinear_columns():
    walk = random_walk(80, seed=95)
    _, prepared = prepare_panel(np.column_stack([walk, walk + 1e-12]), min_obs=40)
    assert not prepared.usable
    codes = _codes(prepared.flags)
    assert QualityCode.NEAR_SINGULAR in codes or QualityCode.INSUFFICIENT_RANK in codes
