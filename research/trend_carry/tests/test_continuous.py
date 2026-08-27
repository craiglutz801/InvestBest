"""Research continuous series vs executable economics; no lookahead on rolls."""

from __future__ import annotations

from datetime import datetime, timezone

from northstar_trend_carry.continuous import (
    build_research_continuous_series,
    executable_contract_state,
    representations_are_separate,
)
from northstar_trend_carry.fixtures import synthetic_futures_chain
from northstar_trend_carry.momentum import evaluate_asset_trend


def test_continuous_and_executable_are_separate_types():
    chain = synthetic_futures_chain(root="ES", curve="contango")
    as_of = datetime(2024, 3, 1, tzinfo=timezone.utc)
    continuous = build_research_continuous_series(chain, as_of=as_of, method="ratio")
    executable = executable_contract_state(chain, as_of=as_of)
    assert representations_are_separate(continuous, executable)
    assert continuous.not_executable_pnl is True
    assert executable.not_research_continuous is True
    assert "CONTINUOUS" not in (executable.selected_contract or "")
    payload_c = continuous.to_dict()
    payload_e = executable.to_dict()
    assert payload_c["is_order"] is False
    assert payload_e["is_live_futures_execution"] is False
    assert "prices" in payload_c
    assert "selected_contract" in payload_e
    assert "selected_contract" not in payload_c


def test_continuous_series_has_no_lookahead_across_roll_or_as_of():
    chain = synthetic_futures_chain(
        root="ES",
        curve="contango",
        n_sessions=90,
        include_future_quotes=True,
    )
    as_of = datetime(2024, 2, 15, tzinfo=timezone.utc)
    series = build_research_continuous_series(chain, as_of=as_of, method="ratio")
    assert series.timestamps
    assert all(t <= as_of for t in series.timestamps)
    # Lookahead quotes were 10x; continuous prices must remain ordinary.
    assert max(series.prices) < 250.0
    assert any(f.code == "lookahead_blocked" for f in series.quality_flags)


def test_ratio_back_adjust_records_roll_events_without_future_fills():
    chain = synthetic_futures_chain(root="ES", curve="contango", n_sessions=100)
    as_of = datetime(2024, 3, 20, tzinfo=timezone.utc)
    series = build_research_continuous_series(chain, as_of=as_of, method="ratio", roll_lead_days=5)
    # Depending on expiries, rolls may or may not fire; prices must be finite either way.
    assert series.prices
    assert all(p > 0 for p in series.prices)
    for event in series.roll_events:
        assert event.timestamp <= as_of
        assert event.method == "ratio"
        assert event.from_contract != event.to_contract


def test_stitched_front_does_not_rewrite_history():
    chain = synthetic_futures_chain(root="ES", curve="contango", n_sessions=80)
    as_of = datetime(2024, 3, 1, tzinfo=timezone.utc)
    stitched = build_research_continuous_series(chain, as_of=as_of, method="stitched_front")
    assert stitched.roll_events == ()
    assert stitched.prices


def test_research_continuous_can_feed_trend_without_being_an_order():
    chain = synthetic_futures_chain(root="ES", curve="backwardation", n_sessions=120)
    as_of = datetime(2024, 4, 1, tzinfo=timezone.utc)
    continuous = build_research_continuous_series(chain, as_of=as_of, method="difference")
    px = continuous.to_price_series()
    assert px.asset_class == "futures_research_continuous"
    # Short sample relative to 12m is OK; ensemble may be unusable, but must not be an order.
    signal = evaluate_asset_trend(px)
    assert signal.to_dict()["is_order"] is False
    assert signal.to_dict()["activates_production_signal"] is False


def test_empty_pit_continuous_fails_closed():
    chain = synthetic_futures_chain(root="ES", curve="contango")
    too_early = datetime(2019, 1, 1, tzinfo=timezone.utc)
    series = build_research_continuous_series(chain, as_of=too_early)
    assert series.prices == ()
    assert any(f.level.value == "fail" for f in series.quality_flags)
