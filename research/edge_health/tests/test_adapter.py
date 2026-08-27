"""Stage 1 DiagnosticResult adapter (duck-typed; real objects when available)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from northstar_edge_health import (
    HealthMonitor,
    HealthState,
    ReasonCode,
    mean_reversion_evidence_from_stage1,
)
from northstar_edge_health.adapter import extract_break_detected

from health_fixtures import MR_IDENTITY, instant_config, ts


def _result(*, usable=True, details=None, statistics=None, pvalue=None, as_of=None, flags=()):
    return SimpleNamespace(
        is_usable=usable,
        details=details or {},
        statistics=statistics or {},
        pvalue=pvalue,
        as_of=as_of,
        quality_flags=flags,
    )


def _healthy_rest(**overrides):
    payload = {
        "as_of": ts(1),
        "rolling_stationarity": _result(
            statistics={"fraction_reject_unit_root_5pct": 1.0},
            details={"windows": [{"adf_pvalue": 0.01, "half_life": 10.0}]},
        ),
        "rolling_parameter_stability": _result(details={"windows": [{"beta": 1.0, "residual_std": 0.02}]}),
        "structural_break": _result(details={"break_detected": False}),
        "half_life": _result(statistics={"half_life": 10.0}),
        "cadf": _result(pvalue=0.01),
        "formation_half_life": 10.0,
        "formation_hedge_ratio": 1.0,
        "formation_residual_vol": 0.02,
        "realized_friction": 0.001,
        "expected_friction": 0.001,
    }
    payload.update(overrides)
    return payload


def test_extract_break_detected_from_stage1_contract():
    detected = _result(details={"break_detected": True, "candidate_index": 40})
    clear = _result(details={"break_detected": False})
    unusable = _result(usable=False, details={"break_detected": True})
    assert extract_break_detected(detected) is True
    assert extract_break_detected(clear) is False
    assert extract_break_detected(unusable) is None
    assert extract_break_detected(None) is None


def test_adapter_maps_rolling_windows_and_break_flag():
    rolling = _result(
        as_of=ts(1),
        statistics={"fraction_reject_unit_root_5pct": 0.9, "half_life_median": 11.0},
        details={
            "windows": [
                {"adf_pvalue": 0.01, "half_life": 10.0},
                {"adf_pvalue": 0.02, "half_life": 11.0},
            ]
        },
    )
    params = _result(
        statistics={"beta_mean": 1.02, "residual_vol_mean": 0.021},
        details={"windows": [{"beta": 1.01, "residual_std": 0.021}]},
    )
    brk = _result(details={"break_detected": False})
    cadf = _result(pvalue=0.01, statistics={"beta_0": 1.0, "residual_std": 0.02}, details={"hedge_ratio": {"beta_0": 1.0}})
    hl = _result(statistics={"half_life": 10.5})
    evidence = mean_reversion_evidence_from_stage1(
        rolling_stationarity=rolling,
        rolling_parameter_stability=params,
        structural_break=brk,
        half_life=hl,
        cadf=cadf,
        formation_half_life=10.0,
        formation_hedge_ratio=1.0,
        formation_residual_vol=0.02,
        realized_friction=0.001,
        expected_friction=0.001,
    )
    assert evidence.source == "stage1_adapter"
    assert evidence.structural_break_detected is False
    assert evidence.rolling_adf_pvalues == (0.01, 0.02)
    assert evidence.half_life == 10.5
    assert evidence.hedge_ratio == 1.01
    snap = HealthMonitor().evaluate(evidence, identity=MR_IDENTITY)
    assert snap.state is HealthState.HEALTHY


def test_unusable_structural_break_does_not_look_healthy():
    evidence = mean_reversion_evidence_from_stage1(
        as_of=ts(1),
        rolling_stationarity=_result(
            statistics={"fraction_reject_unit_root_5pct": 1.0},
            details={"windows": [{"adf_pvalue": 0.01, "half_life": 10.0}]},
        ),
        rolling_parameter_stability=_result(details={"windows": [{"beta": 1.0, "residual_std": 0.02}]}),
        structural_break=_result(usable=False, details={"break_detected": False}),
        half_life=_result(statistics={"half_life": 10.0}),
        cadf=_result(pvalue=0.01),
        formation_half_life=10.0,
        formation_hedge_ratio=1.0,
        formation_residual_vol=0.02,
        realized_friction=0.001,
        expected_friction=0.001,
    )
    assert evidence.structural_break_detected is None
    snap = HealthMonitor().evaluate(evidence, identity=MR_IDENTITY)
    assert snap.fail_closed is True
    assert ReasonCode.MISSING_EVIDENCE in snap.reason_codes
    assert snap.state is HealthState.PAUSED


def test_adapter_break_true_pauses():
    evidence = mean_reversion_evidence_from_stage1(
        as_of=ts(1),
        rolling_stationarity=_result(
            statistics={"fraction_reject_unit_root_5pct": 1.0},
            details={"windows": [{"adf_pvalue": 0.01, "half_life": 10.0}]},
        ),
        rolling_parameter_stability=_result(details={"windows": [{"beta": 1.0, "residual_std": 0.02}]}),
        structural_break=_result(details={"break_detected": True}),
        half_life=_result(statistics={"half_life": 10.0}),
        cadf=_result(pvalue=0.01),
        formation_half_life=10.0,
        formation_hedge_ratio=1.0,
        formation_residual_vol=0.02,
        realized_friction=0.001,
        expected_friction=0.001,
    )
    snap = HealthMonitor(instant_config()).evaluate(evidence, identity=MR_IDENTITY)
    assert snap.state is HealthState.PAUSED
    assert ReasonCode.MR_STRUCTURAL_BREAK in snap.reason_codes


def test_real_stage1_diagnostic_result_if_installed():
    pytest.importorskip("northstar_diagnostics")
    from northstar_diagnostics.schema import SampleWindow, make_result

    sample = SampleWindow(
        n_obs_input=100,
        n_obs_used=100,
        start_index=0,
        end_index=99,
        start_timestamp=None,
        end_timestamp=None,
    )
    result = make_result(
        diagnostic_id="structural_break",
        name="Structural break (Chow OLS)",
        sample=sample,
        method="chow_ols",
        parameters={},
        statistics={"break_detected": 1},
        pvalue=0.01,
        interpretation="chow_reject_stability_at_candidate (break evidence only; not a trade)",
        details={"break_detected": True, "candidate_index": 40},
        as_of=ts(1),
    )
    assert extract_break_detected(result) is True
    assert result.is_usable is True


def test_real_cadf_length_mismatch_fails_closed():
    pytest.importorskip("northstar_diagnostics")
    import numpy as np
    from northstar_diagnostics.cadf import cadf_cointegration
    from northstar_diagnostics.quality import QualityCode

    rng = np.random.default_rng(21)
    y = np.cumsum(rng.normal(size=80))
    x = np.cumsum(rng.normal(size=50))
    cadf = cadf_cointegration(y, x, min_obs=30)
    assert not cadf.is_usable
    assert any(flag.code == QualityCode.LENGTH_MISMATCH for flag in cadf.quality_flags)

    evidence = mean_reversion_evidence_from_stage1(**_healthy_rest(cadf=cadf))
    assert evidence.rolling_cadf_pvalues is None
    assert "length_mismatch" in evidence.extra["unusable_stage1"]["cadf"]
    snap = HealthMonitor().evaluate(evidence, identity=MR_IDENTITY)
    assert snap.fail_closed is True
    assert ReasonCode.MISSING_EVIDENCE in snap.reason_codes
    assert snap.state is HealthState.PAUSED
    assert snap.recommended_risk_multiplier == 0.0


def test_real_cadf_timestamp_mismatch_fails_closed():
    pytest.importorskip("northstar_diagnostics")
    from datetime import timedelta

    import numpy as np
    from northstar_diagnostics.cadf import cadf_cointegration
    from northstar_diagnostics.quality import QualityCode

    rng = np.random.default_rng(22)
    y = np.cumsum(rng.normal(size=80))
    x = y + rng.normal(scale=0.2, size=80)
    ts_y = [ts(1) + timedelta(days=i) for i in range(80)]
    ts_x = [stamp + timedelta(days=3) for stamp in ts_y]
    cadf = cadf_cointegration(y, x, timestamps=ts_y, x_timestamps=ts_x, min_obs=30)
    assert not cadf.is_usable
    assert any(flag.code == QualityCode.TIMESTAMP_MISMATCH for flag in cadf.quality_flags)

    evidence = mean_reversion_evidence_from_stage1(**_healthy_rest(cadf=cadf))
    assert evidence.rolling_cadf_pvalues is None
    assert "timestamp_mismatch" in evidence.extra["unusable_stage1"]["cadf"]
    snap = HealthMonitor().evaluate(evidence, identity=MR_IDENTITY)
    assert snap.fail_closed is True
    assert snap.state is HealthState.PAUSED


def test_real_rolling_pair_length_mismatch_fails_closed():
    pytest.importorskip("northstar_diagnostics")
    import numpy as np
    from northstar_diagnostics.quality import QualityCode
    from northstar_diagnostics.rolling import rolling_parameter_stability

    rng = np.random.default_rng(23)
    y = np.cumsum(rng.normal(size=80))
    x = np.cumsum(rng.normal(size=40))
    rolling = rolling_parameter_stability(y, x, window=30, step=5, min_obs=20)
    assert not rolling.is_usable
    assert any(flag.code == QualityCode.LENGTH_MISMATCH for flag in rolling.quality_flags)

    evidence = mean_reversion_evidence_from_stage1(
        **_healthy_rest(rolling_parameter_stability=rolling, cadf=_result(usable=False, pvalue=0.01))
    )
    assert evidence.hedge_ratio is None
    assert evidence.residual_volatility is None
    assert "length_mismatch" in evidence.extra["unusable_stage1"]["rolling_parameter_stability"]
    assert "cadf" in evidence.extra["unusable_stage1"]
    snap = HealthMonitor().evaluate(evidence, identity=MR_IDENTITY)
    assert snap.fail_closed is True
    assert ReasonCode.MISSING_EVIDENCE in snap.reason_codes
    assert snap.state is HealthState.PAUSED
