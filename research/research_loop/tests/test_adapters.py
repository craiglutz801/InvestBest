from __future__ import annotations

from northstar_research_loop.adapters.discovery import NATIVE_MODULES, discover_all, discover_stage
from northstar_research_loop.adapters.stage2 import Stage2EligibilityAdapter
from northstar_research_loop.adapters.stage3 import Stage3TrendCarryAdapter
from northstar_research_loop.adapters.stage5 import Stage5RobustnessAdapter, Stage5SizingAdapter
from northstar_research_loop.contracts import DiagnosticBundle
from northstar_research_loop.native_evidence import promotion_bundle


def test_all_five_stages_are_native_on_integration_branch():
    snapshot = discover_all()
    for stage, name in NATIVE_MODULES.items():
        found = snapshot[stage]
        assert found.available is True
        assert found.adapter_mode == "native"
        assert found.module_name == name
        assert discover_stage(stage).adapter_mode != "synthetic_fail_closed"
        assert discover_stage(stage).adapter_mode != "missing"


def test_eligibility_does_not_treat_zscore_as_formation():
    diagnostics = DiagnosticBundle(
        usable=False,
        required_property_present=False,
        reason_codes=("diag.required_property_absent",),
        diagnostic_ids=("cadf",),
        efr=4.0,
        efr_fragile=False,
        break_detected=False,
    )
    decision = Stage2EligibilityAdapter().evaluate(
        diagnostics, {"zscore": -3.5, "family": "mean_reversion"}
    )
    assert decision.eligible is False
    assert "elig.zscore_ignored_before_eligibility" in decision.reason_codes
    assert decision.zscore_after_eligibility is None
    assert decision.source_package == "northstar_mean_reversion"


def test_native_promotion_rejects_overfit_and_kelly_is_a_ceiling():
    evidence, rets, cfg = promotion_bundle(experiment_id="adapter-overfit", overfit=True)
    robustness = Stage5RobustnessAdapter().evaluate(
        {"promotion_evidence": evidence, "promotion_config": cfg}
    )
    assert robustness.passed is False
    assert robustness.source_package == "northstar_promotion"
    assert robustness.details.get("self_promotes_to_live") is False

    sizing = Stage5SizingAdapter().evaluate(
        {
            "sizing_returns": rets,
            "sizing_caps": {
                "risk_governor_cap": 0.1,
                "hard_leverage_cap": 0.1,
                "health_advisory_multiplier": 1.0,
            },
        }
    )
    assert sizing.fractional_kelly_ceiling <= 0.1
    assert sizing.subordinate_to_risk_governor is True
    assert sizing.source_package == "northstar_promotion"


def test_health_multiplier_is_applied_once_not_squared():
    _, rets, _ = promotion_bundle(experiment_id="adapter-health-once", overfit=False)
    caps = {
        "risk_governor_cap": 0.5,
        "hard_leverage_cap": 1.0,
        "concentration_max_weight": 1.0,
    }
    full = Stage5SizingAdapter().evaluate(
        {"sizing_returns": rets, "sizing_caps": {**caps, "health_advisory_multiplier": 1.0}}
    )
    half = Stage5SizingAdapter().evaluate(
        {"sizing_returns": rets, "sizing_caps": {**caps, "health_advisory_multiplier": 0.5}}
    )
    assert full.fractional_kelly_ceiling > 0
    expected = 0.5 * full.fractional_kelly_ceiling
    assert abs(half.fractional_kelly_ceiling - expected) < 1e-12
    squared = 0.25 * full.fractional_kelly_ceiling
    assert abs(half.fractional_kelly_ceiling - squared) > 1e-9
    assert half.applied_caps.get("health_applied_once") == 1.0


def test_missing_risk_governor_cap_cannot_yield_positive_sizing():
    _, rets, _ = promotion_bundle(experiment_id="adapter-missing-governor", overfit=False)
    sizing = Stage5SizingAdapter().evaluate(
        {
            "sizing_returns": rets,
            "sizing_caps": {"hard_leverage_cap": 0.5, "health_advisory_multiplier": 1.0},
        }
    )
    assert sizing.fractional_kelly_ceiling == 0.0
    assert "size.missing_risk_governor_cap_fail_closed" in sizing.reason_codes
    assert sizing.subordinate_to_risk_governor is True

    empty = Stage5SizingAdapter().evaluate({"sizing_returns": rets, "sizing_caps": {}})
    assert empty.fractional_kelly_ceiling == 0.0
    assert "size.missing_risk_governor_cap_fail_closed" in empty.reason_codes


def test_trend_adapter_calls_evaluate_asset_trend_not_a_guessed_name():
    from northstar_trend_carry.fixtures import uptrend_series

    ctx = Stage3TrendCarryAdapter().evaluate(
        {
            "family": "trend",
            "price_series": uptrend_series(n=400, seed=11, symbol="UP"),
            "performance_sweep": {21: 1.0, 63: 0.2},
        }
    )
    assert ctx.source_package == "northstar_trend_carry"
    assert ctx.chose_single_optimized_horizon is False
    assert "1m" in ctx.horizons or len(ctx.horizons) >= 1
