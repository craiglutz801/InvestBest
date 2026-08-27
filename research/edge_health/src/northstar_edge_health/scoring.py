"""Deterministic instantaneous health scoring (no hysteresis)."""

from __future__ import annotations

from dataclasses import dataclass

from northstar_edge_health.config import HealthConfig, MeanReversionThresholds, TrendThresholds
from northstar_edge_health.evidence import (
    Evidence,
    MeanReversionEvidence,
    TrendEvidence,
    expansion_ratio,
    horizon_sign_agreement,
    latest_finite,
    reject_fraction,
    relative_drift,
)
from northstar_edge_health.schema import ReasonDetail
from northstar_edge_health.states import HealthState, ReasonCode, worse_state


@dataclass(frozen=True)
class InstantaneousAssessment:
    state: HealthState
    findings: tuple[ReasonDetail, ...]
    hard_pause: bool
    hard_retire: bool
    fail_closed: bool
    missing_fields: tuple[str, ...]
    invalid_fields: tuple[str, ...]


def _finding(
    code: str,
    state: HealthState,
    message: str,
    *,
    hard: bool = False,
    metric: str | None = None,
    value: float | None = None,
    threshold: float | None = None,
) -> ReasonDetail:
    return ReasonDetail(
        code=code,
        state=state,
        message=message,
        hard=hard,
        metric=metric,
        value=value,
        threshold=threshold,
    )


def _band_high_is_bad(
    *,
    value: float | None,
    degraded: float,
    paused: float,
    degraded_code: str,
    paused_code: str,
    metric: str,
    message_degraded: str,
    message_paused: str,
) -> ReasonDetail | None:
    if value is None:
        return None
    if value >= paused:
        return _finding(paused_code, HealthState.PAUSED, message_paused, metric=metric, value=value, threshold=paused)
    if value >= degraded:
        return _finding(
            degraded_code, HealthState.DEGRADED, message_degraded, metric=metric, value=value, threshold=degraded
        )
    return None


def _band_low_is_bad(
    *,
    value: float | None,
    degraded: float,
    paused: float,
    degraded_code: str,
    paused_code: str,
    metric: str,
    message_degraded: str,
    message_paused: str,
) -> ReasonDetail | None:
    if value is None:
        return None
    if value <= paused:
        return _finding(paused_code, HealthState.PAUSED, message_paused, metric=metric, value=value, threshold=paused)
    if value <= degraded:
        return _finding(
            degraded_code, HealthState.DEGRADED, message_degraded, metric=metric, value=value, threshold=degraded
        )
    return None


def _stationarity_findings(
    *,
    pvalues: tuple[float | None, ...] | None,
    reject_frac_supplied: float | None,
    alpha: float,
    fraction_degraded: float,
    fraction_paused: float,
    latest_degraded: float,
    latest_paused: float,
    family: str,
) -> list[ReasonDetail]:
    findings: list[ReasonDetail] = []
    frac = reject_frac_supplied
    if frac is None:
        frac = reject_fraction(pvalues, alpha=alpha)
    latest = latest_finite(pvalues)
    prefix = "mr.rolling_adf" if family == "adf" else "mr.rolling_cadf"
    if family == "adf":
        degraded_code = ReasonCode.MR_ROLLING_ADF_NONSTATIONARY
        paused_code = ReasonCode.MR_ROLLING_ADF_NONSTATIONARY_SEVERE
        metric_frac = "rolling_adf_reject_fraction"
        metric_p = "rolling_adf_latest_pvalue"
    else:
        degraded_code = ReasonCode.MR_ROLLING_CADF_NONSTATIONARY
        paused_code = ReasonCode.MR_ROLLING_CADF_NONSTATIONARY_SEVERE
        metric_frac = "rolling_cadf_reject_fraction"
        metric_p = "rolling_cadf_latest_pvalue"
    item = _band_low_is_bad(
        value=frac,
        degraded=fraction_degraded,
        paused=fraction_paused,
        degraded_code=degraded_code,
        paused_code=paused_code,
        metric=metric_frac,
        message_degraded=f"{prefix} reject fraction is only weakly stationary",
        message_paused=f"{prefix} reject fraction indicates persistent non-stationarity",
    )
    if item is not None:
        findings.append(item)
    if latest is not None:
        item = _band_high_is_bad(
            value=latest,
            degraded=latest_degraded,
            paused=latest_paused,
            degraded_code=degraded_code,
            paused_code=paused_code,
            metric=metric_p,
            message_degraded=f"{prefix} latest p-value fails to reject a unit root",
            message_paused=f"{prefix} latest p-value is far from stationarity",
        )
        if item is not None:
            findings.append(item)
    return findings


