from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from northstar_diagnostics.adf import adf_stationarity
from northstar_diagnostics.cadf import cadf_cointegration
from northstar_diagnostics.johansen import johansen_cointegration
from northstar_diagnostics.series import prepare_series

from fixtures import cointegrated_pair, cointegrated_triple, daily_timestamps, white_noise


def test_datetime_as_of_requires_timestamps():
    y = white_noise(40, seed=80)
    as_of = datetime(2021, 1, 1, tzinfo=timezone.utc)
    prepared = prepare_series(y, as_of=as_of, min_obs=10)
    assert not prepared.usable


def test_unsorted_timestamps_fail():
    y = white_noise(20, seed=81)
    ts = daily_timestamps(20)
    ts[5], ts[6] = ts[6], ts[5]
    prepared = prepare_series(y, timestamps=ts, min_obs=10)
    assert not prepared.usable


def test_future_contaminated_pair_is_ignored_by_as_of():
    y, x = cointegrated_pair(100, seed=82)
    y = y.copy()
    x = x.copy()
    y[70:] = np.inf
    x[70:] = np.inf
    ts = daily_timestamps(100)
    result = cadf_cointegration(y, x, timestamps=ts, as_of=ts[69], min_obs=30)
    assert result.is_usable
    assert result.sample.end_index == 69


def test_future_contaminated_panel_is_ignored_by_index_cutoff():
    panel = cointegrated_triple(120, seed=83)
    panel = panel.copy()
    panel[90:, :] = np.inf
    result = johansen_cointegration(panel, as_of=89, min_obs=40)
    assert result.is_usable
    assert result.sample.end_index == 89


def test_adf_integer_cutoff_matches_manual_slice():
    y = white_noise(90, seed=84)
    full = adf_stationarity(y[:50], min_obs=20)
    cut = adf_stationarity(y, as_of=49, min_obs=20)
    assert full.is_usable and cut.is_usable
    assert abs(float(full.statistics["adf_stat"]) - float(cut.statistics["adf_stat"])) < 1e-12
    assert full.pvalue == cut.pvalue
