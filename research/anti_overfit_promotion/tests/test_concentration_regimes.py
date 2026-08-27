from __future__ import annotations

import numpy as np

from northstar_promotion.concentration import trade_pnl_concentration
from northstar_promotion.quality import QualityLevel
from northstar_promotion.regimes import evaluate_regime_slices


def test_concentrated_pnl_is_surfaced():
    pnl = np.array([10.0, 0.2, 0.1, 0.1, 0.05, -1.0, 0.0])
    report = trade_pnl_concentration(pnl, min_trades=5)
    assert report.top1_share > 0.8
    assert report.herfindahl > 0.7
    assert any(f.code == "pnl_concentration_surfaced" for f in report.quality_flags)
    # Default does not veto; it surfaces.
    assert report.veto is False or any(f.level is QualityLevel.WARN for f in report.quality_flags)


def test_concentrated_pnl_can_veto_when_capped():
    pnl = np.array([10.0, 0.2, 0.1, 0.1, 0.05, 0.05])
    report = trade_pnl_concentration(pnl, max_top1_share=0.5, min_trades=5)
    assert report.veto is True
    assert any(f.level is QualityLevel.FAIL for f in report.quality_flags)


def test_diversified_pnl_has_low_hhi():
    pnl = np.ones(20)
    report = trade_pnl_concentration(pnl, max_top1_share=0.2, min_trades=5)
    assert report.top1_share == 0.05
    assert abs(report.herfindahl - (1.0 / 20.0)) < 1e-12
    assert report.veto is False


def test_regime_slice_required_failure():
    g = np.random.default_rng(2)
    returns = np.concatenate([g.normal(0.01, 0.004, 40), g.normal(-0.01, 0.004, 40)])
    labels = ["bull"] * 40 + ["bear"] * 40
    report = evaluate_regime_slices(returns, labels, min_obs=20, min_sharpe=0.0, required_labels=("bull", "bear"))
    assert report.veto is True
    bear = next(s for s in report.slices if s.label == "bear")
    assert bear.passed is False


def test_regime_expected_fail_label():
    g = np.random.default_rng(3)
    returns = np.concatenate([g.normal(0.01, 0.004, 40), g.normal(-0.01, 0.004, 40)])
    labels = ["works"] * 40 + ["should_fail"] * 40
    report = evaluate_regime_slices(
        returns,
        labels,
        min_obs=20,
        min_sharpe=0.0,
        required_labels=("works",),
        expected_fail_labels=("should_fail",),
    )
    assert report.veto is False
    assert next(s for s in report.slices if s.label == "should_fail").passed is True
