"""Neighboring-parameter plateau: never select a single optimized horizon."""

from __future__ import annotations

from northstar_trend_carry.fixtures import choppy_series, uptrend_series
from northstar_trend_carry.robustness import (
    neighboring_parameter_plateau,
    refuse_performance_sweep_selection,
)


def test_uptrend_neighborhood_is_a_sign_plateau():
    report = neighboring_parameter_plateau(uptrend_series(), radius=4)
    assert report.refuses_single_horizon_selection is True
    assert report.selected_lookback is None
    assert report.modal_sign == 1
    assert report.neighborhood_sign_agreement is not None
    assert report.neighborhood_sign_agreement >= 0.8
    assert report.plateau_width >= 5
    payload = report.to_dict()
    assert payload["selected_lookback"] is None
    assert payload["is_order"] is False


def test_plateau_does_not_pick_argmax_lookback_from_observations():
    report = neighboring_parameter_plateau(uptrend_series(), center_lookbacks=(21, 63), radius=2)
    usable = [o for o in report.observations if o.usable and o.capped_strength is not None]
    assert usable
    strongest = max(usable, key=lambda o: abs(o.capped_strength or 0.0))
    # The report must not promote that lookback.
    assert report.selected_lookback is None
    assert report.selected_lookback != strongest.lookback_bars


def test_performance_sweep_is_refused():
    sweep = {21: 0.40, 42: 0.55, 63: 1.90, 84: 0.70, 126: 0.80, 252: 0.35}
    refusal = refuse_performance_sweep_selection(sweep)
    assert refusal.refuses_single_horizon_selection is True
    assert refusal.selected_lookback is None
    assert refusal.highest_metric_lookback == 63
    assert refusal.highest_metric_value == 1.90
    payload = refusal.to_dict()
    assert payload["used_for_trading"] is False
    assert payload["selected_lookback"] is None
    assert "not a license to promote" in refusal.reason.lower() or "overfitting" in refusal.reason.lower()


def test_choppy_neighborhood_is_less_stable_than_trend():
    trend = neighboring_parameter_plateau(uptrend_series(), center_lookbacks=(21,), radius=6)
    chop = neighboring_parameter_plateau(choppy_series(), center_lookbacks=(21,), radius=6)
    assert trend.neighborhood_sign_agreement is not None
    # Choppy data should not match a perfect long plateau.
    if chop.neighborhood_sign_agreement is None:
        return
    assert chop.neighborhood_sign_agreement <= trend.neighborhood_sign_agreement


def test_invalid_radius_and_lookback():
    bad_radius = neighboring_parameter_plateau(uptrend_series(), radius=-1)
    assert any(f.level.value == "fail" for f in bad_radius.quality_flags)
    bad_L = neighboring_parameter_plateau(uptrend_series(), center_lookbacks=(0, -3))
    assert any(f.level.value == "fail" for f in bad_L.quality_flags)
