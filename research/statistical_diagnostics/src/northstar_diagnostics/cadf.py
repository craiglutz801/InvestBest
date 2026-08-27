"""CADF / Engle-Granger pair residual cointegration diagnostic."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import numpy as np
import statsmodels.tsa.stattools as ts

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import (
    ArrayLike,
    flag,
    length_mismatch_flag,
    ols_with_intercept,
    prepare_series,
    timestamp_mismatch_flag,
    variance_is_degenerate,
)

CADF_ASSUMPTIONS = (
    "Engle-Granger / CADF: OLS hedge regression then a unit-root test on residuals.",
    "Critical values are cointegration values (MacKinnon), not plain ADF values.",
    "The first series is treated as the dependent variable; the rest are regressors.",
    "A stable in-sample hedge ratio is not guaranteed out of sample.",
    "Cointegration is not a sufficient condition for a pairs trade after costs.",
    "Structural breaks can produce spurious residual stationarity or hide a relation.",
    "y and x must already be equal-length and date-aligned; unequal or mismatched inputs fail closed.",
)


def cadf_cointegration(
    y: ArrayLike,
    x: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    x_timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    trend: str = "c",
    maxlag: int | None = None,
    autolag: str | None = "aic",
    min_obs: int = 30,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    """Engle-Granger cointegration test for y against x (1d or 2d).

    ``y`` and ``x`` must have equal aligned lengths. If timestamps are
    supplied, ``x_timestamps`` must match ``timestamps`` exactly. Unequal
    lengths are never truncated.
    """

    params = {
        "trend": trend,
        "maxlag": maxlag,
        "autolag": autolag,
        "min_obs": min_obs,
        "frequency": frequency,
    }
    y_arr = np.asarray(y, dtype=np.float64).reshape(-1)
    x_arr = np.asarray(x, dtype=np.float64)
    flags: list = []

    if x_arr.ndim > 2:
        flags.append(
            flag(
                QualityCode.INVALID_INPUT,
                QualityLevel.FAIL,
                "x must be 1d or 2d",
            )
        )
        dummy = prepare_series(y_arr, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency)
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=dummy.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=dummy.as_of,
            computed_at=computed_at,
        )

    x_rows = int(x_arr.size if x_arr.ndim <= 1 else x_arr.shape[0])
    length_flag = length_mismatch_flag(int(y_arr.size), x_rows)
    ts_flag = timestamp_mismatch_flag(timestamps, x_timestamps if x_timestamps is not None else timestamps)
    if length_flag is not None:
        flags.append(length_flag)
    if ts_flag is not None:
        flags.append(ts_flag)
    if flags:
        dummy = prepare_series(y_arr, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency)
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=dummy.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=dummy.as_of,
            computed_at=computed_at,
        )

    shared_timestamps = timestamps
    y_prep = prepare_series(
        y_arr, timestamps=shared_timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
    )
    if x_arr.ndim == 1:
        x_prep = prepare_series(
            x_arr, timestamps=shared_timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
        )
        x_mat = x_prep.values.reshape(-1, 1) if x_prep.values.size else None
        x_flags = x_prep.flags
        x_usable = x_prep.usable
        x_rows_used = int(x_prep.values.size)
    else:
        from northstar_diagnostics.series import prepare_panel

        x_mat, x_prepared = prepare_panel(
            x_arr, timestamps=shared_timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
        )
        x_flags = x_prepared.flags
        x_usable = x_prepared.usable
        x_rows_used = 0 if x_mat is None else int(x_mat.shape[0])

    flags = list(y_prep.flags) + [f for f in x_flags if f not in y_prep.flags]
    if not y_prep.usable or not x_usable or x_mat is None:
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=y_prep.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    if y_prep.values.size != x_rows_used:
        flags.append(
            length_mismatch_flag(int(y_prep.values.size), x_rows_used, what="point-in-time y and x")
            or flag(
                QualityCode.LENGTH_MISMATCH,
                QualityLevel.FAIL,
                "Point-in-time y and x lengths differ",
            )
        )
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=y_prep.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    y_v = y_prep.values
    x_v = x_mat
    if y_v.size < min_obs:
        flags.append(
            flag(
                QualityCode.SHORT_SAMPLE,
                QualityLevel.FAIL,
                f"Aligned pair length {y_v.size} is below min_obs={min_obs}",
            )
        )
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=y_prep.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    try:
        coef, resid, rank = ols_with_intercept(y_v, x_v)
    except np.linalg.LinAlgError as exc:
        flags.append(
            flag(QualityCode.NEAR_SINGULAR, QualityLevel.FAIL, f"OLS hedge regression failed: {exc}")
        )
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=y_prep.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    expected_rank = 1 + x_v.shape[1]
    if rank < expected_rank:
        flags.append(
            flag(
                QualityCode.NEAR_SINGULAR,
                QualityLevel.FAIL,
                f"Hedge regression is rank-deficient (rank={rank}, expected={expected_rank})",
            )
        )
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=y_prep.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    if variance_is_degenerate(resid):
        flags.append(
            flag(
                QualityCode.DEGENERATE_VARIANCE,
                QualityLevel.FAIL,
                "OLS residuals have degenerate variance (series are nearly identical)",
            )
        )
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=y_prep.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    try:
        tstat, pvalue, crit = ts.coint(y_v, x_v, trend=trend, maxlag=maxlag, autolag=autolag)
    except Exception as exc:  # noqa: BLE001
        flags.append(
            flag(QualityCode.COMPUTATION_ERROR, QualityLevel.FAIL, f"CADF/coint failed: {exc}")
        )
        return failed_result(
            diagnostic_id="cadf",
            name="CADF / Engle-Granger residual cointegration",
            sample=y_prep.sample,
            method="statsmodels.tsa.stattools.coint",
            parameters=params,
            quality_flags=flags,
            assumptions=CADF_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    crit_map = {}
    if crit is not None:
        labels = ("1%", "5%", "10%")
        for label, value in zip(labels, np.asarray(crit).reshape(-1), strict=False):
            crit_map[label] = float(value)

    pvalue_f = float(pvalue) if pvalue is not None else None
    hedge = {f"beta_{i}": float(coef[i + 1]) for i in range(x_v.shape[1])}
    if pvalue_f is not None and pvalue_f < 0.05:
        interpretation = (
            "reject_no_cointegration_at_5pct (residual stationarity evidence only; not a trade)"
        )
    else:
        interpretation = "fail_to_reject_no_cointegration_at_5pct"

    return make_result(
        diagnostic_id="cadf",
        name="CADF / Engle-Granger residual cointegration",
        sample=y_prep.sample,
        method="statsmodels.tsa.stattools.coint",
        parameters=params,
        statistics={
            "coint_tstat": float(tstat),
            "intercept": float(coef[0]),
            "residual_std": float(np.std(resid, ddof=1)),
            "ols_rank": rank,
            **hedge,
        },
        pvalue=pvalue_f,
        critical_values=crit_map,
        hypotheses={
            "H0": "no cointegration (residual has a unit root)",
            "H1": "cointegration (residual is stationary)",
        },
        assumptions=CADF_ASSUMPTIONS,
        quality_flags=tuple(flags),
        interpretation=interpretation,
        details={"hedge_ratio": hedge, "n_regressors": int(x_v.shape[1])},
        notes=(
            "Hedge ratios are in-sample OLS coefficients and may drift.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=y_prep.as_of,
        computed_at=computed_at,
    )
