"""Johansen multivariate cointegration diagnostic."""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

import numpy as np
from statsmodels.tsa.vector_ar.vecm import coint_johansen

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import DiagnosticResult, failed_result, make_result
from northstar_diagnostics.series import ArrayLike, flag, prepare_panel

JOHANSEN_ASSUMPTIONS = (
    "Johansen trace / max-eigenvalue tests of cointegration rank in a VECM.",
    "Results are sensitive to lag (k_ar_diff), det_order, sample length, and scaling.",
    "Eigenvectors are identified only up to scaling and are not unique trading weights.",
    "Suggested rank uses sequential trace tests at the 5% critical values shipped by statsmodels.",
    "A cointegration rank >= 1 is not a pairs/baskets trading signal.",
    "Near-singular or short panels are statistically fragile.",
)


def johansen_cointegration(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | None = None,
    as_of: datetime | int | None = None,
    det_order: int = 0,
    k_ar_diff: int = 1,
    min_obs: int = 40,
    frequency: str | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    """Johansen test on a point-in-time multivariate panel (n_obs x n_series)."""

    params = {
        "det_order": det_order,
        "k_ar_diff": k_ar_diff,
        "min_obs": min_obs,
        "frequency": frequency,
    }
    panel, prepared = prepare_panel(
        values, timestamps=timestamps, as_of=as_of, min_obs=min_obs, frequency=frequency
    )
    flags = list(prepared.flags)

    if panel is None or panel.shape[1] < 2:
        flags.append(
            flag(
                QualityCode.INVALID_INPUT,
                QualityLevel.FAIL,
                "Johansen requires at least two series",
            )
        )
        return failed_result(
            diagnostic_id="johansen",
            name="Johansen multivariate cointegration",
            sample=prepared.sample,
            method="statsmodels.tsa.vector_ar.vecm.coint_johansen",
            parameters=params,
            quality_flags=flags,
            assumptions=JOHANSEN_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    if not prepared.usable:
        return failed_result(
            diagnostic_id="johansen",
            name="Johansen multivariate cointegration",
            sample=prepared.sample,
            method="statsmodels.tsa.vector_ar.vecm.coint_johansen",
            parameters=params,
            quality_flags=flags,
            assumptions=JOHANSEN_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    try:
        result = coint_johansen(panel, det_order=det_order, k_ar_diff=k_ar_diff)
    except Exception as exc:  # noqa: BLE001
        flags.append(
            flag(
                QualityCode.COMPUTATION_ERROR,
                QualityLevel.FAIL,
                f"Johansen failed: {exc}",
            )
        )
        # rank-deficient / singular cases often surface as LinAlgError
        if isinstance(exc, np.linalg.LinAlgError) or "singular" in str(exc).lower():
            flags.append(
                flag(
                    QualityCode.NEAR_SINGULAR,
                    QualityLevel.FAIL,
                    "Johansen encountered a singular/near-singular moment matrix",
                )
            )
        return failed_result(
            diagnostic_id="johansen",
            name="Johansen multivariate cointegration",
            sample=prepared.sample,
            method="statsmodels.tsa.vector_ar.vecm.coint_johansen",
            parameters=params,
            quality_flags=flags,
            assumptions=JOHANSEN_ASSUMPTIONS,
            as_of=prepared.as_of,
            computed_at=computed_at,
        )

    trace = np.asarray(result.lr1, dtype=float)
    maxeig = np.asarray(result.lr2, dtype=float)
    trace_cv = np.asarray(result.cvt, dtype=float)  # columns: 90, 95, 99
    max_cv = np.asarray(result.cvm, dtype=float)
    eig = np.asarray(result.eig, dtype=float)
    evec = np.asarray(result.evec, dtype=float)

    suggested_rank = 0
    for i, stat in enumerate(trace):
        cv95 = float(trace_cv[i, 1]) if trace_cv.ndim == 2 and trace_cv.shape[1] > 1 else float("nan")
        if np.isfinite(cv95) and float(stat) > cv95:
            suggested_rank = i + 1
        else:
            break

    statistics: dict[str, float | int | None] = {
        "n_series": int(panel.shape[1]),
        "suggested_rank_trace_5pct": int(suggested_rank),
        "k_ar_diff": int(k_ar_diff),
        "det_order": int(det_order),
    }
    for i, stat in enumerate(trace):
        statistics[f"trace_r{i}"] = float(stat)
        statistics[f"maxeig_r{i}"] = float(maxeig[i]) if i < maxeig.size else None
        if i < eig.size:
            statistics[f"eigenvalue_{i}"] = float(eig[i])

    crit = {}
    for i in range(trace_cv.shape[0]):
        crit[f"trace_r{i}_90pct"] = float(trace_cv[i, 0])
        crit[f"trace_r{i}_95pct"] = float(trace_cv[i, 1])
        crit[f"trace_r{i}_99pct"] = float(trace_cv[i, 2])
        if max_cv.size:
            crit[f"maxeig_r{i}_90pct"] = float(max_cv[i, 0])
            crit[f"maxeig_r{i}_95pct"] = float(max_cv[i, 1])
            crit[f"maxeig_r{i}_99pct"] = float(max_cv[i, 2])

    if suggested_rank >= 1:
        interpretation = (
            f"trace_test_suggests_rank_{suggested_rank}_at_5pct "
            "(eligibility evidence only; not a trade signal)"
        )
    else:
        interpretation = "trace_test_suggests_rank_0_at_5pct"

    # First cointegrating vector (column 0), if present
    hedge = None
    if evec.size:
        hedge = [float(v) for v in evec[:, 0]]

    return make_result(
        diagnostic_id="johansen",
        name="Johansen multivariate cointegration",
        sample=prepared.sample,
        method="statsmodels.tsa.vector_ar.vecm.coint_johansen",
        parameters=params,
        statistics=statistics,
        pvalue=None,
        critical_values=crit,
        hypotheses={
            "H0_r": "at most r cointegrating relations (sequential trace test)",
            "H1": "more than r cointegrating relations",
        },
        assumptions=JOHANSEN_ASSUMPTIONS,
        quality_flags=tuple(flags),
        interpretation=interpretation,
        details={
            "trace_stats": [float(v) for v in trace],
            "maxeig_stats": [float(v) for v in maxeig],
            "eigenvalues": [float(v) for v in eig],
            "first_coint_vector": hedge,
        },
        notes=(
            "statsmodels Johansen does not return p-values; critical values are used instead.",
            "This result must not place an order or change a simulated position.",
        ),
        as_of=prepared.as_of,
        computed_at=computed_at,
    )
