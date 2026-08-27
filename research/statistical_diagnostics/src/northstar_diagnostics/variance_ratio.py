"""Lo-MacKinlay overlapping variance-ratio diagnostic."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import numpy as np
from scipy.stats import norm

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import ArrayLike, flag, prepare_series

VR_ASSUMPTIONS = (
    "Variance ratio uses overlapping q-period increments of the level series (Lo-MacKinlay).",
    "Under a homoskedastic random walk in increments, VR(q) = 1.",
    "VR < 1 is consistent with anti-persistence / mean reversion at horizon q.",
    "VR > 1 is consistent with positive serial correlation / trend-like increments at horizon q.",
    "Heteroskedastic-robust z-statistics are reported; p-values assume the usual CLT approximation.",
    "Rejecting a random walk is not a trading signal and does not survive cost or break checks by itself.",
)


def variance_ratio_diagnostic(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    q: int = 2,
    min_obs: int = 40,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    """Variance ratio on a level series (prices or log-prices).

    Increments are first differences of the PIT-sliced level series.
    """

    params = {"q": q, "min_obs": min_obs, "frequency": frequency}
    prepared = prepare_series(
        values, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
    )
    flags = list(prepared.flags)
    if q < 2:
        flags.append(
            flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, "q must be an integer >= 2")
        )
    if not prepared.usable or q < 2:
        return failed_result(
            diagnostic_id="variance_ratio",
            name="Variance-ratio diagnostic",
            sample=prepared.sample,
            method="Lo-MacKinlay overlapping VR",
            parameters=params,
            quality_flags=flags,
            assumptions=VR_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    x = prepared.values
    n = x.size - 1  # number of one-period increments
    if n <= 2 * q:
        flags.append(
            flag(
                QualityCode.SHORT_SAMPLE,
                QualityLevel.FAIL,
                f"Need more than 2q increments; got n={n}, q={q}",
            )
        )
        return failed_result(
            diagnostic_id="variance_ratio",
            name="Variance-ratio diagnostic",
            sample=prepared.sample,
            method="Lo-MacKinlay overlapping VR",
            parameters=params,
            quality_flags=flags,
            assumptions=VR_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    mu = (x[-1] - x[0]) / n
    dx = np.diff(x)
    se = dx - mu
    sigma2_1 = float(np.sum(se**2) / (n - 1))
    if not np.isfinite(sigma2_1) or sigma2_1 <= 0:
        flags.append(
            flag(
                QualityCode.DEGENERATE_VARIANCE,
                QualityLevel.FAIL,
                "One-period increment variance is degenerate",
            )
        )
        return failed_result(
            diagnostic_id="variance_ratio",
            name="Variance-ratio diagnostic",
            sample=prepared.sample,
            method="Lo-MacKinlay overlapping VR",
            parameters=params,
            quality_flags=flags,
            assumptions=VR_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    # Overlapping q-period variance with Lo-MacKinlay small-sample denominator
    m = q * (n - q + 1) * (1.0 - q / n)
    acc = 0.0
    for t in range(q, n + 1):
        acc += (x[t] - x[t - q] - q * mu) ** 2
    sigma2_q = float(acc / m) if m > 0 else float("nan")
    vr = sigma2_q / sigma2_1

    # Homoskedastic asymptotic variance of VR
    phi = 2.0 * (2.0 * q - 1.0) * (q - 1.0) / (3.0 * q)
    z_homo = float((vr - 1.0) / np.sqrt(phi / n)) if phi > 0 else float("nan")

    # Heteroskedastic robust (Lo-MacKinlay 1988)
    denom = float(np.sum(se**2) ** 2)
    theta = 0.0
    if denom > 0:
        for j in range(1, q):
            num = float(np.sum((se[j:] ** 2) * (se[:-j] ** 2)))
            delta_j = num / denom
            theta += (2.0 * (1.0 - j / q) ** 2) * delta_j
    z_het = float((vr - 1.0) / np.sqrt(theta)) if theta > 0 else float("nan")
    pvalue = float(2.0 * norm.sf(abs(z_het))) if np.isfinite(z_het) else None

    if not np.isfinite(vr):
        flags.append(
            flag(QualityCode.COMPUTATION_ERROR, QualityLevel.FAIL, "Variance ratio was not finite")
        )
        return failed_result(
            diagnostic_id="variance_ratio",
            name="Variance-ratio diagnostic",
            sample=prepared.sample,
            method="Lo-MacKinlay overlapping VR",
            parameters=params,
            quality_flags=flags,
            assumptions=VR_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    if vr < 0.9:
        interpretation = "vr_below_1_anti_persistent_hint (not a trade signal)"
    elif vr > 1.1:
        interpretation = "vr_above_1_persistent_hint (not a trade signal)"
    else:
        interpretation = "vr_near_1_random_walk_hint (not a trade signal)"

    return make_result(
        diagnostic_id="variance_ratio",
        name="Variance-ratio diagnostic",
        sample=prepared.sample,
        method="Lo-MacKinlay overlapping VR",
        parameters=params,
        statistics={
            "vr": float(vr),
            "q": int(q),
            "n_increments": int(n),
            "sigma2_1": sigma2_1,
            "sigma2_q": sigma2_q,
            "z_homoskedastic": z_homo,
            "z_heteroskedastic": z_het,
            "mu": float(mu),
        },
        pvalue=pvalue,
        hypotheses={
            "H0": "VR(q) = 1 (uncorrelated increments / random walk)",
            "H1": "VR(q) ≠ 1",
        },
        assumptions=VR_ASSUMPTIONS,
        quality_flags=tuple(flags),
        interpretation=interpretation,
        notes=(
            "p-value uses the heteroskedastic-robust z-statistic vs a two-sided Normal.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=prepared.as_of,
        computed_at=computed_at,
    )
