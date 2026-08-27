"""Hurst-exponent diagnostic (lagged-difference variance method)."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import numpy as np

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import ArrayLike, flag, prepare_series

HURST_ASSUMPTIONS = (
    "Primary estimator: Var(X_{t+lag} - X_t) ∝ lag^{2H}; H is half the log-log slope.",
    "H ≈ 0.5 is consistent with a random walk / uncorrelated increments on this window.",
    "H < 0.5 is consistent with anti-persistence (mean-reversion-like), not a trade.",
    "H > 0.5 is consistent with persistence / trend-like increments, not a trade.",
    "The estimator is biased in short samples and is not a sized hypothesis test here.",
    "Chan-style lagged-std slope is reported as a secondary statistic for comparison.",
)


def hurst_diagnostic(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    min_lag: int = 2,
    max_lag: int | None = None,
    min_obs: int = 50,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    params = {
        "min_lag": min_lag,
        "max_lag": max_lag,
        "min_obs": min_obs,
        "frequency": frequency,
    }
    prepared = prepare_series(
        values, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
    )
    if not prepared.usable:
        return failed_result(
            diagnostic_id="hurst",
            name="Hurst exponent diagnostic",
            sample=prepared.sample,
            method="log-log variance of lagged differences",
            parameters=params,
            quality_flags=prepared.flags,
            assumptions=HURST_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    ts = prepared.values
    n = ts.size
    if max_lag is None:
        max_lag = min(100, max(min_lag + 2, n // 4))
    if max_lag <= min_lag:
        return failed_result(
            diagnostic_id="hurst",
            name="Hurst exponent diagnostic",
            sample=prepared.sample,
            method="log-log variance of lagged differences",
            parameters={**params, "max_lag": max_lag},
            quality_flags=(
                *prepared.flags,
                flag(
                    QualityCode.INSUFFICIENT_LAGS,
                    QualityLevel.FAIL,
                    f"Need max_lag > min_lag; got min_lag={min_lag}, max_lag={max_lag}",
                ),
            ),
            assumptions=HURST_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    lags: list[int] = []
    log_vars: list[float] = []
    log_std_sqrt: list[float] = []
    for lag in range(min_lag, int(max_lag) + 1):
        delta = ts[lag:] - ts[:-lag]
        if delta.size < 8:
            continue
        var = float(np.var(delta, ddof=1))
        std = float(np.std(delta, ddof=1))
        if not np.isfinite(var) or var <= 0 or not np.isfinite(std) or std <= 0:
            continue
        lags.append(lag)
        log_vars.append(np.log(var))
        # Chan: tau = sqrt(std(diff)); slope of log(tau) vs log(lag) is H/2
        log_std_sqrt.append(np.log(np.sqrt(std)))

    flags = list(prepared.flags)
    if len(lags) < 5:
        flags.append(
            flag(
                QualityCode.INSUFFICIENT_LAGS,
                QualityLevel.FAIL,
                f"Only {len(lags)} usable lags for the Hurst regression",
            )
        )
        return failed_result(
            diagnostic_id="hurst",
            name="Hurst exponent diagnostic",
            sample=prepared.sample,
            method="log-log variance of lagged differences",
            parameters={**params, "max_lag": max_lag},
            quality_flags=flags,
            assumptions=HURST_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    log_lags = np.log(np.asarray(lags, dtype=float))
    slope_var = float(np.polyfit(log_lags, np.asarray(log_vars, dtype=float), 1)[0])
    hurst = slope_var / 2.0
    slope_chan = float(np.polyfit(log_lags, np.asarray(log_std_sqrt, dtype=float), 1)[0])
    hurst_chan = slope_chan * 2.0

    if hurst < 0.45:
        interpretation = "anti_persistent_hint_H_below_0.45 (not a trade signal)"
    elif hurst > 0.55:
        interpretation = "persistent_hint_H_above_0.55 (not a trade signal)"
    else:
        interpretation = "near_random_walk_hint_H_around_0.5 (not a trade signal)"

    return make_result(
        diagnostic_id="hurst",
        name="Hurst exponent diagnostic",
        sample=prepared.sample,
        method="log-log variance of lagged differences",
        parameters={**params, "max_lag": int(max_lag), "n_lags_used": len(lags)},
        statistics={
            "hurst": float(hurst),
            "hurst_chan_lagged_std": float(hurst_chan),
            "variance_loglog_slope": slope_var,
            "n_lags_used": len(lags),
            "min_lag_used": int(min(lags)),
            "max_lag_used": int(max(lags)),
        },
        pvalue=None,
        hypotheses={
            "random_walk": "H = 0.5",
            "anti_persistence": "H < 0.5",
            "persistence": "H > 0.5",
        },
        assumptions=HURST_ASSUMPTIONS,
        quality_flags=tuple(flags),
        interpretation=interpretation,
        notes=(
            "No p-value is attached; compare H only as a rough persistence diagnostic.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=prepared.as_of,
        computed_at=computed_at,
    )
