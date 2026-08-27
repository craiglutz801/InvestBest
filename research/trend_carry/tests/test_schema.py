"""Package exports and schema sanity."""

from __future__ import annotations

import inspect

import northstar_trend_carry as m


def test_public_exports_exist():
    for name in (
        "evaluate_asset_trend",
        "evaluate_cross_asset_trend",
        "evaluate_trend_health",
        "neighboring_parameter_plateau",
        "refuse_performance_sweep_selection",
        "evaluate_carry",
        "QuoteSyncConfig",
        "build_research_continuous_series",
        "executable_contract_state",
        "research_edge_to_friction",
        "required_provider_fields",
        "DEFAULT_HORIZONS",
    ):
        assert hasattr(m, name)


def test_version_and_schema():
    assert m.__version__ == "0.1.1"
    assert m.SCHEMA_VERSION == "0.1.1"


def test_stage6_native_adapter_signatures_unchanged():
    """Stage 6 harness binds evaluate_asset_trend(series, config, *, as_of=)."""

    sig = inspect.signature(m.evaluate_asset_trend)
    params = list(sig.parameters)
    assert params[0] == "series"
    assert "as_of" in sig.parameters
    assert sig.parameters["as_of"].kind is inspect.Parameter.KEYWORD_ONLY
    sweep = inspect.signature(m.refuse_performance_sweep_selection)
    assert list(sweep.parameters)[0] == "lookback_to_metric"
    assert "CarrySnapshot" in m.__all__
    assert not hasattr(m.CarrySnapshot, "estimated_roll_friction")
