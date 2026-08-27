"""Mean-reversion half-life diagnostic (AR(1) / OU discrete analogue)."""

from __future__ import annotations

from datetime import datetime
from math import log
from typing import Sequence

import numpy as np

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import ArrayLike, flag, prepare_series

HALF_LIFE_ASSUMPTIONS = (
    "Half-life comes from Δy_t = μ + θ y_{t-1} + ε_t, with HL = -ln(2)/θ when θ < 0.",
    "This is the discrete analogue of an Ornstein-Uhlenbeck / AR(1) mean-reverting process.",
    "If the series is not AR(1), the half-life is a misspecified summary, not a holding period.",
    "θ >= 0 means the estimate is not mean-reverting on this window; HL is undefined.",
    "A finite half-life is not evidence that a trade survives friction or structural breaks.",
)


def mean_reversion_half_life(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    min_obs: int = 20,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    params = {"min_obs": min_obs, "frequency": frequency}
    prepared = prepare_series(
        values, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
    )
    if not prepared.usable:
        return failed_result(
            diagnostic_id="half_life",
            name="Mean-reversion half-life",
            sample=prepared.sample,
            method="OLS Δy_t = μ + θ y_{t-1}",
            parameters=params,
            quality_flags=prepared.flags,
            assumptions=HALF_LIFE_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    y = prepared.values
    dy = np.diff(y)
    ylag = y[:-1]
    design = np.column_stack([np.ones(ylag.size), ylag])
    try:
        coef, _, rank, _ = np.linalg.lstsq(design, dy, rcond=None)
    except np.linalg.LinAlgError as exc:
        return failed_result(
            diagnostic_id="half_life",
            name="Mean-reversion half-life",
            sample=prepared.sample,
            method="OLS Δy_t = μ + θ y_{t-1}",
            parameters=params,
            quality_flags=(
                *prepared.flags,
                flag(QualityCode.NEAR_SINGULAR, QualityLevel.FAIL, f"OLS failed: {exc}"),
            ),
            assumptions=HALF_LIFE_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    flags = list(prepared.flags)
    if rank < 2:
        flags.append(
            flag(
                QualityCode.NEAR_SINGULAR,
                QualityLevel.FAIL,
                f"Half-life OLS is rank-deficient (rank={rank})",
            )
        )
        return failed_result(
            diagnostic_id="half_life",
            name="Mean-reversion half-life",
            sample=prepared.sample,
            method="OLS Δy_t = μ + θ y_{t-1}",
            parameters=params,
            quality_flags=flags,
            assumptions=HALF_LIFE_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    mu = float(coef[0])
    theta = float(coef[1])
    phi = 1.0 + theta
    half_life: float | None
    if theta < 0 and np.isfinite(theta):
        half_life = float(-log(2.0) / theta)
        interpretation = (
            "mean_reverting_ar1_half_life_defined (time-scale estimate only; not a trade)"
        )
    else:
        half_life = None
        flags.append(
            flag(
                QualityCode.HALF_LIFE_UNDEFINED,
                QualityLevel.WARN,
                "θ >= 0 so AR(1) half-life is undefined on this window",
            )
        )
        interpretation = "half_life_undefined_not_mean_reverting_ar1"

    if half_life is not None and (half_life > y.size * 5 or not np.isfinite(half_life)):
        flags.append(
            flag(
                QualityCode.UNSTABLE_PARAMETERS,
                QualityLevel.WARN,
                "Estimated half-life is very large relative to the sample; treat as unstable",
            )
        )

    return make_result(
        diagnostic_id="half_life",
        name="Mean-reversion half-life",
        sample=prepared.sample,
        method="OLS Δy_t = μ + θ y_{t-1}",
        parameters=params,
        statistics={
            "theta": theta,
            "mu": mu,
            "phi": phi,
            "half_life": half_life,
            "ols_rank": int(rank),
        },
        pvalue=None,
        hypotheses={
            "model": "Δy_t = μ + θ y_{t-1} + ε_t",
            "mean_reversion": "θ < 0 (equivalently |φ| < 1 with φ = 1+θ)",
        },
        assumptions=HALF_LIFE_ASSUMPTIONS,
        quality_flags=tuple(flags),
        interpretation=interpretation,
        notes=(
            "Holding-period choice still requires cost, horizon, and break diagnostics.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=prepared.as_of,
        computed_at=computed_at,
    )
