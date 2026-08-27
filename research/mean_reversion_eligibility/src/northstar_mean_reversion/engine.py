"""Deterministic mean-reversion eligibility engine (research / shadow only).

Formation/eligibility is evaluated first. Residual z-score entry timing is a
separate shadow step and cannot make an ineligible candidate eligible.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

import numpy as np

from northstar_diagnostics.adf import adf_stationarity
from northstar_diagnostics.cadf import cadf_cointegration
from northstar_diagnostics.efr import edge_to_friction_ratio
from northstar_diagnostics.half_life import mean_reversion_half_life
from northstar_diagnostics.johansen import johansen_cointegration
from northstar_diagnostics.quality import QualityCode
from northstar_diagnostics.rolling import rolling_parameter_stability
from northstar_diagnostics.schema import DiagnosticResult
from northstar_diagnostics.series import (
    length_mismatch_flag,
    prepare_panel,
)
from northstar_diagnostics.structural_break import (
    CUSUMOLSBreakDetector,
    ChowBreakDetector,
    detect_structural_break,
)

from northstar_mean_reversion.events import EventVetoFlags
from northstar_mean_reversion.reasons import EligibilityReasonCode
from northstar_mean_reversion.residual import (
    ResidualFit,
    fit_basket_residual,
    fit_pair_residual,
    residual_summary,
    rolling_hedge_relative_std,
    rolling_spread_vol_cv,
)
from northstar_mean_reversion.types import (
    PACKAGE_VERSION,
    SCHEMA_VERSION,
    EligibilityDecision,
    GateResult,
    MeanReversionEligibilityConfig,
    decision_status,
)
from northstar_mean_reversion.universe import (
    EconomicCandidate,
    EconomicCandidateUniverse,
    validate_economic_candidate,
)

ENGINE_NOTES = (
    "Stage 2 mean-reversion eligibility is research/shadow evidence only.",
    "This function does not place orders, call a broker, or change paper positions.",
    "Residual z-score thresholds are not applied here; see evaluate_shadow_entry.",
    "A collapsing or oversold series is not eligible merely because it is far from a mean.",
)


def evaluate_universe(
    universe: EconomicCandidateUniverse,
    *,
    config: MeanReversionEligibilityConfig | None = None,
    computed_at: datetime | None = None,
) -> tuple[EligibilityDecision, ...]:
    config = config or MeanReversionEligibilityConfig()
    return tuple(
        evaluate_candidate(candidate, config=config, computed_at=computed_at)
        for candidate in universe.candidates
    )


def evaluate_candidate(
    candidate: EconomicCandidate,
    *,
    config: MeanReversionEligibilityConfig | None = None,
    computed_at: datetime | None = None,
) -> EligibilityDecision:
    """Run formation gates. Does not emit an entry signal."""

    config = config or MeanReversionEligibilityConfig()
    computed_at = computed_at or datetime.now(timezone.utc)
    gates: list[GateResult] = []
    diagnostics: dict[str, DiagnosticResult] = {}

    universe_issues = validate_economic_candidate(candidate)
    if universe_issues:
        for issue in universe_issues:
            gates.append(
                GateResult(
                    gate_id="economic_universe",
                    passed=False,
                    reason_code=issue.reason_code,
                    message=issue.message,
                    evidence={"relationship_kind": str(candidate.relationship_kind)},
                )
            )
    else:
        gates.append(
            GateResult(
                gate_id="economic_universe",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="Caller declared an economic relationship for this candidate",
                evidence={
                    "relationship_kind": str(candidate.relationship_kind),
                    "relationship_rationale": candidate.relationship_rationale,
                    "n_legs": len(candidate.symbols),
                },
            )
        )

    _evaluate_event_flags(candidate, gates)
    _evaluate_liquidity(candidate, config, gates)
    _evaluate_efr(candidate, config, computed_at, gates, diagnostics)

    fit: ResidualFit | None = None
    data_ok = not any(
        gate.reason_code
        in {
            EligibilityReasonCode.MISSING_ECONOMIC_RELATIONSHIP,
            EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
            EligibilityReasonCode.INSUFFICIENT_LEGS,
            EligibilityReasonCode.MISSING_OR_INVALID_DATA,
        }
        and not gate.passed
        for gate in gates
    )

    if data_ok:
        fit = _evaluate_statistical_gates(
            candidate, config, computed_at, gates, diagnostics
        )
    else:
        gates.append(
            GateResult(
                gate_id="statistical_formation",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                message="Statistical formation skipped because universe/data identity failed",
                evidence={},
            )
        )

    failures = tuple(
        gate.reason_code
        for gate in gates
        if not gate.passed and gate.reason_code is not EligibilityReasonCode.ELIGIBLE
    )
    status = decision_status(failures)
    eligible = status == "eligible"
    reason_codes = (
        (EligibilityReasonCode.ELIGIBLE,) if eligible else failures
    )
    as_of_ts = _as_of_timestamp(candidate, diagnostics)
    return EligibilityDecision(
        schema_version=SCHEMA_VERSION,
        package_version=PACKAGE_VERSION,
        candidate_id=candidate.candidate_id,
        candidate_kind=candidate.kind,
        symbols=tuple(candidate.symbols),
        evaluated_at=computed_at,
        as_of=as_of_ts,
        status=status,
        eligible=eligible,
        reason_codes=reason_codes,
        gates=tuple(gates),
        diagnostics=diagnostics,
        hedge_ratio=dict(fit.hedge_ratio) if fit and fit.usable else None,
        residual_summary=dict(residual_summary(fit)) if fit and fit.usable else None,
        holding_horizon=float(candidate.holding_horizon)
        if candidate.holding_horizon == candidate.holding_horizon
        else None,
        config=config.to_dict(),
        notes=ENGINE_NOTES,
    )


def _evaluate_event_flags(candidate: EconomicCandidate, gates: list[GateResult]) -> None:
    flags = list(_iter_event_flags(candidate))
    if not flags:
        gates.append(
            GateResult(
                gate_id="event_fundamental_veto",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="No caller-supplied event/fundamental veto flags",
                evidence={"flags_supplied": False},
            )
        )
        return

    fundamental = [item for item in flags if item[1].fundamental_divergence]
    events = [item for item in flags if item[1].active_event_names() and not item[1].fundamental_divergence]
    mixed_events = [
        item
        for item in flags
        if any(name != "fundamental_divergence" for name in item[1].active_event_names())
    ]
    if mixed_events:
        names = []
        for scope, payload in mixed_events:
            names.extend(f"{scope}:{name}" for name in payload.active_event_names() if name != "fundamental_divergence")
        gates.append(
            GateResult(
                gate_id="event_fundamental_veto",
                passed=False,
                reason_code=EligibilityReasonCode.EVENT_DIVERGENCE_VETO,
                message="Caller-supplied event veto flag is active",
                evidence={"active": names},
            )
        )
    if fundamental:
        gates.append(
            GateResult(
                gate_id="event_fundamental_veto",
                passed=False,
                reason_code=EligibilityReasonCode.FUNDAMENTAL_DIVERGENCE_VETO,
                message="Caller-supplied fundamental-divergence veto flag is active",
                evidence={"scopes": [scope for scope, _ in fundamental]},
            )
        )
    if not mixed_events and not fundamental:
        gates.append(
            GateResult(
                gate_id="event_fundamental_veto",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="Caller-supplied event flags are inactive",
                evidence={"flags_supplied": True},
            )
        )


def _iter_event_flags(candidate: EconomicCandidate) -> list[tuple[str, EventVetoFlags]]:
    items: list[tuple[str, EventVetoFlags]] = []
    if candidate.event_flags is not None:
        items.append(("candidate", candidate.event_flags))
    if candidate.event_flags_by_symbol:
        for symbol, payload in candidate.event_flags_by_symbol.items():
            items.append((symbol, payload))
    return items


def _evaluate_liquidity(
    candidate: EconomicCandidate,
    config: MeanReversionEligibilityConfig,
    gates: list[GateResult],
) -> None:
    snapshots = candidate.liquidity or {}
    required = config.require_liquidity_snapshot or config.require_shortable or config.min_adv is not None or config.max_spread_bps is not None
    if required:
        missing = [symbol for symbol in candidate.symbols if symbol not in snapshots]
        if missing:
            gates.append(
                GateResult(
                    gate_id="liquidity_shortability",
                    passed=False,
                    reason_code=EligibilityReasonCode.MISSING_LIQUIDITY_SNAPSHOT,
                    message=f"Liquidity/shortability snapshot missing for {missing}",
                    evidence={"missing_symbols": missing, "source": "caller_supplied"},
                )
            )
            return
    elif not snapshots:
        gates.append(
            GateResult(
                gate_id="liquidity_shortability",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="Liquidity/shortability snapshot not required by config",
                evidence={"source": "caller_supplied", "required": False},
            )
        )
        return

    eval_as_of = candidate.as_of if isinstance(candidate.as_of, datetime) else None
    liquidity_fail = False
    short_fail = False
    pit_fail = False
    invalid = False
    evidence: dict[str, Any] = {"source": "caller_supplied", "snapshots": {}}
    for symbol in candidate.symbols:
        snap = snapshots.get(symbol)
        if snap is None:
            continue
        evidence["snapshots"][symbol] = snap.to_dict()
        if snap.as_of is not None and eval_as_of is not None and snap.as_of > eval_as_of:
            pit_fail = True
        if snap.adv is not None and (snap.adv != snap.adv or snap.adv < 0):
            invalid = True
        if snap.spread_bps is not None and (snap.spread_bps != snap.spread_bps or snap.spread_bps < 0):
            invalid = True
        if config.min_adv is not None and (snap.adv is None or snap.adv < config.min_adv):
            liquidity_fail = True
        if config.max_spread_bps is not None and (
            snap.spread_bps is None or snap.spread_bps > config.max_spread_bps
        ):
            liquidity_fail = True
        if config.require_shortable and snap.shortable is False:
            short_fail = True
        if config.require_shortable and snap.locate_available is False:
            short_fail = True
        if config.require_shortable and snap.shortable is None and snap.locate_available is None:
            short_fail = True

    if pit_fail:
        gates.append(
            GateResult(
                gate_id="liquidity_shortability",
                passed=False,
                reason_code=EligibilityReasonCode.POINT_IN_TIME_VIOLATION,
                message="Liquidity snapshot as_of is after the evaluation cutoff",
                evidence=evidence,
            )
        )
    if invalid:
        gates.append(
            GateResult(
                gate_id="liquidity_shortability",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                message="Liquidity snapshot contains invalid ADV or spread values",
                evidence=evidence,
            )
        )
    if liquidity_fail:
        gates.append(
            GateResult(
                gate_id="liquidity_shortability",
                passed=False,
                reason_code=EligibilityReasonCode.INSUFFICIENT_LIQUIDITY,
                message="ADV or quoted spread fails the configured liquidity gate",
                evidence=evidence,
            )
        )
    if short_fail:
        gates.append(
            GateResult(
                gate_id="liquidity_shortability",
                passed=False,
                reason_code=EligibilityReasonCode.NOT_SHORTABLE,
                message="Caller snapshot marks a required short as not shortable/locatable",
                evidence=evidence,
            )
        )
    if not (pit_fail or invalid or liquidity_fail or short_fail):
        gates.append(
            GateResult(
                gate_id="liquidity_shortability",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="Caller-supplied liquidity/shortability snapshot passed",
                evidence=evidence,
            )
        )


def _evaluate_efr(
    candidate: EconomicCandidate,
    config: MeanReversionEligibilityConfig,
    computed_at: datetime,
    gates: list[GateResult],
    diagnostics: dict[str, DiagnosticResult],
) -> None:
    if not config.require_efr:
        gates.append(
            GateResult(
                gate_id="efr",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="EFR gate disabled in config (research only)",
                evidence={"require_efr": False},
            )
        )
        return
    if candidate.expected_gross_edge is None or candidate.friction is None:
        gates.append(
            GateResult(
                gate_id="efr",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_EFR_INPUTS,
                message="expected_gross_edge and friction are required for the cost-cushion gate",
                evidence={"has_edge": candidate.expected_gross_edge is not None, "has_friction": candidate.friction is not None},
            )
        )
        return

    as_of = candidate.as_of if isinstance(candidate.as_of, datetime) else None
    result = edge_to_friction_ratio(
        candidate.expected_gross_edge,
        candidate.friction,
        fragile_below=config.efr_min,
        as_of=as_of,
        computed_at=computed_at,
    )
    diagnostics["efr"] = result
    if not result.is_usable:
        gates.append(
            GateResult(
                gate_id="efr",
                passed=False,
                reason_code=EligibilityReasonCode.INVALID_FRICTION,
                message="EFR inputs failed Stage 1 quality checks",
                evidence={"quality_flags": [flag.to_dict() for flag in result.quality_flags]},
            )
        )
        return
    efr = result.statistics.get("efr")
    efr_value = float(efr) if isinstance(efr, (int, float)) else float("nan")
    if not np.isfinite(efr_value) or efr_value < config.efr_min:
        gates.append(
            GateResult(
                gate_id="efr",
                passed=False,
                reason_code=EligibilityReasonCode.INSUFFICIENT_EFR,
                message=f"EFR {efr_value} is below cost-cushion minimum {config.efr_min}",
                evidence={"efr": efr_value, "efr_min": config.efr_min},
            )
        )
        return
    gates.append(
        GateResult(
            gate_id="efr",
            passed=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            message="EFR meets the configured cost-cushion gate",
            evidence={"efr": efr_value, "efr_min": config.efr_min},
        )
    )


_ALIGN_QUALITY_CODES = frozenset(
    {
        QualityCode.LENGTH_MISMATCH,
        QualityCode.TIMESTAMP_MISMATCH,
    }
)
_PIT_QUALITY_CODES = frozenset(
    {
        QualityCode.UNSORTED_TIMESTAMPS,
        QualityCode.MISSING_TIMESTAMPS,
        QualityCode.POINT_IN_TIME_SLICE,
    }
)
_INVALID_QUALITY_CODES = frozenset(
    {
        QualityCode.MISSING_DATA,
        QualityCode.NON_FINITE,
        QualityCode.INTERIOR_MISSING,
        QualityCode.CONSTANT_SERIES,
        QualityCode.NEAR_SINGULAR,
        QualityCode.COLLINEAR_SERIES,
        QualityCode.INSUFFICIENT_RANK,
        QualityCode.DEGENERATE_VARIANCE,
        QualityCode.INVALID_INPUT,
    }
)


def _market_data_reason(flags: tuple) -> EligibilityReasonCode:
    codes = {flag.code for flag in flags}
    if codes & _ALIGN_QUALITY_CODES:
        return EligibilityReasonCode.MISALIGNED_INPUTS
    if codes & _INVALID_QUALITY_CODES:
        return EligibilityReasonCode.MISSING_OR_INVALID_DATA
    if codes & _PIT_QUALITY_CODES:
        return EligibilityReasonCode.POINT_IN_TIME_VIOLATION
    if QualityCode.SHORT_SAMPLE in codes:
        return EligibilityReasonCode.SHORT_SAMPLE
    return EligibilityReasonCode.MISSING_OR_INVALID_DATA


def _aligned_leg_matrix(
    candidate: EconomicCandidate,
    gates: list[GateResult],
) -> np.ndarray | None:
    """Assemble equal-length legs. Never truncate a shorter series to fit."""

    columns: list[np.ndarray] = []
    lengths: list[int] = []
    for symbol in candidate.symbols:
        arr = np.asarray(candidate.legs[symbol], dtype=float).reshape(-1)
        columns.append(arr)
        lengths.append(int(arr.size))
    if not columns:
        gates.append(
            GateResult(
                gate_id="market_data",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                message="Candidate has no price legs",
                evidence={},
            )
        )
        return None
    for length in lengths[1:]:
        mismatch = length_mismatch_flag(lengths[0], length, what="candidate legs")
        if mismatch is not None:
            gates.append(
                GateResult(
                    gate_id="market_data",
                    passed=False,
                    reason_code=EligibilityReasonCode.MISALIGNED_INPUTS,
                    message=mismatch.message,
                    evidence={
                        "leg_lengths": dict(zip(candidate.symbols, lengths)),
                        "quality_flags": [mismatch.to_dict()],
                    },
                )
            )
            return None
    if candidate.timestamps is not None:
        n_ts = len(candidate.timestamps)
        if n_ts != lengths[0]:
            mismatch = length_mismatch_flag(lengths[0], n_ts, what="price legs and timestamps")
            gates.append(
                GateResult(
                    gate_id="market_data",
                    passed=False,
                    reason_code=EligibilityReasonCode.MISALIGNED_INPUTS,
                    message=(
                        mismatch.message
                        if mismatch is not None
                        else "timestamps length does not match price legs"
                    ),
                    evidence={"n_obs": lengths[0], "n_timestamps": n_ts},
                )
            )
            return None
    return np.column_stack(columns)


def _evaluate_statistical_gates(
    candidate: EconomicCandidate,
    config: MeanReversionEligibilityConfig,
    computed_at: datetime,
    gates: list[GateResult],
    diagnostics: dict[str, DiagnosticResult],
) -> ResidualFit | None:
    symbols = tuple(candidate.symbols)
    aligned = _aligned_leg_matrix(candidate, gates)
    if aligned is None:
        return None
    try:
        panel, prepared = prepare_panel(
            aligned,
            timestamps=candidate.timestamps,
            as_of=candidate.as_of,
            min_obs=config.min_obs,
            frequency=config.frequency,
        )
    except Exception as exc:  # noqa: BLE001
        gates.append(
            GateResult(
                gate_id="market_data",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                message=f"Failed to assemble point-in-time panel: {exc}",
                evidence={},
            )
        )
        return None

    if panel is None or not prepared.usable:
        fail_code = _market_data_reason(prepared.flags)
        gates.append(
            GateResult(
                gate_id="market_data",
                passed=False,
                reason_code=fail_code,
                message="Point-in-time series failed Stage 1 quality checks",
                evidence={"quality_flags": [flag.to_dict() for flag in prepared.flags]},
            )
        )
        return None

    gates.append(
        GateResult(
            gate_id="market_data",
            passed=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            message="Point-in-time panel is usable",
            evidence={"n_obs_used": prepared.sample.n_obs_used, "n_legs": panel.shape[1]},
        )
    )

    # Panel is already sliced to the point-in-time cutoff. Do not pass the
    # original as_of into Stage 1 again (that would re-slice a shorter array).
    sliced_ts = prepared.timestamps
    common = {
        "timestamps": sliced_ts,
        "as_of": None,
        "min_obs": config.min_obs,
        "frequency": config.frequency,
        "computed_at": computed_at,
    }

    fit: ResidualFit
    if len(symbols) == 2:
        cadf = cadf_cointegration(panel[:, 0], panel[:, 1], **common)
        diagnostics["cadf"] = cadf
        _record_cadf_gate(cadf, config, gates)
        _record_broken_cointegration_gate(panel[:, 0], panel[:, 1], config, computed_at, gates, diagnostics)
        fit = fit_pair_residual(panel[:, 0], panel[:, 1], symbols)
        rolling = rolling_parameter_stability(
            panel[:, 0],
            panel[:, 1],
            window=config.rolling_window,
            step=config.rolling_step,
            **common,
        )
        diagnostics["rolling_hedge"] = rolling
        rel = rolling.statistics.get("beta_relative_std") if rolling.is_usable else None
        hedge_stats = {
            "beta_relative_std": float(rel) if isinstance(rel, (int, float)) else None,
            "n_usable_windows": rolling.statistics.get("n_usable_windows"),
        }
    else:
        johansen = johansen_cointegration(panel, det_order=0, k_ar_diff=1, **common)
        diagnostics["johansen"] = johansen
        _record_johansen_gate(johansen, config, gates)
        weights = johansen.details.get("first_coint_vector") if johansen.is_usable else None
        fit = fit_basket_residual(panel, symbols, weights if isinstance(weights, list) else None)
        hedge_stats = rolling_hedge_relative_std(
            panel[:, 0], panel[:, 1:], window=config.rolling_window, step=config.rolling_step
        )

    if not fit.usable:
        gates.append(
            GateResult(
                gate_id="hedge_ratio",
                passed=False,
                reason_code=EligibilityReasonCode.HEDGE_RATIO_NOT_ESTIMATED,
                message=fit.message,
                evidence={"method": fit.method},
            )
        )
        return None

    gates.append(
        GateResult(
            gate_id="hedge_ratio",
            passed=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            message=fit.message,
            evidence={"method": fit.method, "hedge_ratio": dict(fit.hedge_ratio)},
        )
    )

    adf = adf_stationarity(fit.residual, min_obs=min(config.min_obs, 20), computed_at=computed_at)
    diagnostics["spread_adf"] = adf
    if not adf.is_usable or adf.pvalue is None or adf.pvalue >= config.adf_pvalue_max:
        gates.append(
            GateResult(
                gate_id="spread_stationarity",
                passed=False,
                reason_code=EligibilityReasonCode.SPREAD_NOT_STATIONARY,
                message="Spread/residual failed the ADF stationarity requirement",
                evidence={"pvalue": adf.pvalue, "usable": adf.is_usable},
            )
        )
    else:
        gates.append(
            GateResult(
                gate_id="spread_stationarity",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="Spread/residual ADF rejected a unit root at the configured threshold",
                evidence={"pvalue": adf.pvalue, "adf_pvalue_max": config.adf_pvalue_max},
            )
        )

    _record_hedge_stability(hedge_stats, config, gates)

    vol = rolling_spread_vol_cv(fit.residual, config.rolling_window, config.rolling_step)
    cv = vol.get("residual_vol_cv")
    if cv is None:
        gates.append(
            GateResult(
                gate_id="spread_vol_stability",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                message="Rolling spread-volatility could not be estimated",
                evidence=vol,
            )
        )
    elif float(cv) > config.spread_vol_cv_max:
        gates.append(
            GateResult(
                gate_id="spread_vol_stability",
                passed=False,
                reason_code=EligibilityReasonCode.UNSTABLE_SPREAD_VOLATILITY,
                message=f"Rolling spread-vol CV {cv} exceeds max {config.spread_vol_cv_max}",
                evidence=vol,
            )
        )
    else:
        gates.append(
            GateResult(
                gate_id="spread_vol_stability",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="Rolling spread-volatility is within the configured band",
                evidence=vol,
            )
        )

    hl = mean_reversion_half_life(fit.residual, min_obs=min(config.min_obs, 20), computed_at=computed_at)
    diagnostics["half_life"] = hl
    _record_half_life_gate(hl, candidate.holding_horizon, config, gates)

    brk = _run_structural_break(fit.residual, config, computed_at)
    diagnostics["structural_break"] = brk
    break_detected = bool(brk.details.get("break_detected")) if brk.is_usable else False
    if not brk.is_usable:
        gates.append(
            GateResult(
                gate_id="structural_break",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                message="Structural-break diagnostic was not usable",
                evidence={"quality_flags": [flag.to_dict() for flag in brk.quality_flags]},
            )
        )
    elif break_detected:
        gates.append(
            GateResult(
                gate_id="structural_break",
                passed=False,
                reason_code=EligibilityReasonCode.STRUCTURAL_BREAK_VETO,
                message="Structural-break detector vetoed this residual/spread",
                evidence={
                    "method": config.structural_break_method,
                    "break_detected": True,
                    "pvalue": brk.pvalue,
                },
            )
        )
    else:
        gates.append(
            GateResult(
                gate_id="structural_break",
                passed=True,
                reason_code=EligibilityReasonCode.ELIGIBLE,
                message="No structural-break veto on the residual/spread",
                evidence={"method": config.structural_break_method, "break_detected": False},
            )
        )
    return fit


def _run_structural_break(
    residual: np.ndarray,
    config: MeanReversionEligibilityConfig,
    computed_at: datetime,
) -> DiagnosticResult:
    """Dispatch to Stage 1 detectors, forwarding the configured significance."""

    kwargs = {
        "min_obs": min(config.min_obs, 30),
        "computed_at": computed_at,
        "significance": config.structural_break_significance,
    }
    if config.structural_break_method == "cusum_ols_resid":
        return CUSUMOLSBreakDetector().detect(residual, **kwargs)
    if config.structural_break_method == "chow_ols":
        return ChowBreakDetector().detect(residual, **kwargs)
    return detect_structural_break(
        residual,
        method=config.structural_break_method,
        min_obs=min(config.min_obs, 30),
        computed_at=computed_at,
    )


def _record_cadf_gate(
    cadf: DiagnosticResult,
    config: MeanReversionEligibilityConfig,
    gates: list[GateResult],
) -> None:
    if not cadf.is_usable:
        codes = {flag.code for flag in cadf.quality_flags}
        if codes & _ALIGN_QUALITY_CODES:
            reason = EligibilityReasonCode.MISALIGNED_INPUTS
            message = "CADF refused misaligned or unequal-length inputs"
        else:
            reason = EligibilityReasonCode.MISSING_OR_INVALID_DATA
            message = "CADF diagnostic was not usable"
        gates.append(
            GateResult(
                gate_id="cointegration",
                passed=False,
                reason_code=reason,
                message=message,
                evidence={"quality_flags": [flag.to_dict() for flag in cadf.quality_flags]},
            )
        )
        return
    pvalue = cadf.pvalue
    if pvalue is None or pvalue >= config.cadf_pvalue_max:
        gates.append(
            GateResult(
                gate_id="cointegration",
                passed=False,
                reason_code=EligibilityReasonCode.CADF_NOT_COINTEGRATED,
                message="CADF failed to reject no-cointegration at the configured threshold",
                evidence={"pvalue": pvalue, "cadf_pvalue_max": config.cadf_pvalue_max},
            )
        )
        return
    gates.append(
        GateResult(
            gate_id="cointegration",
            passed=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            message="CADF residual cointegration evidence passed",
            evidence={"pvalue": pvalue, "cadf_pvalue_max": config.cadf_pvalue_max},
        )
    )


def _record_broken_cointegration_gate(
    y: np.ndarray,
    x: np.ndarray,
    config: MeanReversionEligibilityConfig,
    computed_at: datetime,
    gates: list[GateResult],
    diagnostics: dict[str, DiagnosticResult],
) -> None:
    """Flag a relation that held in the first half and failed in the second."""

    n = min(y.size, x.size)
    split = n // 2
    half_min = max(20, min(config.min_obs, split) // 2)
    if split < half_min or (n - split) < half_min:
        return
    first = cadf_cointegration(
        y[:split],
        x[:split],
        min_obs=half_min,
        computed_at=computed_at,
    )
    last = cadf_cointegration(
        y[split:],
        x[split:],
        min_obs=half_min,
        computed_at=computed_at,
    )
    diagnostics["cadf_first_half"] = first
    diagnostics["cadf_second_half"] = last
    first_ok = first.is_usable and first.pvalue is not None and first.pvalue < config.cadf_pvalue_max
    last_ok = last.is_usable and last.pvalue is not None and last.pvalue < config.cadf_pvalue_max
    if first_ok and not last_ok:
        gates.append(
            GateResult(
                gate_id="cointegration_stability",
                passed=False,
                reason_code=EligibilityReasonCode.BROKEN_COINTEGRATION,
                message="CADF passed in the first half and failed in the second half",
                evidence={
                    "first_half_pvalue": first.pvalue,
                    "second_half_pvalue": last.pvalue,
                },
            )
        )


def _record_johansen_gate(
    johansen: DiagnosticResult,
    config: MeanReversionEligibilityConfig,
    gates: list[GateResult],
) -> None:
    if not johansen.is_usable:
        gates.append(
            GateResult(
                gate_id="cointegration",
                passed=False,
                reason_code=EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                message="Johansen diagnostic was not usable",
                evidence={"quality_flags": [flag.to_dict() for flag in johansen.quality_flags]},
            )
        )
        return
    rank = johansen.statistics.get("suggested_rank_trace_5pct")
    rank_i = int(rank) if isinstance(rank, (int, float)) else 0
    if rank_i < config.johansen_min_rank:
        gates.append(
            GateResult(
                gate_id="cointegration",
                passed=False,
                reason_code=EligibilityReasonCode.JOHANSEN_RANK_ZERO,
                message="Johansen trace test does not support the required cointegration rank",
                evidence={"suggested_rank_trace_5pct": rank_i, "johansen_min_rank": config.johansen_min_rank},
            )
        )
        return
    gates.append(
        GateResult(
            gate_id="cointegration",
            passed=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            message="Johansen basket cointegration evidence passed",
            evidence={"suggested_rank_trace_5pct": rank_i, "johansen_min_rank": config.johansen_min_rank},
        )
    )


def _record_hedge_stability(
    stats: Mapping[str, Any],
    config: MeanReversionEligibilityConfig,
    gates: list[GateResult],
) -> None:
    rel = stats.get("beta_relative_std")
    if rel is None:
        gates.append(
            GateResult(
                gate_id="hedge_stability",
                passed=False,
                reason_code=EligibilityReasonCode.UNSTABLE_HEDGE_RATIO,
                message="Rolling hedge-ratio stability could not be estimated",
                evidence=dict(stats),
            )
        )
        return
    if float(rel) > config.hedge_beta_relative_std_max:
        gates.append(
            GateResult(
                gate_id="hedge_stability",
                passed=False,
                reason_code=EligibilityReasonCode.UNSTABLE_HEDGE_RATIO,
                message=(
                    f"Rolling hedge-ratio relative std {float(rel)} exceeds "
                    f"max {config.hedge_beta_relative_std_max}"
                ),
                evidence=dict(stats),
            )
        )
        return
    gates.append(
        GateResult(
            gate_id="hedge_stability",
            passed=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            message="Rolling hedge-ratio stability is within the configured band",
            evidence=dict(stats),
        )
    )


def _record_half_life_gate(
    hl: DiagnosticResult,
    holding_horizon: float,
    config: MeanReversionEligibilityConfig,
    gates: list[GateResult],
) -> None:
    value = hl.statistics.get("half_life") if hl.is_usable else None
    if not isinstance(value, (int, float)) or not np.isfinite(float(value)) or float(value) <= 0:
        gates.append(
            GateResult(
                gate_id="half_life",
                passed=False,
                reason_code=EligibilityReasonCode.HALF_LIFE_UNDEFINED,
                message="AR(1) half-life is undefined or not mean-reverting on this residual",
                evidence={"half_life": value, "usable": hl.is_usable},
            )
        )
        return
    half_life = float(value)
    lo = float(holding_horizon) * float(config.half_life_min_fraction_of_horizon)
    hi = float(holding_horizon) * float(config.half_life_max_multiple_of_horizon)
    if half_life < lo or half_life > hi:
        gates.append(
            GateResult(
                gate_id="half_life",
                passed=False,
                reason_code=EligibilityReasonCode.HALF_LIFE_MISMATCH,
                message=(
                    f"Half-life {half_life:.4g} is outside [{lo:.4g}, {hi:.4g}] "
                    f"for holding_horizon={holding_horizon}"
                ),
                evidence={
                    "half_life": half_life,
                    "holding_horizon": float(holding_horizon),
                    "min_half_life": lo,
                    "max_half_life": hi,
                },
            )
        )
        return
    gates.append(
        GateResult(
            gate_id="half_life",
            passed=True,
            reason_code=EligibilityReasonCode.ELIGIBLE,
            message="Half-life is compatible with the requested holding horizon",
            evidence={
                "half_life": half_life,
                "holding_horizon": float(holding_horizon),
                "min_half_life": lo,
                "max_half_life": hi,
            },
        )
    )


def _as_of_timestamp(
    candidate: EconomicCandidate,
    diagnostics: Mapping[str, DiagnosticResult],
) -> datetime | None:
    if isinstance(candidate.as_of, datetime):
        return candidate.as_of
    for result in diagnostics.values():
        if result.as_of is not None:
            return result.as_of
    return None
