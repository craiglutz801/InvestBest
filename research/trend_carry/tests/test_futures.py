"""Futures carry: contango/backwardation, rolls, expired/missing, PIT, no lookahead."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from northstar_trend_carry.fixtures import expired_only_chain, synthetic_futures_chain, two_leg_chain
from northstar_trend_carry.futures import (
    ContractChain,
    FuturesContractObservation,
    InMemoryFuturesProvider,
    QuoteSyncConfig,
    evaluate_carry,
    required_provider_fields,
)


def test_required_provider_fields_are_documented():
    fields = required_provider_fields()
    for name in ("contract_symbol", "root", "expiry", "price", "timestamp"):
        assert name in fields["required"]
    for name in ("volume", "open_interest"):
        assert name in fields["recommended"]


def test_contango_negative_roll_yield_for_long():
    chain = synthetic_futures_chain(root="ES", curve="contango")
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of, roll_lead_days=5)
    assert carry.is_usable
    assert carry.curve_state == "contango"
    assert carry.roll_yield_annualized is not None
    assert carry.roll_yield_annualized < 0
    assert carry.roll_direction == "front_to_next"
    assert carry.front is not None and carry.next_contract is not None
    assert carry.next_contract.price > carry.front.price
    assert carry.to_dict()["is_live_futures_execution"] is False
    assert carry.to_dict()["curve_gap_is_not_execution_friction"] is True
    assert carry.execution_roll_friction is None
    assert carry.execution_roll_friction_source == "unknown_caller_supplied"
    assert "estimated_roll_friction" not in carry.to_dict()


def test_backwardation_positive_roll_yield_for_long():
    chain = synthetic_futures_chain(root="CL", curve="backwardation")
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of)
    assert carry.is_usable
    assert carry.curve_state == "backwardation"
    assert carry.roll_yield_annualized is not None
    assert carry.roll_yield_annualized > 0
    assert carry.next_contract.price < carry.front.price


def test_roll_recommended_when_inside_lead_days():
    chain = synthetic_futures_chain(root="ES", curve="contango", front_start=date(2024, 1, 25))
    as_of = datetime(2024, 1, 22, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of, roll_lead_days=5)
    assert carry.days_to_front_expiry is not None
    assert carry.days_to_front_expiry <= 5
    assert carry.roll_recommended is True
    assert carry.roll_direction == "front_to_next"


def test_roll_not_recommended_when_far_from_expiry():
    chain = synthetic_futures_chain(root="ES", curve="contango", front_start=date(2024, 6, 15))
    as_of = datetime(2024, 1, 10, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of, roll_lead_days=5)
    assert carry.days_to_front_expiry is not None
    assert carry.days_to_front_expiry > 5
    assert carry.roll_recommended is False


def test_expired_contracts_fail_closed():
    chain = expired_only_chain()
    as_of = datetime(2024, 6, 1, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of)
    assert not carry.is_usable
    assert any(f.code == "expired_contract" for f in carry.quality_flags)


def test_missing_deferred_contract():
    ts = datetime(2024, 1, 10, tzinfo=timezone.utc)
    obs = FuturesContractObservation(
        contract_symbol="ES2403",
        root="ES",
        expiry=date(2024, 3, 15),
        price=100.0,
        timestamp=ts,
    )
    chain = ContractChain(root="ES", observations=(obs,))
    carry = evaluate_carry(chain, as_of=ts)
    assert not carry.is_usable
    assert any(f.code == "insufficient_chain" for f in carry.quality_flags)


def test_missing_chain_at_as_of():
    chain = synthetic_futures_chain(root="ES", curve="contango")
    too_early = datetime(2020, 1, 1, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=too_early)
    assert not carry.is_usable
    assert any(f.code == "missing_contract" for f in carry.quality_flags)


def test_point_in_time_ignores_future_quotes():
    chain = synthetic_futures_chain(root="ES", curve="contango", include_future_quotes=True)
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    carry = evaluate_carry(chain, as_of=as_of)
    assert carry.is_usable
    assert carry.front is not None
    # Lookahead quotes were 10x spiked; PIT front must stay near 100.
    assert carry.front.price < 200.0
    assert any(f.code == "lookahead_blocked" for f in carry.quality_flags)


def test_in_memory_provider_is_not_a_paid_vendor():
    chain = synthetic_futures_chain(root="ES", curve="contango")
    provider = InMemoryFuturesProvider(chains={"ES": chain})
    as_of = datetime(2024, 1, 10, tzinfo=timezone.utc)
    rows = provider.contract_observations("ES", end=as_of)
    assert rows
    assert all(o.timestamp <= as_of for o in rows)
    assert provider.contract_observations("NOPE") == ()


def test_five_percent_curve_gap_is_carry_not_execution_friction():
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    chain = two_leg_chain(front_price=100.0, next_price=105.0, as_of=as_of)
    carry = evaluate_carry(chain, as_of=as_of)
    assert carry.is_usable
    assert carry.curve_state == "contango"
    assert carry.curve_gap == 0.05
    assert carry.roll_gap == 0.05
    assert carry.execution_roll_friction is None
    assert carry.execution_roll_friction_source == "unknown_caller_supplied"
    assert any(f.code == "unknown_execution_friction" for f in carry.quality_flags)
    payload = carry.to_dict()
    assert "estimated_roll_friction" not in payload
    assert payload["curve_gap_is_not_execution_friction"] is True


def test_stale_deferred_quote_fails_closed():
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    chain = two_leg_chain(
        front_timestamp=as_of,
        next_timestamp=as_of - timedelta(days=10),
        as_of=as_of,
    )
    carry = evaluate_carry(
        chain,
        as_of=as_of,
        quote_sync=QuoteSyncConfig(max_quote_age=timedelta(days=3), max_front_next_skew=timedelta(days=1)),
    )
    assert not carry.is_usable
    assert carry.curve_state == "unavailable"
    assert carry.roll_yield_annualized is None
    assert carry.curve_gap is None
    codes = {f.code for f in carry.quality_flags}
    assert "stale_quote" in codes or "misaligned_quotes" in codes


def test_misaligned_front_next_quotes_fail_closed_even_if_each_is_fresh():
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    chain = two_leg_chain(
        front_timestamp=as_of,
        next_timestamp=as_of - timedelta(hours=36),
        as_of=as_of,
    )
    carry = evaluate_carry(
        chain,
        as_of=as_of,
        quote_sync=QuoteSyncConfig(max_quote_age=timedelta(days=3), max_front_next_skew=timedelta(hours=12)),
    )
    assert not carry.is_usable
    assert carry.curve_gap is None
    assert any(f.code == "misaligned_quotes" for f in carry.quality_flags)


def test_stale_front_quote_fails_closed():
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    chain = two_leg_chain(
        front_timestamp=as_of - timedelta(days=8),
        next_timestamp=as_of - timedelta(days=8),
        as_of=as_of,
    )
    carry = evaluate_carry(
        chain,
        as_of=as_of,
        quote_sync=QuoteSyncConfig(max_quote_age=timedelta(days=3), max_front_next_skew=timedelta(days=1)),
    )
    assert not carry.is_usable
    assert any(f.code == "stale_quote" for f in carry.quality_flags)
    assert carry.roll_yield_annualized is None


def test_root_mismatch_fails_closed():
    as_of = datetime(2024, 1, 20, tzinfo=timezone.utc)
    chain = two_leg_chain(as_of=as_of, next_root="NQ")
    carry = evaluate_carry(chain, as_of=as_of)
    assert not carry.is_usable
    assert any(f.code == "root_mismatch" for f in carry.quality_flags)
    assert carry.curve_gap is None


def test_aligned_fresh_quotes_remain_usable():
    as_of = datetime(2024, 1, 20, 16, 0, tzinfo=timezone.utc)
    chain = two_leg_chain(
        front_timestamp=as_of - timedelta(minutes=15),
        next_timestamp=as_of - timedelta(minutes=10),
        as_of=as_of,
    )
    carry = evaluate_carry(
        chain,
        as_of=as_of,
        quote_sync=QuoteSyncConfig(max_quote_age=timedelta(hours=6), max_front_next_skew=timedelta(hours=1)),
    )
    assert carry.is_usable
    assert carry.front_next_skew_seconds == 5 * 60
