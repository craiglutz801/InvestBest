"""Probability of Backtest Overfitting via CSCV.

Implements the Combinatorially Symmetric Cross-Validation estimator of
Bailey, Borwein, López de Prado and Zhu (2014), "The Probability of
Backtest Overfitting".

Algorithm
---------
1. Partition T observations into ``n_slices`` contiguous blocks of equal
   length (remainder bars at the end are dropped and flagged).
2. ``n_slices`` must be even. For every combination of ``n_slices/2``
   blocks used as in-sample (IS), the complement is out-of-sample (OOS).
3. On each combination, select the strategy with the best IS Sharpe.
4. Rank that strategy's OOS Sharpe among all strategies' OOS Sharpes.
   Relative rank λ = (# of strategies with strictly worse OOS + 0.5 * ties)
   / (N - 1). λ = 1 means the IS winner was the unique OOS best.
5. PBO = fraction of combinations with λ < 0.5.

Assumptions
-----------
- Performance metric is per-period Sharpe on concatenated slices.
- Strategies are columns of a T × N return matrix (strategy-agnostic).
- All C(n_slices, n_slices/2) combinations are enumerated in lexicographic
  order (deterministic). No random subsample.
- This is an estimator of PBO, not the exact probability of overfitting.
- N = 1 is undefined (no ranking) and fail-closed.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from northstar_promotion.arrays import has_fail, validate_2d
from northstar_promotion.metrics import period_sharpe
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag, warn_flag
from northstar_promotion.schema import make_meta


@dataclass(frozen=True)
class PBOResult:
    n_obs_used: int
    n_strategies: int
    n_slices: int
    n_combinations: int
    pbo: float
    mean_relative_rank: float
    n_overfit_combinations: int
    quality_flags: tuple[QualityFlag, ...]
    meta: dict

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "n_obs_used": self.n_obs_used,
            "n_strategies": self.n_strategies,
            "n_slices": self.n_slices,
            "n_combinations": self.n_combinations,
            "pbo": self.pbo,
            "mean_relative_rank": self.mean_relative_rank,
            "n_overfit_combinations": self.n_overfit_combinations,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def _sharpes(block: np.ndarray) -> np.ndarray:
    """Per-column period Sharpe. NaN if a column is unusable."""
    t, n = block.shape
    out = np.full(n, np.nan, dtype=float)
    if t < 2:
        return out
    for j in range(n):
        sr, flags = period_sharpe(block[:, j])
        if not has_fail(flags) and np.isfinite(sr):
            out[j] = sr
    return out


def _relative_rank(selected: int, oos: np.ndarray) -> float:
    n = int(oos.size)
    if n < 2 or not np.isfinite(oos[selected]):
        return float("nan")
    sel = oos[selected]
    others = np.delete(oos, selected)
    finite = others[np.isfinite(others)]
    if finite.size == 0:
        return float("nan")
    worse = float(np.sum(finite < sel))
    ties = float(np.sum(finite == sel))
    return (worse + 0.5 * ties) / float(finite.size)


def probability_of_backtest_overfitting(
    strategy_returns: Sequence[Sequence[float]] | np.ndarray,
    *,
    n_slices: int = 8,
    max_combinations: int = 12870,
) -> PBOResult:
    flags: list[QualityFlag] = []
    arr, vflags = validate_2d(strategy_returns, name="strategy_returns")
    flags.extend(vflags)

    def _fail(**extra: float | int) -> PBOResult:
        meta = make_meta(
            method="pbo_cscv",
            parameters={"n_slices": n_slices, "max_combinations": max_combinations},
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return PBOResult(
            n_obs_used=int(extra.get("n_obs_used", 0)),
            n_strategies=int(extra.get("n_strategies", 0)),
            n_slices=int(n_slices),
            n_combinations=int(extra.get("n_combinations", 0)),
            pbo=float("nan"),
            mean_relative_rank=float("nan"),
            n_overfit_combinations=int(extra.get("n_overfit_combinations", 0)),
            quality_flags=tuple(flags),
            meta=meta.to_dict(),
        )

    if has_fail(flags):
        return _fail()
    t, n = arr.shape
    if n < 2:
        flags.append(
            fail_flag(
                QualityCode.INSUFFICIENT_STRATEGIES,
                "PBO/CSCV needs at least 2 strategies (columns) to rank OOS performance.",
            )
        )
        return _fail(n_strategies=n, n_obs_used=t)
    if n_slices < 4 or n_slices % 2 != 0:
        flags.append(
            fail_flag(
                QualityCode.INSUFFICIENT_SLICES,
                "n_slices must be an even integer >= 4.",
            )
        )
        return _fail(n_strategies=n, n_obs_used=t)
    slice_len = t // n_slices
    if slice_len < 2:
        flags.append(
            fail_flag(
                QualityCode.SHORT_SAMPLE,
                f"Each CSCV slice would have length {slice_len}; need at least 2.",
            )
        )
        return _fail(n_strategies=n, n_obs_used=t)

    used = slice_len * n_slices
    dropped = t - used
    if dropped:
        flags.append(
            warn_flag(
                QualityCode.SHORT_SAMPLE,
                f"Dropped {dropped} trailing bars so T is divisible by n_slices={n_slices}.",
            )
        )
    data = arr[:used, :]
    slices = [data[i * slice_len : (i + 1) * slice_len, :] for i in range(n_slices)]

    k = n_slices // 2
    n_combos = math.comb(n_slices, k)
    if n_combos > max_combinations:
        flags.append(
            fail_flag(
                QualityCode.INVALID_INPUT,
                f"C({n_slices},{k})={n_combos} exceeds max_combinations={max_combinations}. "
                "Reduce n_slices rather than subsample randomly.",
            )
        )
        return _fail(n_strategies=n, n_obs_used=used, n_combinations=n_combos)

    ranks: list[float] = []
    skipped = 0
    for combo in itertools.combinations(range(n_slices), k):
        is_idx = list(combo)
        oos_idx = [i for i in range(n_slices) if i not in set(is_idx)]
        is_block = np.concatenate([slices[i] for i in is_idx], axis=0)
        oos_block = np.concatenate([slices[i] for i in oos_idx], axis=0)
        is_sr = _sharpes(is_block)
        oos_sr = _sharpes(oos_block)
        if not np.any(np.isfinite(is_sr)):
            skipped += 1
            continue
        selected = int(np.nanargmax(is_sr))
        lam = _relative_rank(selected, oos_sr)
        if not np.isfinite(lam):
            skipped += 1
            continue
        ranks.append(lam)

    if not ranks:
        flags.append(
            fail_flag(QualityCode.NOT_COMPUTED, "Every CSCV combination was unusable (NaN Sharpes).")
        )
        return _fail(n_strategies=n, n_obs_used=used, n_combinations=n_combos)

    ranks_arr = np.asarray(ranks, dtype=float)
    n_overfit = int(np.sum(ranks_arr < 0.5))
    pbo = float(n_overfit / ranks_arr.size)
    mean_rank = float(np.mean(ranks_arr))
    if skipped:
        flags.append(
            warn_flag(
                QualityCode.MISSING_DATA,
                f"Skipped {skipped} CSCV combinations with undefined Sharpes.",
            )
        )
    flags.append(ok_flag(f"CSCV PBO={pbo:.4f} over {ranks_arr.size} combinations (N={n} strategies)."))
    meta = make_meta(
        method="pbo_cscv_bailey_2014",
        parameters={
            "n_slices": n_slices,
            "max_combinations": max_combinations,
            "n_combinations_enumerated": int(ranks_arr.size),
            "n_combinations_total": n_combos,
            "skipped_combinations": skipped,
        },
        assumptions=_ASSUMPTIONS,
        quality_flags=tuple(flags),
        details={"slice_length": slice_len, "dropped_bars": dropped},
    )
    return PBOResult(
        n_obs_used=used,
        n_strategies=n,
        n_slices=n_slices,
        n_combinations=int(ranks_arr.size),
        pbo=pbo,
        mean_relative_rank=mean_rank,
        n_overfit_combinations=n_overfit,
        quality_flags=tuple(flags),
        meta=meta.to_dict(),
    )


_ASSUMPTIONS = (
    "Bailey, Borwein, López de Prado, Zhu (2014), CSCV estimator of PBO.",
    "Relative rank λ < 0.5 means the IS winner was below the OOS median.",
    "Ties in OOS Sharpe contribute 0.5 to the 'worse' count (mid-rank).",
    "Slices are contiguous equal-length partitions; combinations are exhaustive and deterministic.",
    "Independent noise across strategies yields PBO around 1/2 in large samples; this is a sanity check, not a proof.",
    "A genuine all-period edge in one column should produce PBO well below 1/2.",
)
