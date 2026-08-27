"""Period-return metrics used by promotion gates.

Sharpe ratios used by DSR / PBO are **per-period** (not annualized) unless a
caller explicitly annualizes with ``periods_per_year``. Mixing annualized and
per-period Sharpes in DSR is invalid.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from northstar_promotion.arrays import has_fail, validate_1d
from northstar_promotion.quality import QualityCode, fail_flag


def period_mean_std(returns: Any) -> tuple[float, float, int, tuple]:
    arr, flags = validate_1d(returns, name="returns")
    if has_fail(flags) or arr.size == 0:
        return float("nan"), float("nan"), int(arr.size), flags
    n = int(arr.size)
    if n < 2:
        flags = flags + (
            fail_flag(QualityCode.SHORT_SAMPLE, "Need at least 2 observations for mean/std."),
        )
        return float("nan"), float("nan"), n, flags
    mu = float(np.mean(arr))
    sigma = float(np.std(arr, ddof=1))
    extra = ()
    if not np.isfinite(mu) or not np.isfinite(sigma):
        extra = (fail_flag(QualityCode.NON_FINITE, "Mean or std is non-finite."),)
    elif sigma == 0.0:
        extra = (fail_flag(QualityCode.DEGENERATE_VARIANCE, "Sample standard deviation is zero."),)
    return mu, sigma, n, flags + extra


def period_sharpe(returns: Any) -> tuple[float, tuple]:
    mu, sigma, _n, flags = period_mean_std(returns)
    if has_fail(flags) or not np.isfinite(sigma) or sigma == 0.0:
        return float("nan"), flags
    return float(mu / sigma), flags


def annualized_sharpe(period_sr: float, periods_per_year: float) -> float:
    if not np.isfinite(period_sr) or not np.isfinite(periods_per_year) or periods_per_year <= 0:
        return float("nan")
    return float(period_sr * np.sqrt(periods_per_year))


def max_drawdown(returns: Any) -> tuple[float, tuple]:
    """Peak-to-trough drawdown on a simple-return wealth index. Negative or zero."""
    arr, flags = validate_1d(returns, name="returns")
    if has_fail(flags) or arr.size == 0:
        return float("nan"), flags
    wealth = np.cumprod(1.0 + arr)
    if not np.all(np.isfinite(wealth)):
        return float("nan"), flags + (
            fail_flag(QualityCode.NON_FINITE, "Wealth index became non-finite."),
        )
    peak = np.maximum.accumulate(wealth)
    dd = wealth / peak - 1.0
    return float(np.min(dd)), flags