def score_mean_reversion(evidence: MeanReversionEvidence, config: HealthConfig) -> InstantaneousAssessment:
    thresholds: MeanReversionThresholds = config.mean_reversion
    invalid = evidence.invalid_fields()
    missing = evidence.missing_fields(
        require_cadf=config.require_cadf, require_convergence=config.require_convergence
    )
    findings: list[ReasonDetail] = []

    if not evidence.usable:
        findings.append(
            _finding(
                ReasonCode.INVALID_EVIDENCE,
                HealthState.PAUSED,
                "Caller marked mean-reversion evidence as unusable",
                hard=True,
            )
        )
    elif invalid:
        findings.append(
            _finding(
                ReasonCode.INVALID_EVIDENCE,
                HealthState.PAUSED,
                "Non-finite or illegal mean-reversion metrics: " + ", ".join(invalid),
                hard=True,
            )
        )
    elif config.fail_closed_on_missing and missing:
        findings.append(
            _finding(
                ReasonCode.MISSING_EVIDENCE,
                HealthState.PAUSED,
                "Required mean-reversion evidence missing: " + ", ".join(missing),
                hard=True,
            )
        )
    else:
        findings.extend(
            _stationarity_findings(
                pvalues=evidence.rolling_adf_pvalues,
                reject_frac_supplied=evidence.rolling_adf_reject_fraction,
                alpha=thresholds.adf_alpha,
                fraction_degraded=thresholds.adf_reject_fraction_degraded,
                fraction_paused=thresholds.adf_reject_fraction_paused,
                latest_degraded=thresholds.adf_latest_pvalue_degraded,
                latest_paused=thresholds.adf_latest_pvalue_paused,
                family="adf",
            )
        )
        if evidence.rolling_cadf_pvalues is not None or evidence.rolling_cadf_reject_fraction is not None:
            findings.extend(
                _stationarity_findings(
                    pvalues=evidence.rolling_cadf_pvalues,
                    reject_frac_supplied=evidence.rolling_cadf_reject_fraction,
                    alpha=thresholds.cadf_alpha,
                    fraction_degraded=thresholds.cadf_reject_fraction_degraded,
                    fraction_paused=thresholds.cadf_reject_fraction_paused,
                    latest_degraded=thresholds.cadf_latest_pvalue_degraded,
                    latest_paused=thresholds.cadf_latest_pvalue_paused,
                    family="cadf",
                )
            )
        if evidence.half_life is None and evidence.half_life_baseline is not None:
            findings.append(
                _finding(
                    ReasonCode.MR_HALF_LIFE_UNDEFINED,
                    HealthState.PAUSED,
                    "AR(1) half-life is undefined on the live window",
                    metric="half_life",
                )
            )
        else:
            hl_drift = (
                relative_drift(evidence.half_life, evidence.half_life_baseline)
                if evidence.half_life is not None and evidence.half_life_baseline is not None
                else None
            )
            item = _band_high_is_bad(
                value=hl_drift,
                degraded=thresholds.half_life_rel_drift_degraded,
                paused=thresholds.half_life_rel_drift_paused,
                degraded_code=ReasonCode.MR_HALF_LIFE_DRIFT,
                paused_code=ReasonCode.MR_HALF_LIFE_EXTREME_DRIFT,
                metric="half_life_relative_drift",
                message_degraded="Half-life has drifted versus formation baseline",
                message_paused="Half-life drift is extreme versus formation baseline",
            )
            if item is not None:
                findings.append(item)

        if evidence.hedge_ratio is not None and evidence.hedge_ratio_baseline is not None:
            if abs(float(evidence.hedge_ratio_baseline)) == 0.0:
                rel = None if evidence.hedge_ratio == 0.0 else float("inf")
            else:
                rel = abs(float(evidence.hedge_ratio) - float(evidence.hedge_ratio_baseline)) / abs(
                    float(evidence.hedge_ratio_baseline)
                )
            if rel == float("inf"):
                findings.append(
                    _finding(
                        ReasonCode.MR_HEDGE_RATIO_EXTREME_DRIFT,
                        HealthState.PAUSED,
                        "Hedge ratio drifted off a zero baseline",
                        metric="hedge_ratio_relative_drift",
                    )
                )
            else:
                item = _band_high_is_bad(
                    value=rel,
                    degraded=thresholds.hedge_ratio_rel_drift_degraded,
                    paused=thresholds.hedge_ratio_rel_drift_paused,
                    degraded_code=ReasonCode.MR_HEDGE_RATIO_DRIFT,
                    paused_code=ReasonCode.MR_HEDGE_RATIO_EXTREME_DRIFT,
                    metric="hedge_ratio_relative_drift",
                    message_degraded="Hedge ratio has drifted versus formation baseline",
                    message_paused="Hedge-ratio drift is extreme versus formation baseline",
                )
                if item is not None:
                    findings.append(item)

        vol_ratio = (
            expansion_ratio(evidence.residual_volatility, evidence.residual_volatility_baseline)
            if evidence.residual_volatility is not None and evidence.residual_volatility_baseline is not None
            else None
        )
        item = _band_high_is_bad(
            value=vol_ratio,
            degraded=thresholds.residual_vol_ratio_degraded,
            paused=thresholds.residual_vol_ratio_paused,
            degraded_code=ReasonCode.MR_RESIDUAL_VOL_EXPANSION,
            paused_code=ReasonCode.MR_RESIDUAL_VOL_EXTREME,
            metric="residual_vol_ratio",
            message_degraded="Residual volatility has expanded versus baseline",
            message_paused="Residual-volatility expansion is extreme",
        )
        if item is not None:
            findings.append(item)

        conv = evidence.effective_convergence()
        conv_base = evidence.effective_convergence_baseline()
        conv_ratio = expansion_ratio(conv, conv_base) if conv is not None and conv_base is not None else None
        item = _band_low_is_bad(
            value=conv_ratio,
            degraded=thresholds.convergence_ratio_degraded,
            paused=thresholds.convergence_ratio_paused,
            degraded_code=ReasonCode.MR_CONVERGENCE_COLLAPSE,
            paused_code=ReasonCode.MR_CONVERGENCE_EXTREME,
            metric="convergence_ratio",
            message_degraded="Convergence rate has collapsed versus baseline",
            message_paused="Convergence rate collapse is extreme",
        )
        if item is not None:
            findings.append(item)

        if evidence.structural_break_detected is True:
            findings.append(
                _finding(
                    ReasonCode.MR_STRUCTURAL_BREAK,
                    HealthState.PAUSED,
                    "Stage 1 structural-break flag is true; sleeve is paused",
                    hard=True,
                    metric="structural_break_detected",
                    value=1.0,
                    threshold=1.0,
                )
            )

        friction_ratio = (
            expansion_ratio(evidence.realized_friction, evidence.expected_friction)
            if evidence.realized_friction is not None and evidence.expected_friction is not None
            else None
        )
        item = _band_high_is_bad(
            value=friction_ratio,
            degraded=thresholds.friction_ratio_degraded,
            paused=thresholds.friction_ratio_paused,
            degraded_code=ReasonCode.MR_FRICTION_OVERRUN,
            paused_code=ReasonCode.MR_FRICTION_EXTREME,
            metric="friction_ratio",
            message_degraded="Realized friction overruns expected friction",
            message_paused="Realized friction is extreme versus expected friction",
        )
        if item is not None:
            findings.append(item)

        break_flag = evidence.structural_break_detected is True
        half_life_broken = (
            any(f.code in {ReasonCode.MR_HALF_LIFE_UNDEFINED, ReasonCode.MR_HALF_LIFE_EXTREME_DRIFT} for f in findings)
        )
        friction_or_vol_extreme = any(
            f.code in {ReasonCode.MR_FRICTION_EXTREME, ReasonCode.MR_RESIDUAL_VOL_EXTREME} for f in findings
        )
        if break_flag and half_life_broken and friction_or_vol_extreme:
            findings.append(
                _finding(
                    ReasonCode.MR_THESIS_BROKEN,
                    HealthState.RESEARCH_RETIRE_CANDIDATE,
                    "Combined break, half-life failure, and cost/vol extreme: research/retire candidate",
                    hard=True,
                )
            )

    return _finalize(findings, missing=missing, invalid=invalid)


