"""Neighboring-parameter / plateau robustness (never picks a winner).

Chan Stage 3 rule: no trend enhancement is promoted because one optimized
lookback wins a backtest. These utilities report neighborhood agreement and
explicitly refuse single-horizon selection from a performance sweep.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Sequence

import numpy as np

from northstar_trend_carry.momentum import EnsembleConfig, horizon_strength_for_lookback
from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import QualityFlag, RESEARCH_ONLY_NOTE, jsonable, utcnow
from northstar_trend_carry.series import PriceSeries, validate_and_slice

REFUSAL_NOTE = (
    "Stage 3 does not choose a single optimized horizon from a performance sweep. "
    "selected_lookback is always None."
)


@dataclass(frozen=True)
class LookbackObservation:
    lookback_bars: int
    sign: int
    capped_strength: float | None
    usable: bool

    def to_dict(self) -> dict:
        return {
            "lookback_bars": self.lookback_bars,
            "sign": self.sign,
            "capped_strength": jsonable(self.capped_strength),
            "usable": self.usable,
        }


@dataclass(frozen=True)
class PlateauReport:
    """Neighborhood robustness. selected_lookback is always None."""

    as_of: datetime | None
    computed_at: datetime
    center_lookbacks: tuple[int, ...]
    radius: int
    observations: tuple[LookbackObservation, ...]
    neighborhood_sign_agreement: float | None
    plateau_width: int
    modal_sign: int
    selected_lookback: None
    refuses_single_horizon_selection: bool
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...] = (RESEARCH_ONLY_NOTE, REFUSAL_NOTE)

    def to_dict(self) -> dict:
        return {
            "as_of": jsonable(self.as_of),
            "computed_at": jsonable(self.computed_at),
            "center_lookbacks": list(self.center_lookbacks),
            "radius": self.radius,
            "observations": [o.to_dict() for o in self.observations],
            "neighborhood_sign_agreement": jsonable(self.neighborhood_sign_agreement),
            "plateau_width": self.plateau_width,
            "modal_sign": self.modal_sign,
            "selected_lookback": self.selected_lookback,
            "refuses_single_horizon_selection": self.refuses_single_horizon_selection,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "is_order": False,
        }


@dataclass(frozen=True)
class HorizonSelectionRefusal:
    """Explicit refusal to promote the argmax of a lookback → metric table."""

    sweep_lookbacks: tuple[int, ...]
    sweep_metrics: Mapping[int, float]
    highest_metric_lookback: int | None
    highest_metric_value: float | None
    metric_dispersion: float | None
    selected_lookback: None
    refuses_single_horizon_selection: bool
    reason: str
    notes: tuple[str, ...] = (RESEARCH_ONLY_NOTE, REFUSAL_NOTE)

    def to_dict(self) -> dict:
        return {
            "sweep_lookbacks": list(self.sweep_lookbacks),
            "sweep_metrics": {str(k): jsonable(v) for k, v in self.sweep_metrics.items()},
            "highest_metric_lookback": self.highest_metric_lookback,
            "highest_metric_value": jsonable(self.highest_metric_value),
            "metric_dispersion": jsonable(self.metric_dispersion),
            "selected_lookback": self.selected_lookback,
            "refuses_single_horizon_selection": self.refuses_single_horizon_selection,
            "reason": self.reason,
            "notes": list(self.notes),
            "used_for_trading": False,
        }


def neighboring_parameter_plateau(
    series: PriceSeries,
    *,
    center_lookbacks: Sequence[int] | None = None,
    radius: int = 5,
    config: EnsembleConfig | None = None,
    as_of: datetime | int | None = None,
    computed_at: datetime | None = None,
) -> PlateauReport:
    cfg = config or EnsembleConfig()
    centers = tuple(
        int(x)
        for x in (
            center_lookbacks
            if center_lookbacks is not None
            else tuple(h.lookback_bars for h in cfg.horizons)
        )
    )
    sliced = validate_and_slice(series, as_of=as_of)
    flags = list(sliced.quality_flags)
    if radius < 0:
        flags.append(flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, "radius must be >= 0"))
    if any(c <= 0 for c in centers):
        flags.append(flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, "lookbacks must be > 0"))

    lookbacks: list[int] = []
    for c in centers:
        for L in range(c - radius, c + radius + 1):
            if L > 0:
                lookbacks.append(L)
    unique = tuple(sorted(set(lookbacks)))
    observations: list[LookbackObservation] = []

    if sliced.is_usable and not any(f.level is QualityLevel.FAIL for f in flags):
        for L in unique:
            hs = horizon_strength_for_lookback(sliced.values, L, cfg)
            observations.append(
                LookbackObservation(
                    lookback_bars=L,
                    sign=hs.sign,
                    capped_strength=hs.capped_strength,
                    usable=hs.is_usable,
                )
            )
    else:
        observations = [
            LookbackObservation(lookback_bars=L, sign=0, capped_strength=None, usable=False)
            for L in unique
        ]

    usable_obs = [o for o in observations if o.usable]
    signs = [o.sign for o in usable_obs if o.sign != 0]
    if signs:
        values, counts = np.unique(signs, return_counts=True)
        modal = int(values[int(np.argmax(counts))])
        agreement = float(sum(1 for s in signs if s == modal) / len(signs))
    else:
        modal = 0
        agreement = None

    plateau_width = 0
    if usable_obs:
        run = 0
        best = 0
        prev = None
        for o in usable_obs:
            if o.sign == 0:
                run = 0
                prev = None
                continue
            if prev is not None and o.sign == prev:
                run += 1
            else:
                run = 1
                prev = o.sign
            best = max(best, run)
        plateau_width = best

    return PlateauReport(
        as_of=sliced.as_of,
        computed_at=computed_at or utcnow(),
        center_lookbacks=centers,
        radius=int(radius),
        observations=tuple(observations),
        neighborhood_sign_agreement=agreement,
        plateau_width=int(plateau_width),
        modal_sign=modal,
        selected_lookback=None,
        refuses_single_horizon_selection=True,
        quality_flags=tuple(flags),
    )


def refuse_performance_sweep_selection(
    lookback_to_metric: Mapping[int, float],
) -> HorizonSelectionRefusal:
    """Accept a lookback → metric table and refuse to pick the argmax."""

    cleaned: dict[int, float] = {}
    for k, v in lookback_to_metric.items():
        lk = int(k)
        fv = float(v)
        if fv == fv and fv not in (float("inf"), float("-inf")):
            cleaned[lk] = fv

    highest_L = None
    highest_v = None
    dispersion = None
    if cleaned:
        highest_L = max(cleaned, key=lambda k: cleaned[k])
        highest_v = cleaned[highest_L]
        vals = np.asarray(list(cleaned.values()), dtype=float)
        dispersion = float(np.std(vals, ddof=0)) if vals.size else None

    return HorizonSelectionRefusal(
        sweep_lookbacks=tuple(sorted(cleaned)),
        sweep_metrics=cleaned,
        highest_metric_lookback=highest_L,
        highest_metric_value=highest_v,
        metric_dispersion=dispersion,
        selected_lookback=None,
        refuses_single_horizon_selection=True,
        reason=(
            "A performance sweep is diagnostic evidence of overfitting risk, not a "
            "license to promote the winning lookback. Stage 3 reports the highest "
            "metric lookback for audit only and leaves selected_lookback = None."
        ),
    )
