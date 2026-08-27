"""Uncertainty-shrunk fractional-Kelly *ceiling*, never a target.

Full Kelly is rejected. The returned number is an upper bound on leverage /
fraction of equity, then further clipped by volatility-target, concentration,
drawdown, exposure, liquidity, and RiskGovernor caps.

This module does not size live orders and does not call a RiskGovernor.
Missing RiskGovernor capacity is recorded; it is not treated as permission
to size without that cap in production.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from northstar_promotion.arrays import has_fail, validate_1d
from northstar_promotion.metrics import period_mean_std
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag, warn_flag
from northstar_promotion.schema import make_meta

DEFAULT_FRACTION = 0.25
DEFAULT_SHRINK_PRIOR = 1.0
DEFAULT_HARD_LEVERAGE_CAP = 1.0
Z_ONE_SIDED_95 = 1.6448536269514722


@dataclass(frozen=True)
class RiskCapBundle:
    """Hard caps that Kelly is subordinate to.

    Every field is a **maximum fraction of equity** except ``drawdown_throttle``
    (a multiplier in [0, 1] applied last) and ``vol_target`` / ``asset_vol``
    (used to form ``vol_target / asset_vol``).

    ``None`` means "not supplied". Not supplying a cap is never interpreted
    as infinity except for research reporting; production must pass
    ``risk_governor_cap``.
    """

    vol_target: float | None = None
    asset_vol: float | None = None
    concentration_max_weight: float | None = None
    drawdown_throttle: float | None = None
    exposure_cap: float | None = None
    liquidity_cap: float | None = None
    risk_governor_cap: float | None = None
    hard_leverage_cap: float = DEFAULT_HARD_LEVERAGE_CAP

    def to_dict(self) -> dict:
        return {
            "vol_target": self.vol_target,
            "asset_vol": self.asset_vol,
            "concentration_max_weight": self.concentration_max_weight,
            "drawdown_throttle": self.drawdown_throttle,
            "exposure_cap": self.exposure_cap,
            "liquidity_cap": self.liquidity_cap,
            "risk_governor_cap": self.risk_governor_cap,
            "hard_leverage_cap": self.hard_leverage_cap,
        }


@dataclass(frozen=True)
class KellyCeilingResult:
    n_obs: int
    mean_return: float
    std_return: float
    full_kelly: float
    shrink_factor: float
    shrunk_full_kelly: float
    fraction: float
    fractional_shrunk_kelly: float
    binding_caps: Mapping[str, float]
    ceiling: float
    role: str
    quality_flags: tuple[QualityFlag, ...]
    meta: dict

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "n_obs": self.n_obs,
            "mean_return": self.mean_return,
            "std_return": self.std_return,
            "full_kelly": self.full_kelly,
            "shrink_factor": self.shrink_factor,
            "shrunk_full_kelly": self.shrunk_full_kelly,
            "fraction": self.fraction,
            "fractional_shrunk_kelly": self.fractional_shrunk_kelly,
            "binding_caps": dict(self.binding_caps),
            "ceiling": self.ceiling,
            "role": self.role,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def _positive_cap(name: str, value: float | None, flags: list[QualityFlag]) -> float | None:
    if value is None:
        return None
    if not np.isfinite(value) or value < 0:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, f"{name} must be finite and >= 0."))
        return None
    return float(value)


def kelly_ceiling(
    returns: Sequence[float] | np.ndarray,
    *,
    fraction: float = DEFAULT_FRACTION,
    shrink_prior: float = DEFAULT_SHRINK_PRIOR,
    caps: RiskCapBundle | None = None,
    min_obs: int = 30,
    use_lower_confidence_mean: bool = False,
    z_lower: float = Z_ONE_SIDED_95,
) -> KellyCeilingResult:
    """Return an uncertainty-shrunk fractional-Kelly **ceiling**.

    Shrinkage (default): ``s = t² / (t² + shrink_prior)`` with
    ``t = mean / se(mean)``, then ``μ_shrunk = s * μ``. This pulls expected
    return toward 0 as sample uncertainty grows.

    Optional conservative mean: ``μ_lb = μ - z * se`` (one-sided).

    Gaussian / continuous-bet Kelly: ``f* = μ / σ²`` on per-period simple
    (or excess) returns. This is an approximation; it is not a full discrete
    Kelly solver.
    """
    flags: list[QualityFlag] = []
    role = "ceiling_not_target"
    caps = caps or RiskCapBundle()
    arr, vflags = validate_1d(returns, name="returns")
    flags.extend(vflags)

    def _fail(**vals: float) -> KellyCeilingResult:
        meta = make_meta(
            method="uncertainty_shrunk_fractional_kelly_ceiling",
            parameters={
                "fraction": fraction,
                "shrink_prior": shrink_prior,
                "min_obs": min_obs,
                "use_lower_confidence_mean": use_lower_confidence_mean,
                "caps": caps.to_dict(),
            },
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return KellyCeilingResult(
            n_obs=int(arr.size),
            mean_return=float(vals.get("mean_return", float("nan"))),
            std_return=float(vals.get("std_return", float("nan"))),
            full_kelly=float("nan"),
            shrink_factor=float("nan"),
            shrunk_full_kelly=float("nan"),
            fraction=float(fraction),
            fractional_shrunk_kelly=float("nan"),
            binding_caps={},
            ceiling=0.0,
            role=role,
            quality_flags=tuple(flags),
            meta=meta.to_dict(),
        )

    if has_fail(flags):
        return _fail()
    if not np.isfinite(fraction) or fraction <= 0:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "Kelly fraction must be finite and > 0."))
        return _fail()
    if fraction >= 1.0:
        flags.append(
            fail_flag(
                QualityCode.FULL_KELLY_REJECTED,
                f"fraction={fraction} is full Kelly or leveraged Kelly; rejected. Use a fraction in (0, 1).",
            )
        )
        return _fail()
    if not np.isfinite(shrink_prior) or shrink_prior < 0:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "shrink_prior must be finite and >= 0."))
        return _fail()

    mu, sigma, n, mflags = period_mean_std(arr)
    flags.extend(mflags)
    if n < min_obs:
        flags.append(fail_flag(QualityCode.SHORT_SAMPLE, f"Kelly ceiling needs at least {min_obs} observations."))
    if has_fail(flags):
        return _fail(mean_return=mu, std_return=sigma)

    se = sigma / math.sqrt(n)
    t_stat = mu / se if se > 0 else float("inf")
    if use_lower_confidence_mean:
        mu_used = mu - float(z_lower) * se
        shrink = float("nan")
        flags.append(
            warn_flag(
                "lower_confidence_mean",
                f"Using μ_lb = μ - {z_lower} * se = {mu_used} instead of t-shrinkage.",
            )
        )
    else:
        if not np.isfinite(t_stat):
            shrink = 1.0 if mu > 0 else 0.0
        else:
            shrink = float((t_stat**2) / (t_stat**2 + shrink_prior)) if t_stat**2 + shrink_prior > 0 else 0.0
        mu_used = float(shrink * mu)

    if not np.isfinite(mu_used) or mu_used <= 0:
        flags.append(
            fail_flag(
                QualityCode.NON_POSITIVE_EDGE,
                "Uncertainty-adjusted expected return is non-positive; ceiling is 0.",
            )
        )
        meta = make_meta(
            method="uncertainty_shrunk_fractional_kelly_ceiling",
            parameters={
                "fraction": fraction,
                "shrink_prior": shrink_prior,
                "min_obs": min_obs,
                "use_lower_confidence_mean": use_lower_confidence_mean,
                "caps": caps.to_dict(),
            },
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(flags),
            details={"t_stat": t_stat, "se_mean": se},
        )
        return KellyCeilingResult(
            n_obs=n,
            mean_return=float(mu),
            std_return=float(sigma),
            full_kelly=float(mu / (sigma**2)) if sigma else float("nan"),
            shrink_factor=float(shrink) if np.isfinite(shrink) else 0.0,
            shrunk_full_kelly=0.0,
            fraction=float(fraction),
            fractional_shrunk_kelly=0.0,
            binding_caps={},
            ceiling=0.0,
            role=role,
            quality_flags=tuple(flags),
            meta=meta.to_dict(),
        )

    full = float(mu / (sigma**2))
    shrunk_full = float(mu_used / (sigma**2))
    if shrunk_full < 0:
        shrunk_full = 0.0
    frac_kelly = float(fraction * shrunk_full)

    binding: dict[str, float] = {
        "fractional_shrunk_kelly": frac_kelly,
        "hard_leverage_cap": float(caps.hard_leverage_cap),
    }
    hard = _positive_cap("hard_leverage_cap", caps.hard_leverage_cap, flags)
    if hard is None:
        return _fail(mean_return=mu, std_return=sigma)

    vol_cap = None
    if caps.vol_target is not None:
        vt = _positive_cap("vol_target", caps.vol_target, flags)
        av = caps.asset_vol if caps.asset_vol is not None else float(sigma)
        av = _positive_cap("asset_vol", av, flags)
        if vt is not None and av is not None:
            if av == 0:
                flags.append(fail_flag(QualityCode.DEGENERATE_VARIANCE, "asset_vol is 0; vol-target cap undefined."))
            else:
                vol_cap = float(vt / av)
                binding["vol_target_cap"] = vol_cap

    conc = _positive_cap("concentration_max_weight", caps.concentration_max_weight, flags)
    if conc is not None:
        binding["concentration_max_weight"] = conc
    expo = _positive_cap("exposure_cap", caps.exposure_cap, flags)
    if expo is not None:
        binding["exposure_cap"] = expo
    liq = _positive_cap("liquidity_cap", caps.liquidity_cap, flags)
    if liq is not None:
        binding["liquidity_cap"] = liq
    rg = _positive_cap("risk_governor_cap", caps.risk_governor_cap, flags)
    if rg is None:
        flags.append(
            warn_flag(
                QualityCode.RISK_GOVERNOR_CAP_NOT_SUPPLIED,
                "RiskGovernor cap was not supplied. Research ceiling is still clipped by other caps; "
                "production sizing must not treat a missing RiskGovernor as unlimited capacity.",
            )
        )
    else:
        binding["risk_governor_cap"] = rg

    dd = caps.drawdown_throttle
    if dd is not None:
        if not np.isfinite(dd) or dd < 0 or dd > 1:
            flags.append(
                fail_flag(QualityCode.INVALID_INPUT, "drawdown_throttle must be in [0, 1].")
            )
        else:
            binding["drawdown_throttle"] = float(dd)

    if has_fail(flags):
        return _fail(mean_return=mu, std_return=sigma)

    ceiling = frac_kelly
    for name, cap_val in binding.items():
        if name == "drawdown_throttle":
            continue
        ceiling = min(ceiling, cap_val)
    if dd is not None and np.isfinite(dd):
        ceiling = ceiling * float(dd)
    ceiling = max(0.0, float(ceiling))

    # Invariant: never exceed fractional Kelly or hard cap.
    if ceiling > frac_kelly + 1e-12 or ceiling > hard + 1e-12:
        flags.append(fail_flag(QualityCode.COMPUTATION_ERROR, "Ceiling exceeded fractional Kelly or hard cap."))
        return _fail(mean_return=mu, std_return=sigma)

    flags.append(
        ok_flag(
            f"Kelly ceiling={ceiling:.6f} (role={role}); fractional_shrunk={frac_kelly:.6f}; "
            f"full_kelly={full:.6f} was not used as a target."
        )
    )
    meta = make_meta(
        method="uncertainty_shrunk_fractional_kelly_ceiling",
        parameters={
            "fraction": fraction,
            "shrink_prior": shrink_prior,
            "min_obs": min_obs,
            "use_lower_confidence_mean": use_lower_confidence_mean,
            "z_lower": z_lower,
            "caps": caps.to_dict(),
        },
        assumptions=_ASSUMPTIONS,
        quality_flags=tuple(flags),
        details={
            "t_stat": t_stat,
            "se_mean": se,
            "mu_used": mu_used,
            "subordinate_to": [
                "vol_target_cap",
                "concentration_max_weight",
                "drawdown_throttle",
                "exposure_cap",
                "liquidity_cap",
                "risk_governor_cap",
                "hard_leverage_cap",
            ],
        },
    )
    return KellyCeilingResult(
        n_obs=n,
        mean_return=float(mu),
        std_return=float(sigma),
        full_kelly=full,
        shrink_factor=float(shrink) if np.isfinite(shrink) else 0.0,
        shrunk_full_kelly=shrunk_full,
        fraction=float(fraction),
        fractional_shrunk_kelly=frac_kelly,
        binding_caps=binding,
        ceiling=ceiling,
        role=role,
        quality_flags=tuple(flags),
        meta=meta.to_dict(),
    )


_ASSUMPTIONS = (
    "f* = μ / σ² is the continuous Gaussian Kelly fraction on per-period returns.",
    "Returned value is a CEILING, never a target or an order size.",
    "Full Kelly (fraction >= 1) is rejected. Default fraction is 0.25.",
    "Uncertainty shrink: μ_shrunk = μ * t²/(t² + shrink_prior), t = μ / se(μ).",
    "Kelly is min()'d against vol-target, concentration, exposure, liquidity, hard leverage, then times drawdown throttle.",
    "RiskGovernor remains authoritative. This calculator does not implement or bypass it.",
    "No live broker, no production signal activation, no self-promotion.",
)