def score_trend(evidence: TrendEvidence, config: HealthConfig) -> InstantaneousAssessment:
    thresholds: TrendThresholds = config.trend
    invalid = evidence.invalid_fields()
    missing = evidence.missing_fields()
    findings: list[ReasonDetail] = []

    if not evidence.usable:
        findings.append(
            _finding(
                ReasonCode.INVALID_EVIDENCE,
                HealthState.PAUSED,
                "Caller marked trend evidence as unusable",
                hard=True,
            )
        )
    elif invalid:
        findings.append(
            _finding(
                ReasonCode.INVALID_EVIDENCE,
                HealthState.PAUSED,
                "Non-finite or illegal trend metrics: " + ", ".join(invalid),
                hard=True,
            )
        )
    elif config.fail_closed_on_missing and missing:
        findings.append(
            _finding(
                ReasonCode.MISSING_EVIDENCE,
                HealthState.PAUSED,
                "Required trend evidence missing: " + ", ".join(missing),
                hard=True,
            )
        )
    else:
        agreement = horizon_sign_agreement(evidence.horizon_signs or ())
        item = _band_low_is_bad(
            value=agreement,
            degraded=thresholds.horizon_agreement_degraded,
            paused=thresholds.horizon_agreement_paused,
            degraded_code=ReasonCode.TREND_HORIZON_DISAGREEMENT,
            paused_code=ReasonCode.TREND_HORIZON_DISAGREEMENT_SEVERE,
            metric="horizon_sign_agreement",
            message_degraded="Horizon signs disagree",
            message_paused="Horizon signs are severely split",
        )
        if item is not None:
            findings.append(item)

        item = _band_low_is_bad(
            value=evidence.persistence,
            degraded=thresholds.persistence_degraded,
            paused=thresholds.persistence_paused,
            degraded_code=ReasonCode.TREND_PERSISTENCE_COLLAPSE,
            paused_code=ReasonCode.TREND_PERSISTENCE_EXTREME,
            metric="persistence",
            message_degraded="Trend persistence has collapsed",
            message_paused="Trend persistence is extremely weak",
        )
        if item is not None:
            findings.append(item)

        item = _band_high_is_bad(
            value=evidence.whipsaw_rate,
            degraded=thresholds.whipsaw_degraded,
            paused=thresholds.whipsaw_paused,
            degraded_code=ReasonCode.TREND_WHIPSAW_ELEVATED,
            paused_code=ReasonCode.TREND_WHIPSAW_EXTREME,
            metric="whipsaw_rate",
            message_degraded="Whipsaw rate is elevated",
            message_paused="Whipsaw rate is extreme",
        )
        if item is not None:
            findings.append(item)

        if evidence.volatility_shock is True:
            findings.append(
                _finding(
                    ReasonCode.TREND_VOLATILITY_SHOCK,
                    HealthState.PAUSED,
                    "Volatility shock state is active; sleeve is paused",
                    hard=True,
                    metric="volatility_shock",
                    value=1.0,
                    threshold=1.0,
                )
            )

        friction_ratio = (
            expansion_ratio(evidence.realized_implementation_cost, evidence.expected_implementation_cost)
            if evidence.realized_implementation_cost is not None
            and evidence.expected_implementation_cost is not None
            else None
        )
        item = _band_high_is_bad(
            value=friction_ratio,
            degraded=thresholds.friction_ratio_degraded,
            paused=thresholds.friction_ratio_paused,
            degraded_code=ReasonCode.TREND_FRICTION_OVERRUN,
            paused_code=ReasonCode.TREND_FRICTION_EXTREME,
            metric="implementation_cost_ratio",
            message_degraded="Realized implementation cost overruns expected cost",
            message_paused="Realized implementation cost is extreme versus expected",
        )
        if item is not None:
            findings.append(item)

        item = _band_low_is_bad(
            value=evidence.cross_market_breadth,
            degraded=thresholds.breadth_degraded,
            paused=thresholds.breadth_paused,
            degraded_code=ReasonCode.TREND_BREADTH_COLLAPSE,
            paused_code=ReasonCode.TREND_BREADTH_EXTREME,
            metric="cross_market_breadth",
            message_degraded="Cross-market breadth has collapsed",
            message_paused="Cross-market breadth is extremely narrow",
        )
        if item is not None:
            findings.append(item)

        shock = evidence.volatility_shock is True
        extreme_whipsaw = any(f.code == ReasonCode.TREND_WHIPSAW_EXTREME for f in findings)
        extreme_breadth = any(f.code == ReasonCode.TREND_BREADTH_EXTREME for f in findings)
        if shock and extreme_whipsaw and extreme_breadth:
            findings.append(
                _finding(
                    ReasonCode.TREND_THESIS_BROKEN,
                    HealthState.RESEARCH_RETIRE_CANDIDATE,
                    "Combined vol shock, extreme whipsaw, and breadth collapse: research/retire candidate",
                    hard=True,
                )
            )

    return _finalize(findings, missing=missing, invalid=invalid)


