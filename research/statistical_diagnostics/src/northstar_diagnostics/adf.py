"""Augmented Dickey-Fuller stationarity diagnostic."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import statsmodels.tsa.stattools as ts

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import ArrayLike, flag, prepare_series

ADF_ASSUMPTIONS = (
    "Null hypothesis is a unit root (non-stationary) under the chosen deterministic specification.",
    "Lag length is selected by the requested information criterion (or a fixed maxlag).",
    "MacKinnon p-values assume the fitted specification; they are not a trading rule.",
    "Rejection of a unit root is not evidence of a tradable mean-reverting edge.",
    "Small samples have low power; lag/trend misspecification can reverse the conclusion.",
)


def adf_stationarity(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    regression: str = "c",
    maxlag: int | None = None,
    autolag: str | None = "AIC",
    min_obs: int = 20,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    """Run ADF on a point-in-time window of ``values``.

    Parameters
    ----------
    regression:
        statsmodels code: ``n`` (none), ``c`` (const), ``ct`` (const+trend),
        ``ctt`` (const+trend+trend^2).
    """

    params = {
        "regression": regression,
        "maxlag": maxlag,
        "autolag": autolag,
        "min_obs": min_obs,
        "frequency": frequency,
    }
    prepared = prepare_series(
        values,
        timestamps=timestamps,
        as_of=as_of,
        min_obs=min_obs,
        frequency=frequency,
    )
    if not prepared.usable:
        return failed_result(
            diagnostic_id="adf",
            name="Augmented Dickey-Fuller stationarity",
            sample=prepared.sample,
            method="statsmodels.tsa.stattools.adfuller",
            parameters=params,
            quality_flags=prepared.flags,
            assumptions=ADF_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    try:
        stat, pvalue, usedlag, nobs, crit, icbest = ts.adfuller(
            prepared.values,
            maxlag=maxlag,
            regression=regression,
            autolag=autolag,
        )
    except Exception as exc:  # noqa: BLE001 — normalize library failures into quality flags
        return failed_result(
            diagnostic_id="adf",
            name="Augmented Dickey-Fuller stationarity",
            sample=prepared.sample,
            method="statsmodels.tsa.stattools.adfuller",
            parameters=params,
            quality_flags=(
                *prepared.flags,
                flag(
                    QualityCode.COMPUTATION_ERROR,
                    QualityLevel.FAIL,
                    f"ADF failed: {exc}",
                ),
            ),
            assumptions=ADF_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    crit_map = {str(k): float(v) for k, v in dict(crit).items()}
    pvalue_f = float(pvalue) if pvalue is not None else None
    if pvalue_f is not None and pvalue_f < 0.05:
        interpretation = (
            "reject_unit_root_at_5pct (stationarity evidence only; not a trade signal)"
        )
    else:
        interpretation = (
            "fail_to_reject_unit_root_at_5pct (not evidence of a tradable trend either)"
        )

    return make_result(
        diagnostic_id="adf",
        name="Augmented Dickey-Fuller stationarity",
        sample=prepared.sample,
        method="statsmodels.tsa.stattools.adfuller",
        parameters={**params, "usedlag": int(usedlag), "nobs": int(nobs)},
        statistics={
            "adf_stat": float(stat),
            "usedlag": int(usedlag),
            "nobs": int(nobs),
            "icbest": float(icbest) if icbest is not None else None,
        },
        pvalue=pvalue_f,
        critical_values=crit_map,
        hypotheses={
            "H0": "series has a unit root (non-stationary)",
            "H1": "series is stationary around the chosen deterministic terms",
        },
        assumptions=ADF_ASSUMPTIONS,
        quality_flags=prepared.flags,
        interpretation=interpretation,
        notes=(
            "p-values are MacKinnon approximate p-values from statsmodels.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=prepared.as_of,
        computed_at=computed_at,
    )
