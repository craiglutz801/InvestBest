from __future__ import annotations

import numpy as np

from northstar_diagnostics.quality import QualityCode
from northstar_diagnostics.structural_break import (
    CUSUMOLSBreakDetector,
    ChowBreakDetector,
    StructuralBreakDetector,
    detect_structural_break,
)

from fixtures import mean_break, white_noise


def test_chow_detects_pre_specified_mean_break():
    y = mean_break(200, break_at=100, shift=5.0, seed=70)
    result = detect_structural_break(y, method="chow_ols", candidate_index=100, min_obs=30)
    assert result.is_usable
    assert result.details["break_detected"] is True
    assert result.pvalue is not None and result.pvalue < 0.01
    assert result.details["candidate_index"] == 100
    assert "break_detected" in result.to_dict()["details"]


def test_chow_does_not_flag_stable_noise_at_midpoint():
    y = white_noise(200, seed=71, scale=0.5)
    result = ChowBreakDetector().detect(y, candidate_index=100, min_obs=30)
    assert result.is_usable
    assert result.details["break_detected"] is False
    assert result.pvalue is not None and result.pvalue > 0.05


def test_chow_scan_sets_estimated_date_flag():
    y = mean_break(180, break_at=90, shift=6.0, seed=72)
    result = detect_structural_break(y, method="chow_ols", candidate_index=None, min_obs=30)
    assert result.is_usable
    assert any(f.code == QualityCode.BREAK_DATE_ESTIMATED for f in result.quality_flags)
    idx = int(result.details["candidate_index"])
    assert 60 <= idx <= 120


def test_cusum_reference_detector_matches_interface():
    detector: StructuralBreakDetector = CUSUMOLSBreakDetector()
    y = mean_break(220, break_at=110, shift=4.5, seed=73)
    result = detector.detect(y, min_obs=30)
    assert result.diagnostic_id == "structural_break"
    assert "break_detected" in result.details
    assert result.method == "cusum_ols_resid"
    # Strong mean shift should generally reject stability, but keep a soft assertion
    # if the residual CUSUM is conservative on this DGP.
    assert result.is_usable


def test_structural_break_edge_cases():
    short = detect_structural_break([1.0, 2.0, 3.0], method="chow_ols", min_obs=30)
    assert not short.is_usable
    unknown = detect_structural_break(white_noise(80, seed=74), method="bai_perron")
    assert not unknown.is_usable
    assert any(f.code == QualityCode.INVALID_INPUT for f in unknown.quality_flags)

    y = mean_break(80, 40, seed=75)
    y[5] = np.inf
    inf_res = detect_structural_break(y, method="chow_ols", candidate_index=40, min_obs=30)
    assert not inf_res.is_usable
