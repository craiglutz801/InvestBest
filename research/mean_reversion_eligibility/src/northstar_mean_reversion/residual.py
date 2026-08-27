"""Hedge-ratio / residual construction and rolling spread-vol summaries.

Used as eligibility evidence. Residuals are not entry signals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from northstar_diagnostics.series import ols_with_intercept, variance_is_degenerate


@dataclass(frozen=True)
class ResidualFit:
    symbols: tuple[str, ...]
    hedge_ratio: dict[str, float]
    intercept: float
    residual: np.ndarray
    last_zscore: float | None
    residual_mean: float
    residual_std: float
    method: str
    usable: bool
    message: str


def _window_ends(n: int, window: int, step: int) -> list[int]:
    if window < 2 or step < 1 or n < window:
        return []
    ends = list(range(window - 1, n, step))
    if ends[-1] != n - 1:
        ends.append(n - 1)
    return ends


def _zscore(residual: np.ndarray) -> tuple[float, float, float | None]:
    mean = float(np.mean(residual))
    std = float(np.std(residual, ddof=1)) if residual.size > 1 else float("nan")
    if not np.isfinite(std) or std <= 0:
        return mean, std, None
    return mean, std, float((residual[-1] - mean) / std)


def fit_pair_residual(y: np.ndarray, x: np.ndarray, symbols: Sequence[str]) -> ResidualFit:
    """OLS residual y - a - b x with hedge weights {y: 1, x: -b}."""

    y = np.asarray(y, dtype=np.float64).reshape(-1)
    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = min(y.size, x.size)
    y = y[:n]
    x = x[:n]
    names = tuple(symbols[:2])
    try:
        coef, resid, rank = ols_with_intercept(y, x)
    except (np.linalg.LinAlgError, ValueError) as exc:
        return ResidualFit(
            symbols=names,
            hedge_ratio={},
            intercept=float("nan"),
            residual=np.asarray([], dtype=float),
            last_zscore=None,
            residual_mean=float("nan"),
            residual_std=float("nan"),
            method="ols_y_on_x",
            usable=False,
            message=f"OLS hedge regression failed: {exc}",
        )
    if rank < 2 or variance_is_degenerate(resid):
        return ResidualFit(
            symbols=names,
            hedge_ratio={},
            intercept=float(coef[0]) if coef.size else float("nan"),
            residual=np.asarray([], dtype=float),
            last_zscore=None,
            residual_mean=float("nan"),
            residual_std=float("nan"),
            method="ols_y_on_x",
            usable=False,
            message="Hedge regression is rank-deficient or residual variance is degenerate",
        )
    mean, std, zscore = _zscore(resid)
    hedge = {names[0]: 1.0, names[1]: -float(coef[1])}
    return ResidualFit(
        symbols=names,
        hedge_ratio=hedge,
        intercept=float(coef[0]),
        residual=resid,
        last_zscore=zscore,
        residual_mean=mean,
        residual_std=std,
        method="ols_y_on_x",
        usable=True,
        message="OLS residual formed",
    )


def fit_basket_residual(
    panel: np.ndarray,
    symbols: Sequence[str],
    weights: Sequence[float] | None = None,
) -> ResidualFit:
    """Spread = panel @ weights (Johansen vector or OLS fallback)."""

    panel = np.asarray(panel, dtype=np.float64)
    if panel.ndim != 2 or panel.shape[1] < 2:
        return ResidualFit(
            symbols=tuple(symbols),
            hedge_ratio={},
            intercept=0.0,
            residual=np.asarray([], dtype=float),
            last_zscore=None,
            residual_mean=float("nan"),
            residual_std=float("nan"),
            method="basket_spread",
            usable=False,
            message="Basket residual requires a 2d panel with at least two columns",
        )
    names = tuple(symbols[: panel.shape[1]])
    method = "johansen_vector"
    intercept = 0.0
    if weights is None:
        y = panel[:, 0]
        x = panel[:, 1:]
        try:
            coef, resid, rank = ols_with_intercept(y, x)
        except (np.linalg.LinAlgError, ValueError) as exc:
            return ResidualFit(
                symbols=names,
                hedge_ratio={},
                intercept=float("nan"),
                residual=np.asarray([], dtype=float),
                last_zscore=None,
                residual_mean=float("nan"),
                residual_std=float("nan"),
                method="ols_first_on_rest",
                usable=False,
                message=f"Basket OLS hedge failed: {exc}",
            )
        if rank < 1 + x.shape[1] or variance_is_degenerate(resid):
            return ResidualFit(
                symbols=names,
                hedge_ratio={},
                intercept=float(coef[0]) if coef.size else float("nan"),
                residual=np.asarray([], dtype=float),
                last_zscore=None,
                residual_mean=float("nan"),
                residual_std=float("nan"),
                method="ols_first_on_rest",
                usable=False,
                message="Basket OLS hedge is rank-deficient or degenerate",
            )
        intercept = float(coef[0])
        hedge = {names[0]: 1.0}
        for i, name in enumerate(names[1:]):
            hedge[name] = -float(coef[i + 1])
        method = "ols_first_on_rest"
        mean, std, zscore = _zscore(resid)
        return ResidualFit(
            symbols=names,
            hedge_ratio=hedge,
            intercept=intercept,
            residual=resid,
            last_zscore=zscore,
            residual_mean=mean,
            residual_std=std,
            method=method,
            usable=True,
            message="OLS basket residual formed",
        )

    vec = np.asarray(list(weights), dtype=np.float64).reshape(-1)
    if vec.size != panel.shape[1] or not np.all(np.isfinite(vec)):
        return ResidualFit(
            symbols=names,
            hedge_ratio={},
            intercept=0.0,
            residual=np.asarray([], dtype=float),
            last_zscore=None,
            residual_mean=float("nan"),
            residual_std=float("nan"),
            method=method,
            usable=False,
            message="Johansen cointegrating vector is missing or non-finite",
        )
    if abs(vec[0]) > 1e-12:
        vec = vec / vec[0]
    resid = panel @ vec
    if variance_is_degenerate(resid):
        return ResidualFit(
            symbols=names,
            hedge_ratio={name: float(w) for name, w in zip(names, vec)},
            intercept=0.0,
            residual=np.asarray([], dtype=float),
            last_zscore=None,
            residual_mean=float("nan"),
            residual_std=float("nan"),
            method=method,
            usable=False,
            message="Johansen spread has degenerate variance",
        )
    mean, std, zscore = _zscore(resid)
    return ResidualFit(
        symbols=names,
        hedge_ratio={name: float(w) for name, w in zip(names, vec)},
        intercept=0.0,
        residual=resid,
        last_zscore=zscore,
        residual_mean=mean,
        residual_std=std,
        method=method,
        usable=True,
        message="Johansen spread formed",
    )


def rolling_spread_vol_cv(residual: np.ndarray, window: int, step: int) -> dict[str, float | int | None]:
    residual = np.asarray(residual, dtype=np.float64).reshape(-1)
    ends = _window_ends(residual.size, window, step)
    vols: list[float] = []
    for end in ends:
        start = end - window + 1
        chunk = residual[start : end + 1]
        if chunk.size < 2 or variance_is_degenerate(chunk):
            continue
        vols.append(float(np.std(chunk, ddof=1)))
    mean = float(np.mean(vols)) if vols else None
    std = float(np.std(vols, ddof=1)) if len(vols) > 1 else None
    cv = (std / mean) if mean not in (None, 0) and std is not None else None
    return {
        "n_windows": len(ends),
        "n_usable_windows": len(vols),
        "residual_vol_mean": mean,
        "residual_vol_std": std,
        "residual_vol_cv": cv,
    }


def rolling_hedge_relative_std(
    y: np.ndarray,
    x: np.ndarray,
    window: int,
    step: int,
) -> dict[str, float | int | None]:
    """Rolling OLS beta relative standard deviation (pairs or first-vs-rest)."""

    y = np.asarray(y, dtype=np.float64).reshape(-1)
    x_arr = np.asarray(x, dtype=np.float64)
    if x_arr.ndim == 1:
        x_arr = x_arr.reshape(-1, 1)
    n = min(y.size, x_arr.shape[0])
    y = y[:n]
    x_arr = x_arr[:n]
    ends = _window_ends(n, window, step)
    betas: list[np.ndarray] = []
    for end in ends:
        start = end - window + 1
        try:
            coef, resid, rank = ols_with_intercept(y[start : end + 1], x_arr[start : end + 1])
        except (np.linalg.LinAlgError, ValueError):
            continue
        expected = 1 + x_arr.shape[1]
        if rank < expected or variance_is_degenerate(resid):
            continue
        betas.append(np.asarray(coef[1:], dtype=float))
    if len(betas) < 2:
        return {
            "n_windows": len(ends),
            "n_usable_windows": len(betas),
            "beta_relative_std": None,
        }
    stacked = np.vstack(betas)
    rels: list[float] = []
    for col in range(stacked.shape[1]):
        mean = float(np.mean(stacked[:, col]))
        std = float(np.std(stacked[:, col], ddof=1))
        if mean == 0 or not np.isfinite(mean):
            continue
        rels.append(abs(std / mean))
    return {
        "n_windows": len(ends),
        "n_usable_windows": int(stacked.shape[0]),
        "beta_relative_std": float(max(rels)) if rels else None,
        "beta_mean": float(np.mean(stacked[:, 0])),
        "beta_std": float(np.std(stacked[:, 0], ddof=1)),
    }


def residual_summary(fit: ResidualFit) -> Mapping[str, float | None]:
    return {
        "last_zscore": fit.last_zscore,
        "residual_mean": fit.residual_mean,
        "residual_std": fit.residual_std,
        "n_obs": float(fit.residual.size),
        "intercept": fit.intercept,
    }
