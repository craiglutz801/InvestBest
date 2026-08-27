"""Point-in-time cutoffs: future observations must not affect eligibility."""

from __future__ import annotations

import numpy as np

from datetime import datetime, timezone

from northstar_mean_reversion.engine import evaluate_candidate
from northstar_mean_reversion.liquidity import LiquiditySnapshot
from northstar_mean_reversion.reasons import EligibilityReasonCode

from fixtures import (
    cointegrated_pair,
    daily_timestamps,
    pair_candidate,
    make_config,
)


N = 240


def test_future_inf_contamination_is_ignored_when_as_of_cuts_it_off():
    y, x = cointegrated_pair(N, seed=41)
    timestamps = daily_timestamps(N + 1)
    y_future = np.concatenate([y, np.array([np.inf])])
    x_future = np.concatenate([x, np.array([np.inf])])
    as_of = timestamps[N - 1]
    decision = evaluate_candidate(
        pair_candidate(y_future, x_future, timestamps=timestamps, as_of=as_of),
        config=make_config(),
    )
    assert decision.eligible is True


def test_as_of_index_cutoff_does_not_use_later_bars():
    y, x = cointegrated_pair(N, seed=42)
    y = np.concatenate([y, np.array([1e12])])
    x = np.concatenate([x, np.array([-1e12])])
    decision = evaluate_candidate(
        pair_candidate(y, x, as_of=N - 1),
        config=make_config(),
    )
    assert decision.eligible is True


def test_early_as_of_yields_short_sample():
    y, x = cointegrated_pair(N, seed=43)
    decision = evaluate_candidate(
        pair_candidate(y, x, as_of=20),
        config=make_config(min_obs=40),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.SHORT_SAMPLE in decision.reason_codes


def test_future_liquidity_snapshot_is_a_pit_violation():
    y, x = cointegrated_pair(N, seed=44)
    timestamps = daily_timestamps(N)
    as_of = timestamps[100]
    future = datetime(2025, 1, 1, tzinfo=timezone.utc)
    candidate = pair_candidate(y, x, timestamps=timestamps, as_of=as_of)
    snapshots = {
        "KO": LiquiditySnapshot(symbol="KO", as_of=future, adv=5_000_000, spread_bps=4.0, shortable=True),
        "PEP": LiquiditySnapshot(symbol="PEP", as_of=future, adv=5_000_000, spread_bps=4.0, shortable=True),
    }
    candidate = candidate.__class__(**{**candidate.__dict__, "liquidity": snapshots})
    decision = evaluate_candidate(
        candidate,
        config=make_config(require_liquidity_snapshot=True, min_adv=1.0),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.POINT_IN_TIME_VIOLATION in decision.reason_codes
