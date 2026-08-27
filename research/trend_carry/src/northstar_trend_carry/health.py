"""Trend-health diagnostics (research evidence only; not throttle authority).

Stage 4 will own formal healthy/degraded/paused/retire states. This module
reports the raw ingredients: horizon agreement, persistence, whipsaw rate,
volatility-shock state, and cross-market breadth.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import numpy as np

from northstar_trend_carry.momentum import (
    AssetTrendSignal,
    EnsembleConfig,
    evaluate_asset_trend,
    rolling_ensemble_signs,
)
from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import QualityFlag, RESEARCH_ONLY_NOTE, jsonable, utcnow
from northstar_trend_carry.series import PriceSeries, daily_vol, log_returns, validate_and_slice

HEALTH_ASSUMPTIONS = (
    "Horizon agreement is the fraction of usable horizons whose sign matches the ensemble.",
    "Persistence is the fraction of trailing bars whose PIT ensemble sign matches the current sign.",
    "Whipsaw rate is PIT ensemble sign flips / (bars - 1) over the whipsaw window.",
    "Volatility shock compares current realized vol to a longer trailing median.",
    "Breadth is the fraction of a caller-supplied universe with positive ensemble sign.",
    "These diagnostics do not place orders or authorize sizing changes.",
)


@dataclass(frozen=True)
class TrendHealthReport:
    symbol: str
    as_of: datetime | None
    computed_at: datetime
    horizon_agreement: float | None
    n_horizons_usable: int
    n_horizons_agreeing: int
    persistence: float | None
    persistence_window_bars: int
    whipsaw_rate: float | None
    whipsaw_window_bars: int
    vol_shock_ratio: float | None
    vol_shock_state: str
    breadth_long_fraction: float | None
    research_health_label: str
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...] = (RESEARCH_ONLY_NOTE, *HEALTH_ASSUMPTIONS)

    @property
    def is_usable(self) -> bool:
        return not any(f.level is QualityLevel.FAIL for f in self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "as_of": jsonable(self.as_of),
            "computed_at": jsonable(self.computed_at),
            "horizon_agreement": jsonable(self.horizon_agreement),
            "n_horizons_usable": self.n_horizons_usable,
            "n_horizons_agreeing": self.n_horizons_agreeing,
            "persistence": jsonable(self.persistence),
            "persistence_window_bars": self.persistence_window_bars,
            "whipsaw_rate": jsonable(self.whipsaw_rate),
            "whipsaw_window_bars": self.whipsaw_window_bars,
            "vol_shock_ratio": jsonable(self.vol_shock_ratio),
            "vol_shock_state": self.vol_shock_state,
            "breadth_long_fraction": jsonable(self.breadth_long_fraction),
            "research_health_label": self.research_health_label,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "is_usable": self.is_usable,
            "is_order": False,
            "authorizes_throttle": False,
        }


def evaluate_trend_health(
    series: PriceSeries,
    signal: AssetTrendSignal | None = None,
    config: EnsembleConfig | None = None,
    *,
    as_of: datetime | int | None = None,
    universe_signals: Sequence[AssetTrendSignal] | None = None,
    persistence_window_bars: int = 21,
    whipsaw_window_bars: int = 63,
    vol_shock_lookback_bars: int = 252,
    vol_shock_ratio_threshold: float = 2.0,
    computed_at: datetime | None = None,
) -> TrendHealthReport:
    cfg = config or (signal.config if signal is not None else EnsembleConfig())
    trend = signal or evaluate_asset_trend(series, cfg, as_of=as_of, computed_at=computed_at)
    sliced = validate_and_slice(series, as_of=as_of)
    computed = computed_at or utcnow()
    flags = list(trend.quality_flags)

    usable = [h for h in trend.horizons if h.is_usable]
    agreeing = [h for h in usable if trend.ensemble_sign == 0 or h.sign == trend.ensemble_sign]
    n_usable = len(usable)
    n_agree = len(agreeing)
    agreement = (n_agree / n_usable) if n_usable else None
    if agreement is not None and agreement < 1.0 and n_usable >= 2:
        flags.append(
            flag(
                QualityCode.MIXED_HORIZON_SIGNS,
                QualityLevel.WARN,
                f"Horizon agreement {agreement:.2f} < 1",
            )
        )

    persistence = None
    whipsaw_rate = None
    if sliced.is_usable and sliced.values.size >= 3:
        start = max(0, sliced.values.size - max(persistence_window_bars, whipsaw_window_bars) - 1)
        signs = rolling_ensemble_signs(sliced.values, cfg, start_index=start)
        current = int(trend.ensemble_sign)
        pers_slice = signs[-persistence_window_bars:]
        if pers_slice.size:
            persistence = float(np.mean(pers_slice == current)) if current != 0 else float(
                np.mean(pers_slice == 0)
            )
        whip_slice = signs[-whipsaw_window_bars:]
        if whip_slice.size >= 2:
            flips = int(np.sum(whip_slice[1:] != whip_slice[:-1]))
            whipsaw_rate = flips / float(whip_slice.size - 1)
            if whipsaw_rate >= 0.25:
                flags.append(
                    flag(
                        QualityCode.HIGH_WHIPSAW,
                        QualityLevel.WARN,
                        f"Whipsaw rate {whipsaw_rate:.2f} is elevated",
                    )
                )

    vol_ratio = None
    vol_state = "unavailable"
    if sliced.is_usable:
        current_vol = daily_vol(sliced.values, vol_lookback_bars=cfg.vol_lookback_bars)
        rets = log_returns(sliced.values)
        if current_vol is not None and rets.size >= 10:
            trailing = rets[-vol_shock_lookback_bars:] if rets.size >= 20 else rets
            # rolling 21-day vol path for a median baseline
            baseline_vols: list[float] = []
            w = min(21, trailing.size)
            for i in range(w, trailing.size + 1):
                chunk = trailing[i - w : i]
                std = float(np.std(chunk, ddof=1))
                if std > 0 and np.isfinite(std):
                    baseline_vols.append(std)
            if baseline_vols:
                median_vol = float(np.median(baseline_vols))
                if median_vol > 0:
                    vol_ratio = current_vol / median_vol
                    if vol_ratio >= vol_shock_ratio_threshold:
                        vol_state = "shock"
                        flags.append(
                            flag(
                                QualityCode.VOLATILITY_SHOCK,
                                QualityLevel.WARN,
                                f"Vol shock ratio {vol_ratio:.2f} >= {vol_shock_ratio_threshold:g}",
                            )
                        )
                    elif vol_ratio >= 1.25:
                        vol_state = "elevated"
                    else:
                        vol_state = "normal"

    breadth = None
    if universe_signals:
        usable_u = [s for s in universe_signals if s.is_usable]
        if usable_u:
            breadth = sum(1 for s in usable_u if s.ensemble_sign > 0) / float(len(usable_u))

    if not trend.is_usable:
        label = "not_computed"
        flags.append(
            flag(QualityCode.NOT_COMPUTED, QualityLevel.FAIL, "Underlying trend signal is not usable")
        )
    elif vol_state == "shock" or (whipsaw_rate is not None and whipsaw_rate >= 0.35):
        label = "degraded"
    elif agreement is not None and agreement < 0.5:
        label = "mixed"
    elif trend.ensemble_sign == 0:
        label = "mixed"
    else:
        label = "healthy"

    return TrendHealthReport(
        symbol=series.symbol,
        as_of=sliced.as_of or trend.as_of,
        computed_at=computed,
        horizon_agreement=agreement,
        n_horizons_usable=n_usable,
        n_horizons_agreeing=n_agree,
        persistence=persistence,
        persistence_window_bars=persistence_window_bars,
        whipsaw_rate=whipsaw_rate,
        whipsaw_window_bars=whipsaw_window_bars,
        vol_shock_ratio=vol_ratio,
        vol_shock_state=vol_state,
        breadth_long_fraction=breadth,
        research_health_label=label,
        quality_flags=tuple(flags),
    )
