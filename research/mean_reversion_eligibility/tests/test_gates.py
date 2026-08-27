"""Individual formation-gate rejections with typed reason codes."""

from __future__ import annotations

import numpy as np

from northstar_diagnostics.efr import FrictionInputs
from northstar_mean_reversion.engine import evaluate_candidate
from northstar_mean_reversion.events import EventVetoFlags
from northstar_mean_reversion.liquidity import LiquiditySnapshot
from northstar_mean_reversion.reasons import EligibilityReasonCode

from fixtures import (
    basket_candidate,
    broken_cointegrated_pair,
    cointegrated_pair,
    expensive_friction,
    mean_break_pair,
    pair_candidate,
    make_config,
    random_walk,
    unstable_hedge_pair,
)


N = 240


def _codes(decision) -> set[EligibilityReasonCode]:
    return set(decision.reason_codes)


def test_broken_cointegration_is_rejected():
    y, x = broken_cointegrated_pair(N, seed=11)
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config())
    assert decision.eligible is False
    codes = _codes(decision)
    assert (
        EligibilityReasonCode.BROKEN_COINTEGRATION in codes
        or EligibilityReasonCode.CADF_NOT_COINTEGRATED in codes
        or EligibilityReasonCode.SPREAD_NOT_STATIONARY in codes
        or EligibilityReasonCode.STRUCTURAL_BREAK_VETO in codes
    )


