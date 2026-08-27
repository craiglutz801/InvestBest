"""Point-in-time price series validation and slicing.

Historical calls take ``as_of`` (inclusive index or timestamp). Observations
after that cutoff are never used.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import numpy as np

from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import QualityFlag, SampleWindow, empty_sample


@dataclass(frozen=True)
class PriceSeries:
    """Caller-supplied, provider-neutral close/settle series."""

    symbol: str
    timestamps: tuple[datetime, ...]
    prices: tuple[float, ...]
    asset_class: str | None = None

    def __post_init__(self) -> None:
        if len(self.timestamps) != len(self.prices):
            raise ValueError("timestamps and prices must have equal length")


@dataclass(frozen=True)
class SlicedSeries:
    series: PriceSeries
    values: np.ndarray
    timestamps: tuple[datetime, ...]
    sample: SampleWindow
    quality_flags: tuple[QualityFlag, ...]
    as_of: datetime | None
    as_of_index: int | None

    @property
    def is_usable(self) -> bool:
        return not any(f.level is QualityLevel.FAIL for f in self.quality_flags)


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def validate_and_slice(
    series: PriceSeries,
    *,
    as_of: datetime | int | None = None,
) -> SlicedSeries:
    n_in = len(series.prices)
    flags: list[QualityFlag] = []

    if n_in == 0:
        flags.append(flag(QualityCode.INVALID_INPUT, QualityLevel.FAIL, "Price series is empty"))
        return SlicedSeries(
            series=series,
            values=np.asarray([], dtype=float),
            timestamps=(),
            sample=empty_sample(0),
            quality_flags=tuple(flags),
            as_of=as_of if isinstance(as_of, datetime) else None,
            as_of_index=None,
        )

    stamps = tuple(_as_utc(t) for t in series.timestamps)
    if any(later <= earlier for earlier, later in zip(stamps, stamps[1:])):
        flags.append(
            flag(
                QualityCode.UNSORTED_TIMESTAMPS,
                QualityLevel.FAIL,
                "Timestamps must be strictly increasing",
            )
        )

    values = np.asarray(series.prices, dtype=float)
    end_index = n_in - 1
    as_of_ts: datetime | None = None

    if isinstance(as_of, int):
        if as_of < 0 or as_of >= n_in:
            flags.append(
                flag(
                    QualityCode.INVALID_INPUT,
                    QualityLevel.FAIL,
                    f"as_of index {as_of} is outside [0, {n_in - 1}]",
                )
            )
            end_index = -1
        else:
            end_index = as_of
            as_of_ts = stamps[end_index]
            if as_of < n_in - 1:
                flags.append(
                    flag(
                        QualityCode.POINT_IN_TIME_SLICE,
                        QualityLevel.OK,
                        "Evaluation used only observations at or before as_of",
                    )
                )
    elif isinstance(as_of, datetime):
        as_of_ts = _as_utc(as_of)
        eligible = [i for i, t in enumerate(stamps) if t <= as_of_ts]
        if not eligible:
            flags.append(
                flag(
                    QualityCode.INVALID_INPUT,
                    QualityLevel.FAIL,
                    "as_of is before the first observation",
                )
            )
            end_index = -1
        else:
            end_index = eligible[-1]
            if end_index < n_in - 1:
                flags.append(
                    flag(
                        QualityCode.POINT_IN_TIME_SLICE,
                        QualityLevel.OK,
                        "Evaluation used only observations at or before as_of",
                    )
                )
    else:
        as_of_ts = stamps[-1]

    if end_index < 0:
        return SlicedSeries(
            series=series,
            values=np.asarray([], dtype=float),
            timestamps=(),
            sample=empty_sample(n_in),
            quality_flags=tuple(flags),
            as_of=as_of_ts,
            as_of_index=None,
        )

    used = values[: end_index + 1]
    used_stamps = stamps[: end_index + 1]
    dropped = 0
    if not np.all(np.isfinite(used)):
        dropped = int(np.size(used) - np.sum(np.isfinite(used)))
        flags.append(
            flag(
                QualityCode.NON_FINITE,
                QualityLevel.FAIL,
                "Non-finite prices in the point-in-time window",
            )
        )
    if np.any(used[np.isfinite(used)] <= 0):
        flags.append(
            flag(
                QualityCode.NON_POSITIVE_PRICE,
                QualityLevel.FAIL,
                "Prices must be strictly positive for return calculations",
            )
        )

    sample = SampleWindow(
        n_obs_input=n_in,
        n_obs_used=int(end_index + 1),
        start_index=0,
        end_index=end_index,
        start_timestamp=used_stamps[0],
        end_timestamp=used_stamps[-1],
        dropped_missing=dropped,
        as_of_index=end_index,
    )
    return SlicedSeries(
        series=series,
        values=used.astype(float, copy=False),
        timestamps=used_stamps,
        sample=sample,
        quality_flags=tuple(flags),
        as_of=as_of_ts,
        as_of_index=end_index,
    )


def log_returns(prices: np.ndarray) -> np.ndarray:
    prices = np.asarray(prices, dtype=float)
    if prices.size < 2:
        return np.asarray([], dtype=float)
    return np.diff(np.log(prices))


def realized_vol(
    returns: np.ndarray,
    *,
    annualization_bars: int = 252,
    ddof: int = 1,
) -> float | None:
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if r.size < max(2, ddof + 1):
        return None
    std = float(np.std(r, ddof=ddof))
    if std == 0.0 or not np.isfinite(std):
        return None
    return std * float(np.sqrt(annualization_bars))


def daily_vol(
    prices: np.ndarray,
    *,
    vol_lookback_bars: int,
) -> float | None:
    rets = log_returns(prices)
    if rets.size == 0:
        return None
    window = rets[-vol_lookback_bars:] if rets.size >= vol_lookback_bars else rets
    window = window[np.isfinite(window)]
    if window.size < 2:
        return None
    std = float(np.std(window, ddof=1))
    if std == 0.0 or not np.isfinite(std):
        return None
    return std


def make_daily_series(
    symbol: str,
    prices: Sequence[float],
    *,
    start: datetime | None = None,
    asset_class: str | None = None,
) -> PriceSeries:
    """Build a strictly daily timestamped series from prices (tests / fixtures)."""

    start_ts = start or datetime(2018, 1, 2, tzinfo=timezone.utc)
    stamps = []
    current = start_ts
    for _ in prices:
        stamps.append(current)
        current = current.fromtimestamp(current.timestamp() + 86400, tz=timezone.utc)
    return PriceSeries(
        symbol=symbol,
        timestamps=tuple(stamps),
        prices=tuple(float(p) for p in prices),
        asset_class=asset_class,
    )
