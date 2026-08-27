from __future__ import annotations

import numpy as np

from northstar_promotion.quality import QualityLevel
from northstar_promotion.stress import cost_stress, execution_delay_stress


def test_cost_stress_vetoes_attractive_baseline():
    n = 80
    g = np.random.default_rng(0)
    gross = 0.012 + g.normal(0.0, 0.002, size=n)
    costs = np.full(n, 0.008)
    report = cost_stress(gross, costs, multipliers=(1.0, 1.5, 2.0), min_sharpe=0.0)
    baseline = next(s for s in report.scenarios if s.name == "baseline")
    stressed = [s for s in report.scenarios if s.name != "baseline"]
    assert baseline.passed is True
    assert baseline.sharpe > 0
    assert any(not s.passed for s in stressed)
    assert report.veto is True
    assert any(f.level is QualityLevel.FAIL for f in report.quality_flags)


def test_cost_stress_all_clear_when_edge_survives():
    n = 80
    g = np.random.default_rng(1)
    gross = 0.02 + g.normal(0.0, 0.003, size=n)
    costs = np.full(n, 0.001)
    report = cost_stress(gross, costs, multipliers=(1.0, 1.5, 2.0), min_sharpe=0.0)
    assert report.veto is False
    assert all(s.passed for s in report.scenarios)


def test_delay_stress_vetoes_when_signal_is_one_bar_fragile():
    n = 60
    asset = np.zeros(n)
    # Profit only if we hold the spike bar itself; a 1-bar delay misses it.
    asset[10] = 0.50
    asset[11] = -0.40
    pos = np.zeros(n)
    pos[10] = 1.0
    report = execution_delay_stress(asset, pos, delay_bars=(0, 1), min_sharpe=0.0)
    baseline = next(s for s in report.scenarios if s.delay_bars == 0)
    delayed = next(s for s in report.scenarios if s.delay_bars == 1)
    assert baseline.passed is True
    assert delayed.passed is False
    assert report.veto is True


def test_invalid_cost_inputs_fail_closed():
    report = cost_stress([0.01, np.nan], [0.001, 0.001])
    assert report.veto is True
    assert report.is_usable is False
    report2 = cost_stress([0.01, 0.01], [0.001], multipliers=(1.0, 1.5))
    assert report2.is_usable is False