def test_unstable_hedge_ratio_is_rejected():
    y, x = unstable_hedge_pair(N, seed=12)
    decision = evaluate_candidate(
        pair_candidate(y, x),
        config=make_config(hedge_beta_relative_std_max=0.2),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.UNSTABLE_HEDGE_RATIO in _codes(decision)


def test_half_life_mismatch_is_rejected():
    y, x = cointegrated_pair(N, seed=13)
    # Genuine cointegration, but the requested holding horizon is far too short
    # relative to the estimated residual half-life.
    decision = evaluate_candidate(
        pair_candidate(y, x, holding_horizon=1.0),
        config=make_config(half_life_max_multiple_of_horizon=0.2),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.HALF_LIFE_MISMATCH in _codes(decision)


def test_structural_break_veto():
    y, x = mean_break_pair(N, seed=14, shift=12.0)
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config())
    assert decision.eligible is False
    codes = _codes(decision)
    assert (
        EligibilityReasonCode.STRUCTURAL_BREAK_VETO in codes
        or EligibilityReasonCode.SPREAD_NOT_STATIONARY in codes
        or EligibilityReasonCode.CADF_NOT_COINTEGRATED in codes
    )


def test_insufficient_efr_is_rejected():
    y, x = cointegrated_pair(N, seed=15)
    decision = evaluate_candidate(
        pair_candidate(y, x, expected_gross_edge=0.01, friction=expensive_friction()),
        config=make_config(),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.INSUFFICIENT_EFR in _codes(decision)


def test_missing_efr_inputs_fail_closed():
    y, x = cointegrated_pair(N, seed=16)
    candidate = pair_candidate(y, x)
    candidate = candidate.__class__(
        **{**candidate.__dict__, "expected_gross_edge": None, "friction": None}
    )
    decision = evaluate_candidate(candidate, config=make_config())
    assert decision.eligible is False
    assert decision.status == "insufficient_data"
    assert EligibilityReasonCode.MISSING_EFR_INPUTS in _codes(decision)


def test_invalid_friction_fail_closed():
    y, x = cointegrated_pair(N, seed=17)
    decision = evaluate_candidate(
        pair_candidate(y, x, friction=FrictionInputs(commission=float("nan"))),
        config=make_config(),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.INVALID_FRICTION in _codes(decision)


def test_missing_price_data_is_rejected():
    y, x = cointegrated_pair(N, seed=18)
    y = y.copy()
    y[10] = np.nan
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config())
    assert decision.eligible is False
    assert decision.status == "insufficient_data"
    assert EligibilityReasonCode.MISSING_OR_INVALID_DATA in _codes(decision)


def test_short_sample_is_rejected():
    y, x = cointegrated_pair(25, seed=19)
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config(min_obs=40))
    assert decision.eligible is False
    assert EligibilityReasonCode.SHORT_SAMPLE in _codes(decision)


def test_event_veto_blocks_otherwise_valid_pair():
    y, x = cointegrated_pair(N, seed=20)
    decision = evaluate_candidate(
        pair_candidate(y, x, event_flags=EventVetoFlags(earnings=True, notes=("earnings tomorrow",))),
        config=make_config(),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.EVENT_DIVERGENCE_VETO in _codes(decision)


def test_fundamental_divergence_veto():
    y, x = cointegrated_pair(N, seed=21)
    decision = evaluate_candidate(
        pair_candidate(
            y,
            x,
            event_flags=EventVetoFlags(fundamental_divergence=True, notes=("issuer spin-off",)),
        ),
        config=make_config(),
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.FUNDAMENTAL_DIVERGENCE_VETO in _codes(decision)


def test_not_shortable_snapshot_is_rejected():
    y, x = cointegrated_pair(N, seed=22)
    candidate = pair_candidate(y, x)
    snapshots = dict(candidate.liquidity or {})
    snapshots["PEP"] = LiquiditySnapshot(
        symbol="PEP",
        adv=5_000_000,
        spread_bps=4.0,
        shortable=False,
        locate_available=False,
    )
    candidate = candidate.__class__(**{**candidate.__dict__, "liquidity": snapshots})
    decision = evaluate_candidate(
        candidate, config=make_config(require_shortable=True, require_liquidity_snapshot=True)
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.NOT_SHORTABLE in _codes(decision)


def test_insufficient_liquidity_adv_gate():
    y, x = cointegrated_pair(N, seed=23)
    candidate = pair_candidate(y, x)
    snapshots = dict(candidate.liquidity or {})
    snapshots["KO"] = LiquiditySnapshot(symbol="KO", adv=1_000, spread_bps=80.0, shortable=True)
    candidate = candidate.__class__(**{**candidate.__dict__, "liquidity": snapshots})
    decision = evaluate_candidate(
        candidate, config=make_config(min_adv=1_000_000, max_spread_bps=15.0, require_liquidity_snapshot=True)
    )
    assert decision.eligible is False
    assert EligibilityReasonCode.INSUFFICIENT_LIQUIDITY in _codes(decision)


def test_every_rejection_has_a_typed_reason_code():
    y, x = cointegrated_pair(30, seed=24)
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config())
    assert decision.reason_codes
    assert all(isinstance(code, EligibilityReasonCode) for code in decision.reason_codes)
    for gate in decision.gates:
        if not gate.passed:
            assert gate.reason_code is not EligibilityReasonCode.ELIGIBLE
            assert gate.message


def test_unequal_length_legs_fail_closed_without_truncation():
    y, x = cointegrated_pair(N, seed=25)
    decision = evaluate_candidate(pair_candidate(y, x[:180]), config=make_config())
    assert decision.eligible is False
    assert decision.status == "insufficient_data"
    assert EligibilityReasonCode.MISALIGNED_INPUTS in _codes(decision)
    assert decision.hedge_ratio is None
    assert "cadf" not in decision.diagnostics


def test_duplicate_legs_fail_closed_as_invalid_panel():
    y, _x = cointegrated_pair(N, seed=26)
    decision = evaluate_candidate(pair_candidate(y, y.copy()), config=make_config())
    assert decision.eligible is False
    assert decision.status == "insufficient_data"
    assert EligibilityReasonCode.MISSING_OR_INVALID_DATA in _codes(decision)
    assert EligibilityReasonCode.SHORT_SAMPLE not in _codes(decision)


def test_constant_leg_fails_closed_as_invalid_panel():
    y, x = cointegrated_pair(N, seed=27)
    x = np.ones_like(x)
    decision = evaluate_candidate(pair_candidate(y, x), config=make_config())
    assert decision.eligible is False
    assert decision.status == "insufficient_data"
    assert EligibilityReasonCode.MISSING_OR_INVALID_DATA in _codes(decision)


def test_scaled_duplicate_basket_fails_closed():
    walk = random_walk(N, seed=28)
    panel = np.column_stack([walk, 2.0 * walk, 3.0 * walk])
    decision = evaluate_candidate(basket_candidate(panel), config=make_config())
    assert decision.eligible is False
    assert EligibilityReasonCode.MISSING_OR_INVALID_DATA in _codes(decision)
    assert "johansen" not in decision.diagnostics or not decision.diagnostics["johansen"].is_usable
