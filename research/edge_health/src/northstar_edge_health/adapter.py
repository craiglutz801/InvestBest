"""Adapter from Stage 1 ``DiagnosticResult`` objects to Stage 4 evidence.

Stage 4 scoring does not import Stage 1 at module import time. This adapter
duck-types DiagnosticResult (attributes or mapping) so contracts stay
independently testable. When stacking on
``cursor/chan-stage1-statistical-diagnostics-fd6c``, pass real
``northstar_diagnostics`` results.

If a Stage 1 result is missing or ``is_usable`` is false, the corresponding
evidence field is left unset / unusable so the evaluator fails closed.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from northstar_edge_health.evidence import MeanReversionEvidence, is_finite_number


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _is_usable(result: Any) -> bool:
    if result is None:
        return False
    flag = _get(result, "is_usable", None)
    if flag is not None:
        return bool(flag)
    flags = _get(result, "quality_flags", ()) or ()
    for item in flags:
        level = _get(item, "level", None)
        value = level.value if hasattr(level, "value") else level
        if str(value).lower() == "fail":
            return False
    return True


def extract_break_detected(result: Any) -> bool | None:
    """Read Stage 1 structural-break contract field ``details.break_detected``."""

    if result is None or not _is_usable(result):
        return None
    details = _get(result, "details", {}) or {}
    if isinstance(details, Mapping) and "break_detected" in details:
        value = details.get("break_detected")
        return None if value is None else bool(value)
    statistics = _get(result, "statistics", {}) or {}
    if isinstance(statistics, Mapping) and "break_detected" in statistics:
        value = statistics.get("break_detected")
        if value is None:
            return None
        return bool(int(value)) if isinstance(value, (int, float)) else bool(value)
    return None


def _window_values(result: Any, key: str) -> tuple[float | None, ...] | None:
    details = _get(result, "details", {}) or {}
    windows = details.get("windows") if isinstance(details, Mapping) else None
    if not windows:
        return None
    values: list[float | None] = []
    for row in windows:
        if not isinstance(row, Mapping):
            values.append(None)
            continue
        raw = row.get(key)
        values.append(float(raw) if is_finite_number(raw) else None)
    return tuple(values)


def _stat(result: Any, key: str) -> float | None:
    if result is None or not _is_usable(result):
        return None
    statistics = _get(result, "statistics", {}) or {}
    if not isinstance(statistics, Mapping):
        return None
    value = statistics.get(key)
    return float(value) if is_finite_number(value) else None


def _pvalue(result: Any) -> float | None:
    if result is None or not _is_usable(result):
        return None
    value = _get(result, "pvalue", None)
    return float(value) if is_finite_number(value) else None


def _as_of_from_results(explicit: datetime | None, results: Sequence[Any]) -> datetime | None:
    if explicit is not None:
        return explicit
    for result in results:
        stamp = _get(result, "as_of", None)
        if isinstance(stamp, datetime):
            return stamp
    return None


def mean_reversion_evidence_from_stage1(
    *,
    as_of: datetime | None = None,
    rolling_stationarity: Any | None = None,
    rolling_parameter_stability: Any | None = None,
    structural_break: Any | None = None,
    half_life: Any | None = None,
    cadf: Any | None = None,
    formation_half_life: float | None = None,
    formation_hedge_ratio: float | None = None,
    formation_residual_vol: float | None = None,
    formation_convergence_rate: float | None = None,
    realized_friction: float | None = None,
    expected_friction: float | None = None,
    convergence_rate: float | None = None,
    extra: Mapping[str, object] | None = None,
) -> MeanReversionEvidence:
    """Map Stage 1 diagnostic results onto mean-reversion health evidence.

    Unusable Stage 1 results do not silently look healthy: the field is omitted
    so ``HealthMonitor`` fails closed when ``fail_closed_on_missing`` is set.
    """

    results = (
        rolling_stationarity,
        rolling_parameter_stability,
        structural_break,
        half_life,
        cadf,
    )
    stamp = _as_of_from_results(as_of, results)
    if stamp is None:
        raise ValueError("as_of is required when Stage 1 results do not carry as_of timestamps")

    adf_pvalues = _window_values(rolling_stationarity, "adf_pvalue") if _is_usable(rolling_stationarity) else None
    adf_frac = _stat(rolling_stationarity, "fraction_reject_unit_root_5pct")
    cadf_pvalues: tuple[float | None, ...] | None = None
    cadf_frac: float | None = None
    cadf_pvalue = _pvalue(cadf)
    if cadf_pvalue is not None:
        cadf_pvalues = (cadf_pvalue,)
        cadf_frac = 1.0 if cadf_pvalue < 0.05 else 0.0

    live_half_life = _stat(half_life, "half_life")
    if live_half_life is None and _is_usable(rolling_stationarity):
        live_half_life = _stat(rolling_stationarity, "half_life_median")
        window_hls = _window_values(rolling_stationarity, "half_life")
        if window_hls:
            finite = [v for v in window_hls if v is not None]
            if finite:
                live_half_life = finite[-1]

    live_beta = None
    live_vol = None
    if _is_usable(rolling_parameter_stability):
        live_beta = _stat(rolling_parameter_stability, "beta_mean")
        live_vol = _stat(rolling_parameter_stability, "residual_vol_mean")
        betas = _window_values(rolling_parameter_stability, "beta")
        vols = _window_values(rolling_parameter_stability, "residual_std")
        if betas:
            finite_b = [v for v in betas if v is not None]
            if finite_b:
                live_beta = finite_b[-1]
        if vols:
            finite_v = [v for v in vols if v is not None]
            if finite_v:
                live_vol = finite_v[-1]
    if live_beta is None and _is_usable(cadf):
        details = _get(cadf, "details", {}) or {}
        hedge = details.get("hedge_ratio") if isinstance(details, Mapping) else None
        if isinstance(hedge, Mapping) and hedge:
            first = next(iter(hedge.values()))
            if is_finite_number(first):
                live_beta = float(first)
        else:
            live_beta = _stat(cadf, "beta_0")
        live_vol = live_vol if live_vol is not None else _stat(cadf, "residual_std")

    break_detected = extract_break_detected(structural_break)
    usable = True
    if structural_break is not None and not _is_usable(structural_break):
        # Unusable break diagnostic cannot be treated as "no break".
        break_detected = None
        usable = True  # missing break field triggers fail-closed missing_evidence
    notes = (
        "Adapted from Stage 1 DiagnosticResult objects.",
        "Unusable diagnostics omit fields so health fails closed rather than assuming health.",
        "Adapter output is evidence only and must not place an order.",
    )
    return MeanReversionEvidence(
        as_of=stamp,
        rolling_adf_pvalues=adf_pvalues,
        rolling_adf_reject_fraction=adf_frac,
        rolling_cadf_pvalues=cadf_pvalues,
        rolling_cadf_reject_fraction=cadf_frac,
        half_life=live_half_life,
        half_life_baseline=formation_half_life,
        hedge_ratio=live_beta,
        hedge_ratio_baseline=formation_hedge_ratio,
        residual_volatility=live_vol,
        residual_volatility_baseline=formation_residual_vol,
        convergence_rate=convergence_rate,
        convergence_rate_baseline=formation_convergence_rate,
        structural_break_detected=break_detected,
        realized_friction=realized_friction,
        expected_friction=expected_friction,
        usable=usable,
        source="stage1_adapter",
        notes=notes,
        extra=dict(extra or {}),
    )