def score_evidence(evidence: Evidence, config: HealthConfig) -> InstantaneousAssessment:
    if isinstance(evidence, MeanReversionEvidence):
        return score_mean_reversion(evidence, config)
    if isinstance(evidence, TrendEvidence):
        return score_trend(evidence, config)
    raise TypeError(f"Unsupported evidence type: {type(evidence)!r}")


def _finalize(
    findings: list[ReasonDetail], *, missing: tuple[str, ...], invalid: tuple[str, ...]
) -> InstantaneousAssessment:
    state = HealthState.HEALTHY
    for item in findings:
        state = worse_state(state, item.state)
    hard_pause = any(item.hard and item.state is HealthState.PAUSED for item in findings) or any(
        item.hard and item.state is HealthState.RESEARCH_RETIRE_CANDIDATE for item in findings
    )
    hard_retire = any(item.hard and item.state is HealthState.RESEARCH_RETIRE_CANDIDATE for item in findings)
    fail_closed = any(
        item.code in {ReasonCode.MISSING_EVIDENCE, ReasonCode.INVALID_EVIDENCE, ReasonCode.FUTURE_OBSERVATION, ReasonCode.NON_MONOTONIC_HISTORY}
        for item in findings
    )
    return InstantaneousAssessment(
        state=state,
        findings=tuple(findings),
        hard_pause=hard_pause or fail_closed,
        hard_retire=hard_retire,
        fail_closed=fail_closed,
        missing_fields=missing,
        invalid_fields=invalid,
    )
