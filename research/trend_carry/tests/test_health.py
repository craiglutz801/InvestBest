"""Trend-health diagnostics: agreement, persistence, whipsaw, vol shock, breadth."""

from __future__ import annotations

from northstar_trend_carry.fixtures import (
    choppy_series,
    downtrend_series,
    mixed_horizon_series,
    uptrend_series,
    vol_shock_series,
)
from northstar_trend_carry.health import evaluate_trend_health
from northstar_trend_carry.momentum import evaluate_cross_asset_trend


def test_uptrend_health_high_agreement_and_persistence():
    series = uptrend_series()
    health = evaluate_trend_health(series)
    assert health.is_usable
    assert health.horizon_agreement == 1.0
    assert health.persistence is not None and health.persistence >= 0.8
    assert health.whipsaw_rate is not None and health.whipsaw_rate < 0.2
    assert health.research_health_label == "healthy"
    assert health.to_dict()["authorizes_throttle"] is False
    assert health.to_dict()["is_order"] is False


def test_mixed_horizons_report_disagreement():
    series = mixed_horizon_series()
    health = evaluate_trend_health(series)
    assert health.horizon_agreement is not None
    assert health.horizon_agreement < 1.0
    assert health.n_horizons_agreeing < health.n_horizons_usable
    assert health.research_health_label in {"mixed", "degraded", "healthy"}


def test_choppy_series_has_elevated_whipsaw():
    series = choppy_series(period=6)
    health = evaluate_trend_health(series, whipsaw_window_bars=40)
    assert health.whipsaw_rate is not None
    assert health.whipsaw_rate > 0.15


def test_volatility_shock_state():
    series = vol_shock_series()
    health = evaluate_trend_health(series, vol_shock_ratio_threshold=2.0)
    assert health.vol_shock_ratio is not None
    assert health.vol_shock_state in {"shock", "elevated"}
    if health.vol_shock_state == "shock":
        assert any(f.code == "volatility_shock" for f in health.quality_flags)


def test_breadth_from_universe_snapshot():
    universe = evaluate_cross_asset_trend(
        {
            "UP": uptrend_series(symbol="UP"),
            "UP2": uptrend_series(seed=99, symbol="UP2"),
            "DN": downtrend_series(symbol="DN"),
        }
    )
    health = evaluate_trend_health(
        uptrend_series(symbol="UP"),
        universe_signals=universe.assets,
    )
    assert health.breadth_long_fraction is not None
    assert health.breadth_long_fraction == universe.breadth_long_fraction
    assert 0.5 <= health.breadth_long_fraction <= 1.0
