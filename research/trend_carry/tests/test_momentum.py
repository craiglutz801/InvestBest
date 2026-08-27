"""Sustained trend, chop, vol scaling, mixed horizons, and invalid inputs."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pytest

from northstar_trend_carry.fixtures import (
    choppy_series,
    downtrend_series,
    mixed_horizon_series,
    uptrend_series,
    vol_pair_same_drift,
)
from northstar_trend_carry.momentum import EnsembleConfig, evaluate_asset_trend, evaluate_cross_asset_trend
from northstar_trend_carry.schema import DEFAULT_HORIZONS, HorizonSpec
from northstar_trend_carry.series import PriceSeries, make_daily_series


def test_default_horizons_are_multi_speed_trading_months():
    names = [h.name for h in DEFAULT_HORIZONS]
    bars = [h.lookback_bars for h in DEFAULT_HORIZONS]
    assert names == ["1m", "3m", "6m", "12m"]
    assert bars == [21, 63, 126, 252]


def test_sustained_uptrend_is_long_across_horizons():
    series = uptrend_series()
    signal = evaluate_asset_trend(series)
    assert signal.is_usable
    assert signal.ensemble_sign == 1
    assert signal.ensemble_expression == "long"
    assert signal.ensemble_method == "equal_weight_capped_horizons"
    assert signal.to_dict()["is_order"] is False
    usable = [h for h in signal.horizons if h.is_usable]
    assert usable
    assert all(h.sign == 1 for h in usable)


def test_sustained_downtrend_is_short_when_research_shorts_allowed():
    series = downtrend_series()
    signal = evaluate_asset_trend(series)
    assert signal.is_usable
    assert signal.ensemble_sign == -1
    assert signal.ensemble_expression == "short"


def test_downtrend_flattens_when_shorts_not_permitted():
    series = downtrend_series()
    cfg = EnsembleConfig(allow_short=False)
    signal = evaluate_asset_trend(series, cfg)
    assert signal.ensemble_sign == 0
    assert signal.ensemble_expression == "flat"
    assert any(f.code == "short_expression_blocked" for h in signal.horizons for f in h.quality_flags)


def test_choppy_series_is_not_a_clean_trend():
    series = choppy_series()
    signal = evaluate_asset_trend(series)
    assert signal.is_usable
    # Oscillation should not look like a strong one-sided ensemble.
    assert abs(signal.ensemble_strength) < 2.0
    signs = {h.sign for h in signal.horizons if h.is_usable}
    # Either mixed or near-flat; must not be a unanimous strong trend.
    assert not (len(signs) == 1 and abs(signal.ensemble_strength or 0) > 1.5)


def test_volatility_normalization_scales_strength():
    low, high = vol_pair_same_drift()
    cfg = EnsembleConfig(signal_cap=10.0)
    s_low = evaluate_asset_trend(low, cfg)
    s_high = evaluate_asset_trend(high, cfg)
    assert s_low.is_usable and s_high.is_usable
    # Same drift, higher vol => smaller |vol-normalized| strength.
    assert abs(s_low.ensemble_strength) > abs(s_high.ensemble_strength)


def test_signal_strength_cap_is_applied():
    series = uptrend_series()
    tight = evaluate_asset_trend(series, EnsembleConfig(signal_cap=0.25))
    assert tight.is_usable
    for h in tight.horizons:
        if h.capped_strength is not None:
            assert abs(h.capped_strength) <= 0.25 + 1e-12
    assert abs(tight.ensemble_strength) <= 0.25 + 1e-12


def test_mixed_horizon_agreement_recent_reversal():
    series = mixed_horizon_series()
    signal = evaluate_asset_trend(series)
    by_name = {h.horizon.name: h for h in signal.horizons if h.is_usable}
    assert "1m" in by_name and "12m" in by_name
    assert by_name["1m"].sign == -1
    assert by_name["12m"].sign == 1
    assert any(f.code == "mixed_horizon_signs" for f in signal.quality_flags)


def test_horizon_metadata_is_explicit():
    signal = evaluate_asset_trend(uptrend_series())
    payload = signal.to_dict()
    assert payload["horizons"][0]["horizon"]["name"] == "1m"
    assert payload["horizons"][0]["horizon"]["lookback_bars"] == 21
    assert payload["config"]["does_not_select_optimized_lookback"] is True


def test_cross_asset_snapshot_is_not_live_portfolio_input():
    snap = evaluate_cross_asset_trend(
        {
            "UP": uptrend_series(symbol="UP"),
            "DN": downtrend_series(symbol="DN"),
            "CHOP": choppy_series(symbol="CHOP"),
        }
    )
    payload = snap.to_dict()
    assert payload["wired_to_live_portfolio_engine"] is False
    assert payload["is_order"] is False
    assert snap.breadth_long_fraction is not None
    assert 0.0 < snap.breadth_long_fraction < 1.0
    assert snap.research_weights
    assert pytest.approx(sum(abs(w) for w in snap.research_weights.values()), rel=1e-9) == 1.0


def test_point_in_time_index_ignores_later_prices():
    series = uptrend_series(n=400)
    early = evaluate_asset_trend(series, as_of=200)
    assert early.sample.end_index == 200
    assert early.sample.n_obs_used == 201
    # Contaminate the tail; PIT result must be unchanged.
    dirty_prices = list(series.prices)
    dirty_prices[-1] = 1e9
    dirty = PriceSeries(series.symbol, series.timestamps, tuple(dirty_prices), series.asset_class)
    early_dirty = evaluate_asset_trend(dirty, as_of=200)
    assert early_dirty.ensemble_strength == pytest.approx(early.ensemble_strength)


def test_point_in_time_timestamp_cutoff():
    series = uptrend_series(n=100)
    cutoff = series.timestamps[50]
    signal = evaluate_asset_trend(series, as_of=cutoff)
    assert signal.sample.end_index == 50
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    full = evaluate_asset_trend(series, as_of=future)
    assert full.sample.end_index == 99


def test_invalid_empty_series():
    series = PriceSeries("X", (), (), None)
    signal = evaluate_asset_trend(series)
    assert not signal.is_usable
    assert signal.ensemble_strength is None


def test_invalid_nan_and_inf_prices():
    base = uptrend_series(n=80)
    nan_prices = list(base.prices)
    nan_prices[10] = float("nan")
    nan_series = PriceSeries(base.symbol, base.timestamps, tuple(nan_prices), base.asset_class)
    assert not evaluate_asset_trend(nan_series).is_usable

    inf_prices = list(base.prices)
    inf_prices[-1] = float("inf")
    inf_series = PriceSeries(base.symbol, base.timestamps, tuple(inf_prices), base.asset_class)
    assert not evaluate_asset_trend(inf_series).is_usable


def test_invalid_unsorted_timestamps():
    series = uptrend_series(n=40)
    stamps = list(series.timestamps)
    stamps[5], stamps[6] = stamps[6], stamps[5]
    bad = PriceSeries(series.symbol, tuple(stamps), series.prices, series.asset_class)
    assert not evaluate_asset_trend(bad).is_usable


def test_invalid_non_positive_prices():
    series = make_daily_series("Z", [100.0, 101.0, 0.0, 102.0])
    assert not evaluate_asset_trend(series).is_usable


def test_constant_series_degenerate_vol():
    series = make_daily_series("FLAT", [100.0] * 300)
    signal = evaluate_asset_trend(series)
    assert not signal.is_usable


def test_negative_lookback_is_invalid():
    cfg = EnsembleConfig(horizons=(HorizonSpec("bad", lookback_bars=-5),))
    signal = evaluate_asset_trend(uptrend_series(), cfg)
    assert not signal.is_usable


def test_short_sample_fails_closed():
    series = make_daily_series("S", [100.0, 101.0, 102.0])
    signal = evaluate_asset_trend(series)
    assert not signal.is_usable


def test_as_of_before_first_observation():
    series = uptrend_series(n=50)
    too_early = datetime(1990, 1, 1, tzinfo=timezone.utc)
    signal = evaluate_asset_trend(series, as_of=too_early)
    assert not signal.is_usable


def test_mismatched_lengths_raise():
    with pytest.raises(ValueError):
        PriceSeries("X", (datetime(2020, 1, 1, tzinfo=timezone.utc),), (1.0, 2.0), None)


def test_results_are_deterministic():
    series = uptrend_series(seed=99)
    a = evaluate_asset_trend(series, computed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    b = evaluate_asset_trend(series, computed_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert a.ensemble_strength == b.ensemble_strength
    assert [h.capped_strength for h in a.horizons] == [h.capped_strength for h in b.horizons]
