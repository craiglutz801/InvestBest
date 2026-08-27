"""Trade / P&L concentration diagnostics.

Surfaces how much of total P&L is concentrated in a few trades or a few
time buckets. High concentration is a falsification warning: the backtest
may be a handful of lucky bets rather than a repeatable process.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from northstar_promotion.arrays import has_fail, validate_1d
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag, warn_flag
from northstar_promotion.schema import make_meta


@dataclass(frozen=True)
class ConcentrationReport:
    n_trades: int
    total_pnl: float
    herfindahl: float
    top1_share: float
    top5_share: float
    max_trade_pnl: float
    positive_trade_share_of_gains: float
    quality_flags: tuple[QualityFlag, ...]
    meta: dict
    veto: bool

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "n_trades": self.n_trades,
            "total_pnl": self.total_pnl,
            "herfindahl": self.herfindahl,
            "top1_share": self.top1_share,
            "top5_share": self.top5_share,
            "max_trade_pnl": self.max_trade_pnl,
            "positive_trade_share_of_gains": self.positive_trade_share_of_gains,
            "veto": self.veto,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def trade_pnl_concentration(
    trade_pnl: Sequence[float] | np.ndarray,
    *,
    max_top1_share: float | None = None,
    max_herfindahl: float | None = None,
    min_trades: int = 5,
) -> ConcentrationReport:
    flags: list[QualityFlag] = []
    arr, vflags = validate_1d(trade_pnl, name="trade_pnl")
    flags.extend(vflags)
    if has_fail(flags):
        meta = make_meta(
            method="trade_pnl_concentration",
            parameters={
                "max_top1_share": max_top1_share,
                "max_herfindahl": max_herfindahl,
                "min_trades": min_trades,
            },
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return ConcentrationReport(0, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), tuple(flags), meta.to_dict(), True)

    n = int(arr.size)
    if n < min_trades:
        flags.append(
            fail_flag(QualityCode.SHORT_SAMPLE, f"Need at least {min_trades} trades to assess concentration.")
        )

    total = float(np.sum(arr))
    max_trade = float(np.max(arr)) if n else float("nan")
    # HHI and top-k shares are defined on positive P&L mass so a large loser
    # does not mechanically "diversify" a concentrated winner.
    gains = np.clip(arr, 0.0, None)
    gain_sum = float(np.sum(gains))
    if gain_sum <= 0:
        flags.append(
            fail_flag(
                QualityCode.DEGENERATE_VARIANCE,
                "No positive trade P&L; concentration of gains is undefined.",
            )
        )
        hhi = top1 = top5 = pos_share = float("nan")
    else:
        shares = gains / gain_sum
        hhi = float(np.sum(shares**2))
        ordered = np.sort(shares)[::-1]
        top1 = float(ordered[0])
        top5 = float(np.sum(ordered[: min(5, ordered.size)]))
        pos_share = float(np.sum(gains > 0) / n)

    veto = has_fail(flags)
    if np.isfinite(top1) and max_top1_share is not None and top1 > max_top1_share:
        flags.append(
            fail_flag(
                "pnl_concentration",
                f"Top-1 positive P&L share {top1} exceeds cap {max_top1_share}.",
            )
        )
        veto = True
    if np.isfinite(hhi) and max_herfindahl is not None and hhi > max_herfindahl:
        flags.append(
            fail_flag(
                "pnl_concentration",
                f"P&L HHI {hhi} exceeds cap {max_herfindahl}.",
            )
        )
        veto = True
    if np.isfinite(top1) and top1 >= 0.5:
        flags.append(
            warn_flag(
                "pnl_concentration_surfaced",
                f"Top trade accounts for {top1:.1%} of positive P&L (HHI={hhi}).",
            )
        )
    elif np.isfinite(top1) and not veto:
        flags.append(ok_flag(f"P&L concentration surfaced: top1={top1:.3f}, HHI={hhi:.3f}."))

    meta = make_meta(
        method="trade_pnl_concentration",
        parameters={
            "max_top1_share": max_top1_share,
            "max_herfindahl": max_herfindahl,
            "min_trades": min_trades,
        },
        assumptions=_ASSUMPTIONS,
        quality_flags=tuple(flags),
        details={"n_trades": n},
    )
    return ConcentrationReport(
        n_trades=n,
        total_pnl=total,
        herfindahl=hhi,
        top1_share=top1,
        top5_share=top5,
        max_trade_pnl=max_trade,
        positive_trade_share_of_gains=pos_share,
        quality_flags=tuple(flags),
        meta=meta.to_dict(),
        veto=veto,
    )


_ASSUMPTIONS = (
    "Herfindahl-Hirschman index and top-k shares use the positive P&L mass.",
    "A single large winner dominating total gains is surfaced even when no hard cap is set.",
    "This diagnostic does not prove robustness; it only rejects or flags concentrated luck.",
)
