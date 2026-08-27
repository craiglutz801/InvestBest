from __future__ import annotations

from northstar_research_loop.adapters.discovery import discover_all, discover_stage
from northstar_research_loop.adapters.stage2 import Stage2EligibilityAdapter
from northstar_research_loop.adapters.stage5 import Stage5RobustnessAdapter, Stage5SizingAdapter
from northstar_research_loop.contracts import DiagnosticBundle, RobustnessDecision


def test_stage1_is_discoverable_on_stacked_branch():
    found = discover_stage(1)
    assert found.available is True
    assert found.module_name == "northstar_diagnostics"
    assert found.adapter_mode == "native"


def test_missing_later_stages_are_synthetic_fail_closed():
    snapshot = discover_all()
    # Stages 2–5 may still be in flight; adapters must not crash.
    for stage in (2, 3, 4, 5):
        assert snapshot[stage].adapter_mode in {"native", "synthetic_fail_closed"}


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


def test_overfit_and_full_kelly_are_clamped():
    robustness = Stage5RobustnessAdapter().evaluate(
        {
            "robustness": RobustnessDecision(
                passed=True,
                reason_codes=(),
                trial_count=200,
                plateau_stable=False,
                holdout_contaminated=True,
                cost_stress_failed=True,
                delay_stress_failed=False,
                concentration_flag=True,
                pbo=0.9,
                details={"concentration_veto": True},
            )
        }
    )
    assert robustness.passed is False
    assert "rob.holdout_contaminated" in robustness.reason_codes
    assert "rob.pbo_above_threshold" in robustness.reason_codes
    assert "rob.unstable_parameter_peak" in robustness.reason_codes

    sizing = Stage5SizingAdapter().evaluate(
        {
            "sizing": {
                "fractional_kelly_ceiling": 1.5,
                "applied_caps": {"hard_risk_cap": 0.1},
                "subordinate_to_risk_governor": True,
            }
        }
    )
    assert sizing.fractional_kelly_ceiling <= 0.1
    assert sizing.subordinate_to_risk_governor is True
    assert any("clamped" in code or "full_kelly" in code for code in sizing.reason_codes)


def test_trend_adapter_refuses_single_optimized_horizon():
    from northstar_research_loop.adapters.stage3 import Stage3TrendCarryAdapter

    ctx = Stage3TrendCarryAdapter().evaluate(
        {
            "family": "trend",
            "trend": {
                "usable": True,
                "horizons": ["1m", "3m", "6m", "12m"],
                "chose_single_optimized_horizon": True,
                "selected_lookback": 77,
                "reason_codes": ("trend.sweep",),
            },
        }
    )
    assert ctx.usable is False
    assert ctx.chose_single_optimized_horizon is True
    assert "trend.single_optimized_horizon_forbidden" in ctx.reason_codes
