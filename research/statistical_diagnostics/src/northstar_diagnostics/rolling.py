"""Rolling stationarity and parameter-stability diagnostics.

Each window uses only observations at or before that window's end index.
Windows never peek at future observations relative to their ``as_of_index``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import numpy as np

from northstar_diagnostics.adf import adf_stationarity
from northstar_diagnostics.half_life import mean_reversion_half_life
from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import ArrayLike, flag, ols_with_intercept, prepare_series, variance_is_degenerate

ROLLING_ASSUMPTIONS = (
    "Each rolling window is sliced with an inclusive end index; later observations are unused.",
    "Overlapping windows are serially dependent, so stability fractions are descriptive, not independent tests.",
    "Parameter-stability statistics summarize in-window OLS hedge ratios and residual volatility.",
    "A stable in-sample coefficient path is not a trading signal and can still break after the last window.",
)


def _window_ends(n: int, window: int, step: int) -> list[int]:
    if window < 2 or step < 1 or n < window:
        return []
    ends = list(range(window - 1, n, step))
    if ends[-1] != n - 1:
        ends.append(n - 1)
    return ends


def rolling_stationarity(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    window: int = 60,
    step: int = 5,
    min_obs: int = 20,
    frequency: str | None = None,
    computed_at: datetime | None = None,
    adf_regression: str = "c",
) -> DiagnosticResult:
    """Rolling ADF p-values and rolling AR(1) half-life on a univariate series."""

    params = {
        "window": window,
        "step": step,
        "min_obs": min_obs,
        "frequency": frequency,
        "adf_regression": adf_regression,
    }
    prepared = prepare_series(
        values, timestamps=timestamps, as_of=as_of, min_obs=max(min_obs, window), frequency=frequency
    )
    flags = list(prepared.flags)
    if window < min_obs:
        flags.append(
            flag(
                QualityCode.INVALID_INPUT,
                QualityLevel.FAIL,
                f"rolling window {window} is below min_obs={min_obs}",
            )
        )
    if not prepared.usable:
        return failed_result(
            diagnostic_id="rolling_stationarity",
            name="Rolling stationarity / half-life stability",
            sample=prepared.sample,
            method="rolling ADF + half-life",
            parameters=params,
            quality_flags=flags,
            assumptions=ROLLING_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    series = prepared.values
    ends = _window_ends(series.size, window, step)
    if not ends:
        flags.append(
            flag(QualityCode.SHORT_SAMPLE, QualityLevel.FAIL, "Not enough observations for any rolling window")
        )
        return failed_result(
            diagnostic_id="rolling_stationarity",
            name="Rolling stationarity / half-life stability",
            sample=prepared.sample,
            method="rolling ADF + half-life",
            parameters=params,
            quality_flags=flags,
            assumptions=ROLLING_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    observations: list[dict[str, float | int | None]] = []
    pvalues: list[float] = []
    half_lives: list[float] = []
    for end in ends:
        start = end - window + 1
        chunk = series[start : end + 1]
        adf_res = adf_stationarity(
            chunk,
            as_of=window - 1,
            regression=adf_regression,
            min_obs=min_obs,
            computed_at=computed_at,
        )
        hl_res = mean_reversion_half_life(
            chunk, as_of=window - 1, min_obs=min_obs, computed_at=computed_at
        )
        pval = adf_res.pvalue
        hl = hl_res.statistics.get("half_life") if hl_res.is_usable else None
        if isinstance(pval, float) and np.isfinite(pval):
            pvalues.append(pval)
        if isinstance(hl, (int, float)) and np.isfinite(float(hl)):
            half_lives.append(float(hl))
        ts_end = None
        if prepared.timestamps is not None and prepared.timestamps.size > end:
            from northstar_diagnostics.series import _datetime_from_ns

            ts_end = _datetime_from_ns(prepared.timestamps[end]).isoformat()
        observations.append(
            {
                "start_index": start,
                "end_index": end,
                "as_of_index": end,
                "end_timestamp": ts_end,
                "adf_pvalue": pval,
                "adf_usable": adf_res.is_usable,
                "half_life": float(hl) if isinstance(hl, (int, float)) else None,
            }
        )

    n_usable = sum(1 for row in observations if row["adf_usable"])
    frac_stat = (
        float(np.mean([p < 0.05 for p in pvalues])) if pvalues else None
    )
    stability = {
        "n_windows": len(observations),
        "n_usable_adf_windows": n_usable,
        "fraction_reject_unit_root_5pct": frac_stat,
        "adf_pvalue_mean": float(np.mean(pvalues)) if pvalues else None,
        "adf_pvalue_std": float(np.std(pvalues, ddof=1)) if len(pvalues) > 1 else None,
        "half_life_median": float(np.median(half_lives)) if half_lives else None,
        "half_life_std": float(np.std(half_lives, ddof=1)) if len(half_lives) > 1 else None,
    }

    interpretation = "rolling_stationarity_summary (descriptive; not a trade signal)"
    return make_result(
        diagnostic_id="rolling_stationarity",
        name="Rolling stationarity / half-life stability",
        sample=prepared.sample,
        method="rolling ADF + half-life",
        parameters=params,
        statistics=stability,
        pvalue=None,
        hypotheses={
            "window_H0": "unit root inside each formation window",
            "stability": "descriptive dispersion of window statistics",
        },
        assumptions=ROLLING_ASSUMPTIONS,
        quality_flags=tuple(flags),
        interpretation=interpretation,
        details={"windows": observations},
        notes=(
            "Last window ends at the point-in-time cutoff; no future bars are used.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=prepared.as_of,
        computed_at=computed_at,
    )


def rolling_parameter_stability(
    y: ArrayLike,
    x: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    window: int = 60,
    step: int = 5,
    min_obs: int = 30,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    """Rolling OLS hedge ratio and residual-volatility stability for a pair."""

    params = {"window": window, "step": step, "min_obs": min_obs, "frequency": frequency}
    y_prep = prepare_series(y, timestamps=timestamps, as_of=as_of, min_obs=max(min_obs, window), frequency=frequency)
    x_prep = prepare_series(x, timestamps=timestamps, as_of=as_of, min_obs=max(min_obs, window), frequency=frequency)
    flags = list(y_prep.flags) + [f for f in x_prep.flags if f not in y_prep.flags]
    if not y_prep.usable or not x_prep.usable:
        return failed_result(
            diagnostic_id="rolling_parameter_stability",
            name="Rolling hedge-ratio / residual-vol stability",
            sample=y_prep.sample,
            method="rolling OLS hedge ratio",
            parameters=params,
            quality_flags=flags,
            assumptions=ROLLING_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    n = min(y_prep.values.size, x_prep.values.size)
    y_v = y_prep.values[:n]
    x_v = x_prep.values[:n]
    ends = _window_ends(n, window, step)
    if not ends:
        flags.append(
            flag(QualityCode.SHORT_SAMPLE, QualityLevel.FAIL, "Not enough observations for any rolling window")
        )
        return failed_result(
            diagnostic_id="rolling_parameter_stability",
            name="Rolling hedge-ratio / residual-vol stability",
            sample=y_prep.sample,
            method="rolling OLS hedge ratio",
            parameters=params,
            quality_flags=flags,
            assumptions=ROLLING_ASSUMPTIONS,
            as_of=y_prep.as_of,
            computed_at=computed_at,
        )

    observations: list[dict[str, float | int | None | bool]] = []
    betas: list[float] = []
    vols: list[float] = []
    for end in ends:
        start = end - window + 1
        yy = y_v[start : end + 1]
        xx = x_v[start : end + 1]
        try:
            coef, resid, rank = ols_with_intercept(yy, xx)
        except np.linalg.LinAlgError:
            observations.append(
                {
                    "start_index": start,
                    "end_index": end,
                    "usable": False,
                    "beta": None,
                    "residual_std": None,
                }
            )
            continue
        if rank < 2 or variance_is_degenerate(resid):
            observations.append(
                {
                    "start_index": start,
                    "end_index": end,
                    "usable": False,
                    "beta": None,
                    "residual_std": None,
                    "ols_rank": rank,
                }
            )
            continue
        beta = float(coef[1])
        vol = float(np.std(resid, ddof=1))
        betas.append(beta)
        vols.append(vol)
        observations.append(
            {
                "start_index": start,
                "end_index": end,
                "usable": True,
                "intercept": float(coef[0]),
                "beta": beta,
                "residual_std": vol,
                "ols_rank": rank,
            }
        )

    beta_std = float(np.std(betas, ddof=1)) if len(betas) > 1 else None
    beta_mean = float(np.mean(betas)) if betas else None
    vol_mean = float(np.mean(vols)) if vols else None
    vol_std = float(np.std(vols, ddof=1)) if len(vols) > 1 else None
    rel_beta = (
        abs(beta_std / beta_mean) if beta_std is not None and beta_mean not in (0, None) else None
    )
    if rel_beta is not None and rel_beta > 0.5:
        flags.append(
            flag(
                QualityCode.UNSTABLE_PARAMETERS,
                QualityLevel.WARN,
                f"Rolling hedge ratio relative std is {rel_beta:.2f} (> 0.5)",
            )
        )

    return make_result(
        diagnostic_id="rolling_parameter_stability",
        name="Rolling hedge-ratio / residual-vol stability",
        sample=y_prep.sample,
        method="rolling OLS hedge ratio",
        parameters=params,
        statistics={
            "n_windows": len(observations),
            "n_usable_windows": len(betas),
            "beta_mean": beta_mean,
            "beta_std": beta_std,
            "beta_relative_std": rel_beta,
            "residual_vol_mean": vol_mean,
            "residual_vol_std": vol_std,
            "residual_vol_cv": (vol_std / vol_mean) if vol_std is not None and vol_mean not in (0, None) else None,
        },
        pvalue=None,
        hypotheses={"stability": "descriptive dispersion of rolling OLS hedge ratios"},
        assumptions=ROLLING_ASSUMPTIONS,
        quality_flags=tuple(flags),
        interpretation="rolling_parameter_stability_summary (descriptive; not a trade signal)",
        details={"windows": observations},
        notes=(
            "Each window ends at or before the point-in-time cutoff.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=y_prep.as_of,
        computed_at=computed_at,
    )
