"""Package exports and schema sanity."""

from __future__ import annotations

import northstar_trend_carry as m


def test_public_exports_exist():
    for name in (
        "evaluate_asset_trend",
        "evaluate_cross_asset_trend",
        "evaluate_trend_health",
        "neighboring_parameter_plateau",
        "refuse_performance_sweep_selection",
        "evaluate_carry",
        "build_research_continuous_series",
        "executable_contract_state",
        "research_edge_to_friction",
        "required_provider_fields",
        "DEFAULT_HORIZONS",
    ):
        assert hasattr(m, name)


def test_version_and_schema():
    assert m.__version__ == "0.1.0"
    assert m.SCHEMA_VERSION == "0.1.0"
