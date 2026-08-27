from __future__ import annotations

from datetime import datetime, timezone

from northstar_diagnostics.adf import adf_stationarity
from northstar_diagnostics.efr import FrictionInputs, edge_to_friction_ratio
from northstar_diagnostics.quality import QualityLevel
from northstar_diagnostics.schema import SCHEMA_VERSION

REQUIRED_KEYS = {
    "diagnostic_id",
    "name",
    "schema_version",
    "package_version",
    "library_versions",
    "computed_at",
    "as_of",
    "sample",
    "method",
    "parameters",
    "statistics",
    "pvalue",
    "critical_values",
    "hypotheses",
    "assumptions",
    "quality_flags",
    "interpretation",
    "notes",
    "details",
    "is_usable",
}

SAMPLE_KEYS = {
    "n_obs_input",
    "n_obs_used",
    "start_index",
    "end_index",
    "start_timestamp",
    "end_timestamp",
    "frequency",
    "dropped_missing",
    "as_of_index",
}


def test_result_schema_is_complete_and_jsonable():
    frozen = datetime(2026, 8, 26, tzinfo=timezone.utc)
    result = adf_stationarity(
        [0.1, -0.2, 0.05, 0.0, -0.1] * 10,
        computed_at=frozen,
        min_obs=20,
    )
    payload = result.to_dict()
    assert set(payload) >= REQUIRED_KEYS
    assert set(payload["sample"]) >= SAMPLE_KEYS
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["computed_at"].startswith("2026-08-26")
    assert "numpy" in payload["library_versions"]
    assert "statsmodels" in payload["library_versions"]
    assert payload["assumptions"]
    assert payload["quality_flags"]


def test_failed_result_still_exposes_schema():
    result = edge_to_friction_ratio(
        expected_gross_edge=0.01,
        friction=FrictionInputs(),  # total 0
    )
    payload = result.to_dict()
    assert payload["is_usable"] is False
    assert payload["interpretation"] == "not_computed"
    assert any(f["level"] == QualityLevel.FAIL.value for f in payload["quality_flags"])
    assert set(payload) >= REQUIRED_KEYS
