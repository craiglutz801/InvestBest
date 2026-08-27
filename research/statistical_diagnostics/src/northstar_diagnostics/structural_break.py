"""Structural-break interface and result contract.

Stage 1 defines the contract plus two reference detectors (Chow at a
pre-specified or estimated date; CUSUM of OLS residuals). Detection is
eligibility evidence only and must not place an order.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable

import numpy as np
from scipy.stats import f as f_dist
from statsmodels.stats.diagnostic import breaks_cusumolsresid

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import ArrayLike, flag, ols_with_intercept, prepare_series

BREAK_ASSUMPTIONS = (
    "A structural-break flag is not a trade, stop, or order.",
    "Chow p-values are valid only for a break date chosen independently of the data.",
    "If the candidate date is estimated by scanning, the p-value is anti-conservative.",
    "CUSUM-of-OLS-residuals follows Ploberger-Kramer via statsmodels; it targets coefficient instability in a mean/OLS model.",
    "These tests do not identify the economic cause of a break.",
)


@runtime_checkable
class StructuralBreakDetector(Protocol):
    """Interface every Stage 1 (and later) break detector must satisfy."""

    method_id: str

    def detect(
        self,
        series: ArrayLike,
        *,
        timestamps: Sequence[datetime] | None = None,
        as_of: datetime | int | None = None,
        candidate_index: int | None = None,
        exog: ArrayLike | None = None,
        min_obs: int = 30,
        frequency: str | None = None,
        computed_at: datetime | None = None,
    ) -> DiagnosticResult:
        ...


class ChowBreakDetector:
    """Chow test for a mean (or OLS) break at a candidate index."""

    method_id = "chow_ols"

    def detect(
        self,
        series: ArrayLike,
        *,
        timestamps: Sequence[datetime] | None = None,
        as_of: datetime | int | None = None,
        candidate_index: int | None = None,
        exog: ArrayLike | None = None,
        min_obs: int = 30,
        frequency: str | None = None,
        computed_at: datetime | None = None,
        significance: float = 0.05,
    ) -> DiagnosticResult:
        params = {
            "candidate_index": candidate_index,
            "min_obs": min_obs,
            "frequency": frequency,
            "significance": significance,
            "has_exog": exog is not None,
        }
        prepared = prepare_series(
            series, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
        )
        flags = list(prepared.flags)
        if not prepared.usable:
            return failed_result(
                diagnostic_id="structural_break",
                name="Structural break (Chow OLS)",
                sample=prepared.sample,
                method="chow_ols",
                parameters=params,
                quality_flags=flags,
                assumptions=BREAK_ASSUMPTIONS,
                as_of=prepared.as_of,
                computed_at=computed_at,
            )

        y = prepared.values
        if exog is None:
            x = np.zeros((y.size, 0))
        else:
            x_prep = prepare_series(
                np.asarray(exog, dtype=float).reshape(-1),
                timestamps=timestamps,
                as_of=as_of,
                min_obs=min_obs,
                frequency=frequency,
            )
            flags.extend(list(x_prep.flags))
            if not x_prep.usable:
                return failed_result(
                    diagnostic_id="structural_break",
                    name="Structural break (Chow OLS)",
                    sample=prepared.sample,
                    method="chow_ols",
                    parameters=params,
                    quality_flags=flags,
                    assumptions=BREAK_ASSUMPTIONS,
                    as_of=prepared.as_of,
                    computed_at=computed_at,
                )
            n = min(y.size, x_prep.values.size)
            y = y[:n]
            x = x_prep.values[:n].reshape(n, -1)

        k = 1 + x.shape[1]
        estimated = candidate_index is None
        if estimated:
            # Scan interior indices; p-value is not valid for a data-mined date.
            lo = k + 1
            hi = y.size - k - 1
            if hi <= lo:
                flags.append(
                    flag(
                        QualityCode.SHORT_SAMPLE,
                        QualityLevel.FAIL,
                        "Sample too short to scan for a Chow break",
                    )
                )
                return failed_result(
                    diagnostic_id="structural_break",
                    name="Structural break (Chow OLS)",
                    sample=prepared.sample,
                    method="chow_ols",
                    parameters=params,
                    quality_flags=flags,
                    assumptions=BREAK_ASSUMPTIONS,
                    as_of=prepared.as_of,
                    computed_at=computed_at,
                )
            best = None
            for idx in range(lo, hi + 1):
                parsed = _chow_at(y, x, idx, k)
                if parsed is None:
                    continue
                fstat, _, _, _ = parsed
                if best is None or fstat > best[0]:
                    best = (fstat, idx, parsed)
            if best is None:
                flags.append(
                    flag(
                        QualityCode.COMPUTATION_ERROR,
                        QualityLevel.FAIL,
                        "Chow scan produced no valid split",
                    )
                )
                return failed_result(
                    diagnostic_id="structural_break",
                    name="Structural break (Chow OLS)",
                    sample=prepared.sample,
                    method="chow_ols",
                    parameters=params,
                    quality_flags=flags,
                    assumptions=BREAK_ASSUMPTIONS,
                    as_of=prepared.as_of,
                    computed_at=computed_at,
                )
            fstat, split, parsed = best[0], best[1], best[2]
            flags.append(
                flag(
                    QualityCode.BREAK_DATE_ESTIMATED,
                    QualityLevel.WARN,
                    "Break date was estimated by a max-F scan; the Chow p-value is anti-conservative",
                )
            )
        else:
            split = int(candidate_index)
            parsed = _chow_at(y, x, split, k)
            if parsed is None:
                flags.append(
                    flag(
                        QualityCode.INVALID_INPUT,
                        QualityLevel.FAIL,
                        "Candidate index leaves a regime that is too short or rank-deficient",
                    )
                )
                return failed_result(
                    diagnostic_id="structural_break",
                    name="Structural break (Chow OLS)",
                    sample=prepared.sample,
                    method="chow_ols",
                    parameters=params,
                    quality_flags=flags,
                    assumptions=BREAK_ASSUMPTIONS,
                    as_of=prepared.as_of,
                    computed_at=computed_at,
                )
            fstat = parsed[0]

        fstat, pvalue, rss_r, rss_u = parsed
        break_detected: bool | None = bool(pvalue < significance) if pvalue is not None else None
        if estimated:
            interpretation = (
                "chow_max_f_scan_candidate (p-value not valid for estimated date; not a trade)"
            )
        elif break_detected:
            interpretation = "chow_reject_stability_at_candidate (break evidence only; not a trade)"
        else:
            interpretation = "chow_fail_to_reject_stability_at_candidate"

        ts = None
        if prepared.timestamps is not None and 0 <= split < prepared.timestamps.size:
            from northstar_diagnostics.series import _datetime_from_ns

            ts = _datetime_from_ns(prepared.timestamps[split]).isoformat()

        return make_result(
            diagnostic_id="structural_break",
            name="Structural break (Chow OLS)",
            sample=prepared.sample,
            method="chow_ols",
            parameters={**params, "candidate_index": split, "break_date_estimated": estimated},
            statistics={
                "f_stat": float(fstat),
                "candidate_index": int(split),
                "k_params": int(k),
                "rss_restricted": float(rss_r),
                "rss_unrestricted": float(rss_u),
                "break_detected": int(bool(break_detected)) if break_detected is not None else None,
                "significance": float(significance),
            },
            pvalue=float(pvalue) if pvalue is not None else None,
            hypotheses={
                "H0": "OLS coefficients are stable across the candidate split",
                "H1": "coefficients differ across the split",
            },
            assumptions=BREAK_ASSUMPTIONS,
            quality_flags=tuple(flags),
            interpretation=interpretation,
            details={
                "candidate_index": int(split),
                "candidate_timestamp": ts,
                "break_detected": break_detected,
                "break_date_estimated": estimated,
            },
            notes=(
                "Interface result contract: details.break_detected, candidate_index, candidate_timestamp.",
                "This result must not place an order or change a simulated position.",
            ),
            as_of=prepared.as_of,
            computed_at=computed_at,
        )


def _chow_at(
    y: np.ndarray, x: np.ndarray, split: int, k: int
) -> tuple[float, float, float, float] | None:
    if split < k or (y.size - split) < k:
        return None
    try:
        coef_r, resid_r, rank_r = ols_with_intercept(y, x if x.size else np.zeros((y.size, 0)))
        coef_1, resid_1, rank_1 = ols_with_intercept(
            y[:split], x[:split] if x.size else np.zeros((split, 0))
        )
        coef_2, resid_2, rank_2 = ols_with_intercept(
            y[split:], x[split:] if x.size else np.zeros((y.size - split, 0))
        )
    except np.linalg.LinAlgError:
        return None
    if min(rank_r, rank_1, rank_2) < k:
        return None
    rss_r = float(np.sum(resid_r**2))
    rss_u = float(np.sum(resid_1**2) + np.sum(resid_2**2))
    df2 = y.size - 2 * k
    if df2 <= 0 or rss_u <= 0 or not np.isfinite(rss_u):
        return None
    fstat = ((rss_r - rss_u) / k) / (rss_u / df2)
    if not np.isfinite(fstat) or fstat < 0:
        return None
    pvalue = float(f_dist.sf(fstat, k, df2))
    return float(fstat), pvalue, rss_r, rss_u


class CUSUMOLSBreakDetector:
    """Ploberger-Kramer CUSUM of OLS residuals (statsmodels)."""

    method_id = "cusum_ols_resid"

    def detect(
        self,
        series: ArrayLike,
        *,
        timestamps: Sequence[datetime] | None = None,
        as_of: datetime | int | None = None,
        candidate_index: int | None = None,
        exog: ArrayLike | None = None,
        min_obs: int = 30,
        frequency: str | None = None,
        computed_at: datetime | None = None,
        significance: float = 0.05,
    ) -> DiagnosticResult:
        params = {
            "min_obs": min_obs,
            "frequency": frequency,
            "significance": significance,
            "has_exog": exog is not None,
            "candidate_index": candidate_index,
        }
        prepared = prepare_series(
            series, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
        )
        flags = list(prepared.flags)
        if not prepared.usable:
            return failed_result(
                diagnostic_id="structural_break",
                name="Structural break (CUSUM OLS residuals)",
                sample=prepared.sample,
                method="cusum_ols_resid",
                parameters=params,
                quality_flags=flags,
                assumptions=BREAK_ASSUMPTIONS,
                as_of=prepared.as_of,
                computed_at=computed_at,
            )

        y = prepared.values
        if exog is None:
            x = np.zeros((y.size, 0))
        else:
            x_arr = np.asarray(exog, dtype=float).reshape(-1)
            n = min(y.size, x_arr.size)
            y = y[:n]
            x = x_arr[:n].reshape(n, -1)
        try:
            _, resid, rank = ols_with_intercept(y, x)
            sup_b, pvalue, crit = breaks_cusumolsresid(resid, ddof=max(rank, 1))
        except Exception as exc:  # noqa: BLE001
            flags.append(
                flag(QualityCode.COMPUTATION_ERROR, QualityLevel.FAIL, f"CUSUM OLS residual test failed: {exc}")
            )
            return failed_result(
                diagnostic_id="structural_break",
                name="Structural break (CUSUM OLS residuals)",
                sample=prepared.sample,
                method="cusum_ols_resid",
                parameters=params,
                quality_flags=flags,
                assumptions=BREAK_ASSUMPTIONS,
                as_of=prepared.as_of,
                computed_at=computed_at,
            )

        pvalue_f = float(pvalue) if pvalue is not None else None
        break_detected = bool(pvalue_f < significance) if pvalue_f is not None else None
        crit_map = {}
        if crit is not None:
            arr = np.asarray(crit, dtype=float).reshape(-1)
            labels = ("10%", "5%", "1%")
            for label, value in zip(labels, arr, strict=False):
                crit_map[label] = float(value)

        interpretation = (
            "cusum_ols_reject_stability (break evidence only; not a trade)"
            if break_detected
            else "cusum_ols_fail_to_reject_stability"
        )
        return make_result(
            diagnostic_id="structural_break",
            name="Structural break (CUSUM OLS residuals)",
            sample=prepared.sample,
            method="cusum_ols_resid",
            parameters=params,
            statistics={
                "sup_b": float(sup_b),
                "break_detected": int(bool(break_detected)) if break_detected is not None else None,
                "significance": float(significance),
            },
            pvalue=pvalue_f,
            critical_values=crit_map,
            hypotheses={
                "H0": "OLS residual CUSUM is consistent with coefficient stability",
                "H1": "coefficient instability",
            },
            assumptions=BREAK_ASSUMPTIONS,
            quality_flags=tuple(flags),
            interpretation=interpretation,
            details={
                "candidate_index": candidate_index,
                "break_detected": break_detected,
                "method_id": self.method_id,
            },
            notes=(
                "Interface result contract: details.break_detected plus method_id.",
                "This result must not place an order or change a simulated position.",
            ),
            as_of=prepared.as_of,
            computed_at=computed_at,
        )


def detect_structural_break(
    series: ArrayLike,
    *,
    method: str = "chow_ols",
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    candidate_index: int | None = None,
    exog: ArrayLike | None = None,
    min_obs: int = 30,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    """Dispatch to a reference detector. ``method`` is ``chow_ols`` or ``cusum_ols_resid``."""

    detectors: dict[str, StructuralBreakDetector] = {
        "chow_ols": ChowBreakDetector(),
        "cusum_ols_resid": CUSUMOLSBreakDetector(),
    }
    detector = detectors.get(method)
    if detector is None:
        prepared = prepare_series(series, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency)
        return failed_result(
            diagnostic_id="structural_break",
            name="Structural break",
            sample=prepared.sample,
            method=method,
            parameters={"method": method},
            quality_flags=(
                flag(
                    QualityCode.INVALID_INPUT,
                    QualityLevel.FAIL,
                    f"Unknown structural-break method {method!r}",
                ),
            ),
            assumptions=BREAK_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )
    return detector.detect(
        series,
        timestamps=timestamps,
        as_of=as_of,
        candidate_index=candidate_index,
        exog=exog,
        min_obs=min_obs,
        frequency=frequency,
        computed_at=computed_at,
    )
