"""Multi-speed time-series momentum ensemble (research only).

Default horizons approximate 1m / 3m / 6m / 12m trading days. The ensemble is
equal-weight across capped, volatility-normalized horizon strengths. This module
never selects a single lookback from a performance sweep.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

import numpy as np

from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import (
    DEFAULT_HORIZONS,
    EnsembleConfig,
    HorizonSpec,
    QualityFlag,
    RESEARCH_ONLY_NOTE,
    SampleWindow,
    jsonable,
    library_versions,
    utcnow,
)
from northstar_trend_carry.series import (
    PriceSeries,
    daily_vol,
    validate_and_slice,
)

MOMENTUM_ASSUMPTIONS = (
    "Time-series momentum: sign and strength of the trailing total return at each horizon.",
    "Strength = (price_t / price_{t-L} - 1) / (daily_vol * sqrt(L)), then clipped to ±signal_cap.",
    "Ensemble is equal-weight of usable capped horizon strengths, never an optimized lookback.",
    "Volatility normalization uses only returns at or before as_of.",
    "allow_short controls research expression only; it is not broker permission or live shorting.",
    "A non-zero ensemble strength is not an order and is not wired to the portfolio engine.",
)


@dataclass(frozen=True)
class HorizonSignal:
    horizon: HorizonSpec
    raw_return: float | None
    daily_realized_vol: float | None
    vol_normalized_strength: float | None
    capped_strength: float | None
    sign: int
    expression: str
    quality_flags: tuple[QualityFlag, ...]

    @property
    def is_usable(self) -> bool:
        return self.capped_strength is not None and not any(
            f.level is QualityLevel.FAIL for f in self.quality_flags
        )

    def to_dict(self) -> dict:
        return {
            "horizon": self.horizon.to_dict(),
            "raw_return": jsonable(self.raw_return),
            "daily_realized_vol": jsonable(self.daily_realized_vol),
            "vol_normalized_strength": jsonable(self.vol_normalized_strength),
            "capped_strength": jsonable(self.capped_strength),
            "sign": self.sign,
            "expression": self.expression,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
        }


@dataclass(frozen=True)
class AssetTrendSignal:
    """Portfolio-ready research signal contract. Not live portfolio input."""

    symbol: str
    asset_class: str | None
    as_of: datetime | None
    computed_at: datetime
    sample: SampleWindow
    config: EnsembleConfig
    horizons: tuple[HorizonSignal, ...]
    ensemble_strength: float | None
    ensemble_sign: int
    ensemble_expression: str
    ensemble_method: str
    shorting_permitted_in_research: bool
    quality_flags: tuple[QualityFlag, ...]
    interpretation: str
    notes: tuple[str, ...] = (RESEARCH_ONLY_NOTE,)

    @property
    def is_usable(self) -> bool:
        return self.ensemble_strength is not None and not any(
            f.level is QualityLevel.FAIL for f in self.quality_flags
        )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "as_of": jsonable(self.as_of),
            "computed_at": jsonable(self.computed_at),
            "sample": self.sample.to_dict(),
            "config": self.config.to_dict(),
            "horizons": [h.to_dict() for h in self.horizons],
            "ensemble_strength": jsonable(self.ensemble_strength),
            "ensemble_sign": self.ensemble_sign,
            "ensemble_expression": self.ensemble_expression,
            "ensemble_method": self.ensemble_method,
            "shorting_permitted_in_research": self.shorting_permitted_in_research,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "interpretation": self.interpretation,
            "notes": list(self.notes),
            "is_usable": self.is_usable,
            "is_order": False,
            "activates_production_signal": False,
            "library_versions": library_versions(),
            "schema_version": "0.1.0",
        }


@dataclass(frozen=True)
class CrossAssetTrendSnapshot:
    """Cross-symbol research snapshot. Does not mutate the live portfolio engine."""

    as_of: datetime | None
    computed_at: datetime
    assets: tuple[AssetTrendSignal, ...]
    breadth_long_fraction: float | None
    breadth_short_fraction: float | None
    research_weights: Mapping[str, float]
    weight_method: str
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...] = (
        RESEARCH_ONLY_NOTE,
        "research_weights are diagnostic equal-risk research weights, not live orders.",
    )

    def to_dict(self) -> dict:
        return {
            "as_of": jsonable(self.as_of),
            "computed_at": jsonable(self.computed_at),
            "assets": [a.to_dict() for a in self.assets],
            "breadth_long_fraction": jsonable(self.breadth_long_fraction),
            "breadth_short_fraction": jsonable(self.breadth_short_fraction),
            "research_weights": dict(self.research_weights),
            "weight_method": self.weight_method,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "is_order": False,
            "wired_to_live_portfolio_engine": False,
            "library_versions": library_versions(),
        }


def _sign(value: float | None) -> int:
    if value is None or value == 0.0 or value != value:
        return 0
    return 1 if value > 0 else -1


def _expression(sign: int, allow_short: bool) -> str:
    if sign > 0:
        return "long"
    if sign < 0:
        return "short" if allow_short else "flat"
    return "flat"


def _horizon_signal(
    prices: np.ndarray,
    spec: HorizonSpec,
    config: EnsembleConfig,
) -> HorizonSignal:
    flags: list[QualityFlag] = []
    n = int(prices.size)
    L = int(spec.lookback_bars)
    if L <= 0:
        flags.append(
            flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, f"lookback_bars must be > 0, got {L}")
        )
        return HorizonSignal(spec, None, None, None, None, 0, "flat", tuple(flags))
    if n < L + 1 or n < config.min_horizon_obs:
        flags.append(
            flag(
                QualityCode.SHORT_SAMPLE,
                QualityLevel.FAIL,
                f"Need at least {L + 1} observations for horizon {spec.name}",
            )
        )
        return HorizonSignal(spec, None, None, None, None, 0, "flat", tuple(flags))

    p_now = float(prices[-1])
    p_then = float(prices[-1 - L])
    if not np.isfinite(p_now) or not np.isfinite(p_then) or p_then <= 0 or p_now <= 0:
        flags.append(
            flag(QualityCode.NON_FINITE, QualityLevel.FAIL, "Non-finite or non-positive endpoint prices")
        )
        return HorizonSignal(spec, None, None, None, None, 0, "flat", tuple(flags))

    raw = p_now / p_then - 1.0
    dvol = daily_vol(prices, vol_lookback_bars=config.vol_lookback_bars)
    if dvol is None:
        flags.append(
            flag(
                QualityCode.DEGENERATE_VARIANCE,
                QualityLevel.FAIL,
                "Realized volatility is undefined (short window or zero variance)",
            )
        )
        return HorizonSignal(spec, raw, None, None, None, _sign(raw), "flat", tuple(flags))

    denom = dvol * float(np.sqrt(L))
    if denom <= 0 or not np.isfinite(denom):
        flags.append(
            flag(QualityCode.DEGENERATE_VARIANCE, QualityLevel.FAIL, "Volatility scaling denominator invalid")
        )
        return HorizonSignal(spec, raw, dvol, None, None, _sign(raw), "flat", tuple(flags))

    strength = raw / denom
    cap = abs(float(config.signal_cap))
    capped = float(np.clip(strength, -cap, cap))
    if abs(strength) > cap + 1e-15:
        flags.append(
            flag(
                QualityCode.RESEARCH_ONLY,
                QualityLevel.OK,
                f"Strength capped at ±{cap:g}",
            )
        )

    sign = _sign(capped)
    expression = _expression(sign, config.allow_short)
    applied = capped
    if sign < 0 and not config.allow_short:
        applied = 0.0
        sign = 0
        expression = "flat"
        flags.append(
            flag(
                QualityCode.SHORT_EXPRESSION_BLOCKED,
                QualityLevel.WARN,
                "Negative strength flattened because allow_short is False (research expression only)",
            )
        )

    return HorizonSignal(
        horizon=spec,
        raw_return=float(raw),
        daily_realized_vol=float(dvol),
        vol_normalized_strength=float(strength),
        capped_strength=float(applied),
        sign=int(sign),
        expression=expression,
        quality_flags=tuple(flags),
    )


def evaluate_asset_trend(
    series: PriceSeries,
    config: EnsembleConfig | None = None,
    *,
    as_of: datetime | int | None = None,
    computed_at: datetime | None = None,
) -> AssetTrendSignal:
    cfg = config or EnsembleConfig()
    sliced = validate_and_slice(series, as_of=as_of)
    computed = computed_at or utcnow()
    flags = list(sliced.quality_flags)

    if not cfg.horizons:
        flags.append(flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, "horizons must be non-empty"))
    if cfg.signal_cap <= 0 or not np.isfinite(cfg.signal_cap):
        flags.append(flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, "signal_cap must be finite and > 0"))
    if cfg.vol_lookback_bars < 2:
        flags.append(flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, "vol_lookback_bars must be >= 2"))

    fail_closed = any(f.level is QualityLevel.FAIL for f in flags)
    if fail_closed:
        empty_horizons = tuple(
            HorizonSignal(h, None, None, None, None, 0, "flat", (flags[0],))
            if flags
            else HorizonSignal(h, None, None, None, None, 0, "flat", ())
            for h in (cfg.horizons or DEFAULT_HORIZONS)
        )
        return AssetTrendSignal(
            symbol=series.symbol,
            asset_class=series.asset_class,
            as_of=sliced.as_of,
            computed_at=computed,
            sample=sliced.sample,
            config=cfg,
            horizons=empty_horizons,
            ensemble_strength=None,
            ensemble_sign=0,
            ensemble_expression="flat",
            ensemble_method="equal_weight_capped_horizons",
            shorting_permitted_in_research=cfg.allow_short,
            quality_flags=tuple(flags),
            interpretation="not_computed",
        )

    horizons = tuple(_horizon_signal(sliced.values, spec, cfg) for spec in cfg.horizons)
    usable = [h for h in horizons if h.is_usable and h.capped_strength is not None]
    for h in horizons:
        if not h.is_usable:
            flags.append(
                flag(
                    QualityCode.HORIZON_UNAVAILABLE,
                    QualityLevel.WARN,
                    f"Horizon {h.horizon.name} unavailable",
                )
            )

    if not usable:
        flags.append(
            flag(
                QualityCode.SHORT_SAMPLE,
                QualityLevel.FAIL,
                "No usable horizons; ensemble not computed",
            )
        )
        return AssetTrendSignal(
            symbol=series.symbol,
            asset_class=series.asset_class,
            as_of=sliced.as_of,
            computed_at=computed,
            sample=sliced.sample,
            config=cfg,
            horizons=horizons,
            ensemble_strength=None,
            ensemble_sign=0,
            ensemble_expression="flat",
            ensemble_method="equal_weight_capped_horizons",
            shorting_permitted_in_research=cfg.allow_short,
            quality_flags=tuple(flags),
            interpretation="not_computed",
        )

    ensemble = float(np.mean([h.capped_strength for h in usable]))  # type: ignore[misc]
    signs = {h.sign for h in usable if h.sign != 0}
    if len(signs) > 1:
        flags.append(
            flag(
                QualityCode.MIXED_HORIZON_SIGNS,
                QualityLevel.WARN,
                "Usable horizons disagree on sign",
            )
        )

    sign = _sign(ensemble)
    expression = _expression(sign, cfg.allow_short)
    if sign < 0 and not cfg.allow_short:
        ensemble = 0.0
        sign = 0
        expression = "flat"

    if sign > 0:
        interpretation = "research_uptrend_ensemble (not a trade)"
    elif sign < 0:
        interpretation = "research_downtrend_ensemble (not a trade)"
    else:
        interpretation = "research_flat_or_mixed_ensemble (not a trade)"

    return AssetTrendSignal(
        symbol=series.symbol,
        asset_class=series.asset_class,
        as_of=sliced.as_of,
        computed_at=computed,
        sample=sliced.sample,
        config=cfg,
        horizons=horizons,
        ensemble_strength=ensemble,
        ensemble_sign=sign,
        ensemble_expression=expression,
        ensemble_method="equal_weight_capped_horizons",
        shorting_permitted_in_research=cfg.allow_short,
        quality_flags=tuple(flags),
        interpretation=interpretation,
        notes=(RESEARCH_ONLY_NOTE, *MOMENTUM_ASSUMPTIONS),
    )


def evaluate_cross_asset_trend(
    series_by_symbol: Mapping[str, PriceSeries],
    config: EnsembleConfig | None = None,
    *,
    as_of: datetime | int | None = None,
    computed_at: datetime | None = None,
) -> CrossAssetTrendSnapshot:
    """Cross-asset research snapshot. Does not call the live portfolio engine."""

    cfg = config or EnsembleConfig()
    computed = computed_at or utcnow()
    assets = tuple(
        evaluate_asset_trend(series, cfg, as_of=as_of, computed_at=computed)
        for series in series_by_symbol.values()
    )
    usable = [a for a in assets if a.is_usable]
    n = len(usable)
    longs = sum(1 for a in usable if a.ensemble_sign > 0)
    shorts = sum(1 for a in usable if a.ensemble_sign < 0)
    breadth_long = (longs / n) if n else None
    breadth_short = (shorts / n) if n else None

    weights: dict[str, float] = {}
    raw: dict[str, float] = {}
    for asset in usable:
        assert asset.ensemble_strength is not None
        vol = None
        for h in asset.horizons:
            if h.daily_realized_vol is not None:
                vol = h.daily_realized_vol
                break
        if vol is None or vol <= 0:
            continue
        scaled = asset.ensemble_strength * (cfg.vol_target / (vol * np.sqrt(cfg.annualization_bars)))
        if not cfg.allow_short:
            scaled = max(0.0, scaled)
        raw[asset.symbol] = float(scaled)

    total_abs = float(sum(abs(v) for v in raw.values()))
    if total_abs > 0:
        weights = {k: v / total_abs for k, v in raw.items()}
    flags: list[QualityFlag] = []
    if not usable:
        flags.append(
            flag(QualityCode.SHORT_SAMPLE, QualityLevel.FAIL, "No usable asset trend signals")
        )

    as_of_ts = next((a.as_of for a in assets if a.as_of is not None), None)
    return CrossAssetTrendSnapshot(
        as_of=as_of_ts,
        computed_at=computed,
        assets=assets,
        breadth_long_fraction=breadth_long,
        breadth_short_fraction=breadth_short,
        research_weights=weights,
        weight_method="equal_risk_vol_target_l1_normalized_research_only",
        quality_flags=tuple(flags),
    )


def rolling_ensemble_signs(
    prices: np.ndarray,
    config: EnsembleConfig,
    *,
    start_index: int,
) -> np.ndarray:
    """Ensemble sign at each index i >= start_index using only prices[:i+1]."""

    n = int(prices.size)
    out = np.zeros(n, dtype=int)
    for i in range(max(start_index, 0), n):
        window = prices[: i + 1]
        usable_strengths: list[float] = []
        for spec in config.horizons:
            hs = _horizon_signal(window, spec, config)
            if hs.is_usable and hs.capped_strength is not None:
                usable_strengths.append(hs.capped_strength)
        if usable_strengths:
            out[i] = _sign(float(np.mean(usable_strengths)))
    return out


def horizon_strength_for_lookback(
    prices: np.ndarray,
    lookback_bars: int,
    config: EnsembleConfig,
) -> HorizonSignal:
    spec = HorizonSpec(
        name=f"L{lookback_bars}",
        lookback_bars=lookback_bars,
        intended_holding_bars=lookback_bars,
        annualization_bars=config.annualization_bars,
    )
    return _horizon_signal(prices, spec, config)
