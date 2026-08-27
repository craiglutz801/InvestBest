"""Deflated Sharpe Ratio (Bailey & López de Prado, 2014).

The DSR is the Probabilistic Sharpe Ratio evaluated at the expected *maximum*
Sharpe ratio under ``n_trials`` independent tests. It is a multiple-testing
correction, not a license to trade.

Two **different** variance quantities appear in the definition:

1. **Cross-sectional trial-Sharpe variance** ``V[{SR_n}]`` — dispersion of
   Sharpe ratios **across the tried strategies/trials**. This is the scale of
   the False Strategy / expected-max threshold ``SR0``. It is **not** the
   selected strategy's return-series sampling variance.

2. **Selected-strategy sampling-error term** (skew/kurtosis) — the PSR/DSR
   denominator. This uses only the candidate's own return series.

Formulas (per-period Sharpe, not annualized):

    SR̂ = mean(r) / std(r, ddof=1)

    γ₃ = sample skewness,  γ₄ = sample Pearson kurtosis (normal = 3)

    denom = sqrt(1 - γ₃ SR̂ + ((γ₄ - 1) / 4) SR̂²)

    V[{SR_n}] = sample variance of the N trial Sharpes (ddof=1),
                or an explicit caller-supplied estimate.
                Never inferred from denom² / (n_obs - 1).

    SR₀ = sqrt(V[{SR_n}]) * [(1-γ) Φ⁻¹(1 - 1/N) + γ Φ⁻¹(1 - 1/(N e))]

    where γ is the Euler–Mascheroni constant and N = n_trials.
    For N = 1, SR₀ is defined as 0 (no selection bias). For N > 1,
    trial-Sharpe dispersion evidence is required (fail-closed if missing).

    DSR = Φ[ (SR̂ - SR₀) * sqrt(n_obs - 1) / denom ]

Assumptions and limitations are recorded on every result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.stats import kurtosis as scipy_kurtosis
from scipy.stats import norm, skew as scipy_skew

from northstar_promotion.arrays import has_fail, validate_1d
from northstar_promotion.metrics import period_mean_std
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag, warn_flag
from northstar_promotion.schema import make_meta

EULER_MASCHERONI = 0.5772156649015328606
MIN_DSR_OBS = 5


@dataclass(frozen=True)
class DSRResult:
    n_obs: int
    n_trials: int
    period_sharpe: float
    skewness: float
    kurtosis: float
    sampling_denominator: float
    trial_sharpe_variance: float
    expected_max_sharpe: float
    deflated_sharpe: float
    quality_flags: tuple[QualityFlag, ...]
    meta: dict

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "n_obs": self.n_obs,
            "n_trials": self.n_trials,
            "period_sharpe": self.period_sharpe,
            "skewness": self.skewness,
            "kurtosis": self.kurtosis,
            "sampling_denominator": self.sampling_denominator,
            "trial_sharpe_variance": self.trial_sharpe_variance,
            "expected_max_sharpe": self.expected_max_sharpe,
            "deflated_sharpe": self.deflated_sharpe,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def expected_max_sharpe(n_trials: int, trial_sharpe_variance: float) -> tuple[float, tuple[QualityFlag, ...]]:
    """False Strategy expected-maximum Sharpe.

    ``trial_sharpe_variance`` is ``V[{SR_n}]`` — cross-sectional variance of
    Sharpe ratios **across trials**, not the selected series' sampling variance.

    Independent trials, SR ~ Normal. For ``n_trials == 1`` this is 0.
    The small-N approximation is known to be slightly biased (N=2 exact
    E[max of two N(0,1)] = 1/sqrt(pi) ≈ 0.5642).
    """
    flags: list[QualityFlag] = []
    if n_trials < 1 or not np.isfinite(n_trials):
        return float("nan"), (
            fail_flag(QualityCode.INSUFFICIENT_TRIALS, "n_trials must be a finite integer >= 1."),
        )
    if trial_sharpe_variance < 0 or not np.isfinite(trial_sharpe_variance):
        return float("nan"), (
            fail_flag(QualityCode.INVALID_INPUT, "trial_sharpe_variance must be finite and >= 0."),
        )
    if n_trials == 1 or trial_sharpe_variance == 0.0:
        return 0.0, tuple(flags)
    z1 = float(norm.ppf(1.0 - 1.0 / n_trials))
    z2 = float(norm.ppf(1.0 - 1.0 / (n_trials * math.e)))
    if not np.isfinite(z1) or not np.isfinite(z2):
        return float("nan"), (
            fail_flag(QualityCode.COMPUTATION_ERROR, "Normal PPF overflow while computing SR0."),
        )
    loc = (1.0 - EULER_MASCHERONI) * z1 + EULER_MASCHERONI * z2
    return float(math.sqrt(trial_sharpe_variance) * loc), tuple(flags)


def sharpe_sampling_variance(period_sharpe: float, n_obs: int, skewness: float, kurtosis: float) -> float:
    """Selected-strategy Sharpe *sampling* variance (PSR term). Not V[{SR_n}]."""
    denom_sq = 1.0 - skewness * period_sharpe + ((kurtosis - 1.0) / 4.0) * period_sharpe**2
    if denom_sq <= 0 or not np.isfinite(denom_sq) or n_obs < 2:
        return float("nan")
    return float(denom_sq / (n_obs - 1))


def cross_sectional_sharpe_variance(
    trial_sharpes: Sequence[float] | np.ndarray,
) -> tuple[float, tuple[QualityFlag, ...]]:
    """Sample variance (ddof=1) of trial Sharpe ratios. Fail-closed on gaps."""
    arr, flags = validate_1d(trial_sharpes, name="trial_sharpes")
    if has_fail(flags):
        return float("nan"), flags
    if arr.size < 2:
        return float("nan"), (
            fail_flag(
                QualityCode.INSUFFICIENT_TRIALS,
                "Cross-sectional Sharpe variance needs at least 2 finite trial Sharpes.",
            ),
        )
    var = float(np.var(arr, ddof=1))
    extra: tuple[QualityFlag, ...] = ()
    if var == 0.0:
        extra = (
            warn_flag(
                QualityCode.DEGENERATE_VARIANCE,
                "All trial Sharpes are identical; V[{SR_n}]=0 so SR0=0. "
                "This understates selection bias if the trials are not true replicates.",
            ),
        )
    return var, flags + extra


def _resolve_trial_variance(
    *,
    n_trials: int,
    trial_sharpes: Sequence[float] | np.ndarray | None,
    sharpe_trials_variance: float | None,
) -> tuple[float, tuple[QualityFlag, ...]]:
    flags: list[QualityFlag] = []
    if n_trials == 1:
        if trial_sharpes is not None or sharpe_trials_variance is not None:
            flags.append(
                warn_flag(
                    QualityCode.INVALID_INPUT,
                    "N=1: SR0 is 0 (no selection bias). Supplied trial-Sharpe dispersion is not used for SR0.",
                )
            )
        return 0.0, tuple(flags)

    if trial_sharpes is not None and sharpe_trials_variance is not None:
        return float("nan"), (
            fail_flag(
                QualityCode.INVALID_INPUT,
                "Pass either trial_sharpes or sharpe_trials_variance, not both.",
            ),
        )
    if trial_sharpes is None and sharpe_trials_variance is None:
        return float("nan"), (
            fail_flag(
                QualityCode.MISSING_TRIAL_SHARPE_DISPERSION,
                "n_trials > 1 requires explicit trial-Sharpe dispersion "
                "(trial_sharpes or sharpe_trials_variance). "
                "It is not inferred from the selected strategy's sampling variance.",
            ),
        )
    if trial_sharpes is not None:
        arr, vflags = validate_1d(trial_sharpes, name="trial_sharpes")
        flags.extend(vflags)
        if has_fail(flags):
            return float("nan"), tuple(flags)
        if arr.size != int(n_trials):
            return float("nan"), (
                fail_flag(
                    QualityCode.INVALID_INPUT,
                    f"len(trial_sharpes)={arr.size} must equal n_trials={n_trials}. "
                    "Do not drop undefined Sharpes from the search universe.",
                ),
            )
        var, var_flags = cross_sectional_sharpe_variance(arr)
        flags.extend(var_flags)
        return var, tuple(flags)

    var = float(sharpe_trials_variance)  # type: ignore[arg-type]
    if not np.isfinite(var) or var < 0:
        return float("nan"), (
            fail_flag(
                QualityCode.INVALID_INPUT,
                "sharpe_trials_variance must be finite and >= 0.",
            ),
        )
    flags.append(
        warn_flag(
            QualityCode.MISSING_DATA,
            "Using caller-supplied sharpe_trials_variance rather than empirical trial Sharpes.",
        )
    )
    return var, tuple(flags)


def deflated_sharpe_ratio(
    returns: Sequence[float] | np.ndarray,
    n_trials: int,
    *,
    trial_sharpes: Sequence[float] | np.ndarray | None = None,
    sharpe_trials_variance: float | None = None,
    min_obs: int = MIN_DSR_OBS,
) -> DSRResult:
    flags: list[QualityFlag] = []
    arr, vflags = validate_1d(returns, name="returns")
    flags.extend(vflags)
    if n_trials < 1:
        flags.append(
            fail_flag(
                QualityCode.INSUFFICIENT_TRIALS,
                "n_trials must be >= 1. Unknown search breadth is fail-closed.",
            )
        )

    def _fail(**vals: float) -> DSRResult:
        meta = make_meta(
            method="deflated_sharpe_ratio",
            parameters={
                "n_trials": n_trials,
                "min_obs": min_obs,
                "supplied_trial_sharpes": trial_sharpes is not None,
                "supplied_sharpe_trials_variance": sharpe_trials_variance is not None,
            },
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return DSRResult(
            n_obs=int(arr.size),
            n_trials=int(n_trials) if n_trials == n_trials else 0,
            period_sharpe=float("nan"),
            skewness=float("nan"),
            kurtosis=float("nan"),
            sampling_denominator=float("nan"),
            trial_sharpe_variance=float(vals.get("trial_sharpe_variance", float("nan"))),
            expected_max_sharpe=float("nan"),
            deflated_sharpe=float("nan"),
            quality_flags=tuple(flags),
            meta=meta.to_dict(),
        )

    if has_fail(flags):
        return _fail()

    v_trials, disp_flags = _resolve_trial_variance(
        n_trials=int(n_trials),
        trial_sharpes=trial_sharpes,
        sharpe_trials_variance=sharpe_trials_variance,
    )
    flags.extend(disp_flags)
    if has_fail(flags):
        return _fail(trial_sharpe_variance=v_trials)

    mu, sigma, n, mflags = period_mean_std(arr)
    flags.extend(mflags)
    if n < min_obs:
        flags.append(fail_flag(QualityCode.SHORT_SAMPLE, f"DSR needs at least {min_obs} observations; got {n}."))
    if has_fail(flags):
        return _fail(trial_sharpe_variance=v_trials)

    period_sr = float(mu / sigma)
    g3 = float(scipy_skew(arr, bias=True, nan_policy="omit"))
    g4 = float(scipy_kurtosis(arr, fisher=False, bias=True, nan_policy="omit"))
    if not np.isfinite(g3) or not np.isfinite(g4):
        flags.append(fail_flag(QualityCode.NON_FINITE, "Skewness or kurtosis is non-finite."))
        return _fail(trial_sharpe_variance=v_trials)
    if g4 < 1.0:
        flags.append(
            fail_flag(
                QualityCode.INVALID_INPUT,
                f"Pearson kurtosis {g4} < 1 is incompatible with the DSR denominator.",
            )
        )
        return _fail(trial_sharpe_variance=v_trials)

    denom_sq = 1.0 - g3 * period_sr + ((g4 - 1.0) / 4.0) * period_sr**2
    if denom_sq <= 0 or not np.isfinite(denom_sq):
        flags.append(
            fail_flag(
                QualityCode.DEGENERATE_VARIANCE,
                f"DSR denominator squared is {denom_sq}; non-normality correction is not usable.",
            )
        )
        return _fail(trial_sharpe_variance=v_trials)
    denom = math.sqrt(denom_sq)
    sampling_var = denom_sq / (n - 1)
    sr0, sr0_flags = expected_max_sharpe(int(n_trials), v_trials)
    flags.extend(sr0_flags)
    if has_fail(flags) or not np.isfinite(sr0):
        return _fail(trial_sharpe_variance=v_trials)

    z = (period_sr - sr0) * math.sqrt(n - 1) / denom
    dsr = float(norm.cdf(z))
    if not np.isfinite(dsr):
        flags.append(fail_flag(QualityCode.COMPUTATION_ERROR, "DSR CDF was non-finite."))
        return _fail(trial_sharpe_variance=v_trials)

    if n < 30:
        flags.append(
            warn_flag(
                QualityCode.SHORT_SAMPLE,
                "DSR with n < 30 has weak power; treat the probability as noisy.",
            )
        )
    flags.append(
        ok_flag(
            f"DSR={dsr:.4f} with n_trials={n_trials}, SR0={sr0:.4f} from V[{{SR_n}}]={v_trials:.6g}, "
            f"period SR={period_sr:.4f}."
        )
    )
    meta = make_meta(
        method="deflated_sharpe_ratio_bailey_2014",
        parameters={
            "n_trials": int(n_trials),
            "min_obs": min_obs,
            "euler_mascheroni": EULER_MASCHERONI,
            "supplied_trial_sharpes": trial_sharpes is not None,
            "supplied_sharpe_trials_variance": sharpe_trials_variance is not None,
        },
        assumptions=_ASSUMPTIONS,
        quality_flags=tuple(flags),
        details={
            "z_stat": z,
            "psr_denominator": denom,
            "mean": mu,
            "std": sigma,
            "selected_sampling_variance_not_used_for_sr0": sampling_var,
            "trial_sharpe_variance_used_for_sr0": v_trials,
        },
    )
    return DSRResult(
        n_obs=n,
        n_trials=int(n_trials),
        period_sharpe=period_sr,
        skewness=g3,
        kurtosis=g4,
        sampling_denominator=float(denom),
        trial_sharpe_variance=float(v_trials),
        expected_max_sharpe=sr0,
        deflated_sharpe=dsr,
        quality_flags=tuple(flags),
        meta=meta.to_dict(),
    )


_ASSUMPTIONS = (
    "Bailey, D. H. and López de Prado, M. (2014), 'The Deflated Sharpe Ratio'.",
    "SR0 uses V[{SR_n}] = cross-sectional variance of trial Sharpe ratios (False Strategy theorem).",
    "The PSR/DSR denominator uses the selected strategy's skew/kurtosis sampling-error term only.",
    "V[{SR_n}] is never inferred from denom²/(n_obs-1) of the selected return series.",
    "For n_trials > 1, trial_sharpes or sharpe_trials_variance is required (fail-closed if missing).",
    "Trials are treated as independent given V[{SR_n}]. Positive correlation among trials understates SR0.",
    "Sharpe is per-period; do not pass annualized Sharpe into this function.",
    "SR0 for N=1 is defined as 0 so DSR reduces to PSR(0).",
    "The expected-max formula is an extreme-value approximation, slightly biased at small N.",
    "DSR is a probability that SR̂ exceeds the multiple-testing-adjusted hurdle, not an edge guarantee.",
)
