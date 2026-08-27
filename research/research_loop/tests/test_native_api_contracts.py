"""Catch renamed functions / signature drift between Chan stages."""

from __future__ import annotations

import inspect

from northstar_research_loop.adapters.discovery import NATIVE_MODULES, require_native_stages


def test_canonical_modules_are_native():
    snapshot = require_native_stages()
    for stage, name in NATIVE_MODULES.items():
        assert snapshot[stage].available
        assert snapshot[stage].adapter_mode == "native"
        assert snapshot[stage].module_name == name


def test_stage2_evaluate_candidate_signature():
    from northstar_mean_reversion import evaluate_candidate
    from northstar_mean_reversion.universe import EconomicCandidate

    sig = inspect.signature(evaluate_candidate)
    params = list(sig.parameters)
    assert params[0] == "candidate"
    assert sig.parameters["candidate"].annotation is EconomicCandidate or params[0] == "candidate"
    assert "config" in sig.parameters
    assert sig.parameters["config"].kind is inspect.Parameter.KEYWORD_ONLY
    assert not hasattr(evaluate_candidate, "evaluate_eligibility")


def test_stage3_evaluate_asset_trend_signature():
    from northstar_trend_carry import evaluate_asset_trend, refuse_performance_sweep_selection
    from northstar_trend_carry.series import PriceSeries

    sig = inspect.signature(evaluate_asset_trend)
    params = list(sig.parameters)
    assert params[0] == "series"
    assert "as_of" in sig.parameters
    assert sig.parameters["as_of"].kind is inspect.Parameter.KEYWORD_ONLY
    sweep = inspect.signature(refuse_performance_sweep_selection)
    assert list(sweep.parameters)[0] == "lookback_to_metric"
    assert PriceSeries is not None


def test_stage4_health_monitor_evaluate_signature():
    from northstar_edge_health import HealthMonitor
    from northstar_edge_health.evaluator import HealthMonitor as MonitorCls

    sig = inspect.signature(HealthMonitor.evaluate)
    params = list(sig.parameters)
    assert params[0] == "self"
    assert params[1] == "evidence"
    assert "identity" in sig.parameters
    assert sig.parameters["identity"].kind is inspect.Parameter.KEYWORD_ONLY
    assert MonitorCls is HealthMonitor


def test_stage5_evaluate_promotion_and_kelly_ceiling_signatures():
    import northstar_promotion as promo
    from northstar_promotion import evaluate_promotion, kelly_ceiling
    from northstar_promotion.promotion import PromotionEvidence

    assert not hasattr(promo, "evaluate_robustness")
    assert not hasattr(promo, "promotion_decision")
    promo_sig = inspect.signature(evaluate_promotion)
    params = list(promo_sig.parameters)
    assert params[0] == "evidence"
    assert promo_sig.parameters["evidence"].annotation is PromotionEvidence or params[0] == "evidence"
    kelly_sig = inspect.signature(kelly_ceiling)
    assert list(kelly_sig.parameters)[0] == "returns"
    assert "caps" in kelly_sig.parameters
    assert kelly_sig.parameters["caps"].kind is inspect.Parameter.KEYWORD_ONLY


def test_guessed_stage5_names_are_not_the_integration_path():
    from northstar_promotion import evaluate_promotion, kelly_ceiling
    from northstar_research_loop.adapters.stage5 import Stage5RobustnessAdapter, Stage5SizingAdapter

    adapter = Stage5RobustnessAdapter()
    assert adapter.evaluate_promotion is evaluate_promotion
    source = inspect.getsource(Stage5RobustnessAdapter.evaluate)
    assert "evaluate_robustness" not in source
    assert "promotion_decision" not in source
    assert "fn(evidence)" not in source
    assert "evaluate_promotion(" in source
    assert "config=" in source
    assert Stage5SizingAdapter().kelly_ceiling is kelly_ceiling
    size_src = inspect.getsource(Stage5SizingAdapter.evaluate)
    assert "kelly_ceiling(" in size_src
    assert "caps=" in size_src


def test_stage2_adapter_calls_evaluate_candidate_not_a_guessed_name():
    from northstar_mean_reversion import evaluate_candidate
    from northstar_research_loop.adapters.stage2 import Stage2EligibilityAdapter

    adapter = Stage2EligibilityAdapter()
    assert adapter.evaluate_candidate is evaluate_candidate
    source = inspect.getsource(Stage2EligibilityAdapter.evaluate)
    assert "evaluate_candidate(" in source
    assert "config=config" in source
    assert "evaluate_eligibility" not in source


def test_stage3_adapter_calls_evaluate_asset_trend_not_a_guessed_name():
    from northstar_trend_carry import evaluate_asset_trend, refuse_performance_sweep_selection
    from northstar_research_loop.adapters.stage3 import Stage3TrendCarryAdapter

    adapter = Stage3TrendCarryAdapter()
    assert adapter.evaluate_asset_trend is evaluate_asset_trend
    assert adapter.refuse_performance_sweep_selection is refuse_performance_sweep_selection
    source = inspect.getsource(Stage3TrendCarryAdapter.evaluate)
    assert "evaluate_asset_trend(" in source
    assert "refuse_performance_sweep_selection(" in source
    assert "as_of=" in source


def test_stage4_adapter_calls_health_monitor_evaluate():
    from northstar_edge_health import HealthMonitor
    from northstar_research_loop.adapters.stage4 import Stage4HealthAdapter

    adapter = Stage4HealthAdapter()
    assert adapter.HealthMonitor is HealthMonitor
    source = inspect.getsource(Stage4HealthAdapter.evaluate)
    assert "HealthMonitor" in source
    assert "identity=" in source
    assert "monitor.evaluate(" in source


def test_require_native_stages_fails_closed_when_a_package_is_missing(monkeypatch):
    import pytest

    from northstar_research_loop.adapters import discovery

    real_import = discovery.importlib.import_module

    def fake_import(name: str):
        if name == "northstar_promotion":
            raise ImportError("simulated missing Stage 5")
        return real_import(name)

    monkeypatch.setattr(discovery.importlib, "import_module", fake_import)
    with pytest.raises(discovery.NativeStageMissingError, match="northstar_promotion"):
        discovery.require_native_stages()
