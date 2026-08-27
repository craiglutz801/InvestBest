"""Point-in-time series preparation and numeric guards.

Historical calculations use only observations at or before ``as_of``.
Future values are never consumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import numpy as np

from northstar_diagnostics.quality import QualityCode, QualityLevel
from northstar_diagnostics.schema import QualityFlag, SampleWindow

ArrayLike = Sequence[float] | np.ndarray


@dataclass(frozen=True)
class PreparedSeries:
    values: np.ndarray
    timestamps: np.ndarray | None
    sample: SampleWindow
    flags: tuple[QualityFlag, ...]
    as_of: datetime | None
    usable: bool


def empty_sample(n_obs_input: int = 0) -> SampleWindow:
    return SampleWindow(
        n_obs_input=n_obs_input,
        n_obs_used=0,
        start_index=None,
        end_index=None,
        start_timestamp=None,
        end_timestamp=None,
        as_of_index=None,
    )


def to_float_array(values: ArrayLike) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64).reshape(-1)
    return arr


def to_float_matrix(values: ArrayLike) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim == 1:
        arr = arr.reshape(-1, 1)
    if arr.ndim != 2:
        raise ValueError("expected a 1d or 2d numeric array")
    return arr


def variance_is_degenerate(values: np.ndarray, *, atol: float = 1e-18) -> bool:
    if values.size < 2:
        return True
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return True
    return float(np.nanvar(finite)) <= atol


def flag(code: str, level: QualityLevel, message: str) -> QualityFlag:
    return QualityFlag(code=code, level=level, message=message)


def _as_utc_datetime(value: datetime | np.datetime64) -> datetime:
    if isinstance(value, np.datetime64):
        # datetime64[ns] -> naive UTC datetime
        ts = value.astype("datetime64[ns]")
        epoch_ns = int(ts.astype("int64"))
        return datetime.fromtimestamp(epoch_ns / 1e9, tz=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamps_to_datetime64(timestamps: Sequence[datetime] | np.ndarray) -> np.ndarray:
    arr = np.asarray(timestamps)
    if arr.dtype == object or np.issubdtype(arr.dtype, np.datetime64):
        converted = np.array(
            [
                np.datetime64(_as_utc_datetime(item).replace(tzinfo=None))
                if not isinstance(item, np.datetime64)
                else np.datetime64(item)
                for item in arr.reshape(-1)
            ],
            dtype="datetime64[ns]",
        )
        return converted
    raise TypeError("timestamps must be datetime or numpy.datetime64 values")


def _datetime_from_ns(ts: np.datetime64) -> datetime:
    epoch_ns = int(ts.astype("datetime64[ns]").astype("int64"))
    return datetime.fromtimestamp(epoch_ns / 1e9, tz=timezone.utc)


def prepare_series(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | np.ndarray | None = None,
    as_of: datetime | int | None = None,
    min_obs: int,
    frequency: str | None = None,
    allow_dropna: bool = False,
) -> PreparedSeries:
    """Slice ``values`` to a point-in-time window and apply quality checks.

    ``as_of``:
      - ``None``: use the full provided series (caller must already be PIT-safe)
      - ``int``: inclusive observation index cutoff
      - ``datetime``: include observations with timestamp <= as_of
    """

    flags: list[QualityFlag] = []
    raw = np.asarray(values, dtype=np.float64).reshape(-1)
    n_input = int(raw.size)
    ts_arr: np.ndarray | None = None
    as_of_dt: datetime | None = None

    if timestamps is not None:
        try:
            ts_arr = _timestamps_to_datetime64(timestamps)
        except (TypeError, ValueError) as exc:
            flags.append(
                flag(
                    QualityCode.INVALID_INPUT,
                    QualityLevel.FAIL,
                    f"Could not parse timestamps: {exc}",
                )
            )
            return PreparedSeries(
                values=np.asarray([], dtype=np.float64),
                timestamps=None,
                sample=empty_sample(n_input),
                flags=tuple(flags),
                as_of=as_of if isinstance(as_of, datetime) else None,
                usable=False,
            )
        if ts_arr.size != n_input:
            flags.append(
                flag(
                    QualityCode.INVALID_INPUT,
                    QualityLevel.FAIL,
                    "timestamps length does not match values length",
                )
            )
            return PreparedSeries(
                values=np.asarray([], dtype=np.float64),
                timestamps=None,
                sample=empty_sample(n_input),
                flags=tuple(flags),
                as_of=as_of if isinstance(as_of, datetime) else None,
                usable=False,
            )
        if ts_arr.size > 1 and np.any(ts_arr[1:] < ts_arr[:-1]):
            flags.append(
                flag(
                    QualityCode.UNSORTED_TIMESTAMPS,
                    QualityLevel.FAIL,
                    "timestamps must be non-decreasing for point-in-time slicing",
                )
            )
            return PreparedSeries(
                values=np.asarray([], dtype=np.float64),
                timestamps=None,
                sample=empty_sample(n_input),
                flags=tuple(flags),
                as_of=as_of if isinstance(as_of, datetime) else None,
                usable=False,
            )

    exclusive_end = n_input
    if as_of is None:
        exclusive_end = n_input
    elif isinstance(as_of, (int, np.integer)):
        if int(as_of) < 0:
            flags.append(
                flag(
                    QualityCode.INVALID_INPUT,
                    QualityLevel.FAIL,
                    "as_of index must be >= 0",
                )
            )
            return PreparedSeries(
                values=np.asarray([], dtype=np.float64),
                timestamps=None,
                sample=empty_sample(n_input),
                flags=tuple(flags),
                as_of=None,
                usable=False,
            )
        exclusive_end = min(int(as_of) + 1, n_input)
    else:
        as_of_dt = _as_utc_datetime(as_of)
        if ts_arr is None:
            flags.append(
                flag(
                    QualityCode.MISSING_TIMESTAMPS,
                    QualityLevel.FAIL,
                    "datetime as_of requires timestamps so future observations can be excluded",
                )
            )
            return PreparedSeries(
                values=np.asarray([], dtype=np.float64),
                timestamps=None,
                sample=empty_sample(n_input),
                flags=tuple(flags),
                as_of=as_of_dt,
                usable=False,
            )
        cutoff = np.datetime64(as_of_dt.replace(tzinfo=None))
        exclusive_end = int(np.searchsorted(ts_arr, cutoff, side="right"))

    sliced = raw[:exclusive_end]
    sliced_ts = ts_arr[:exclusive_end] if ts_arr is not None else None
    dropped = 0

    if sliced.size and not np.all(np.isfinite(sliced)):
        inf_mask = np.isinf(sliced)
        nan_mask = np.isnan(sliced)
        if np.any(inf_mask):
            flags.append(
                flag(
                    QualityCode.NON_FINITE,
                    QualityLevel.FAIL,
                    "Series contains Inf values in the point-in-time window",
                )
            )
        if np.any(nan_mask):
            flags.append(
                flag(
                    QualityCode.MISSING_DATA,
                    QualityLevel.FAIL if not allow_dropna else QualityLevel.WARN,
                    "Series contains NaN values in the point-in-time window",
                )
            )
            if allow_dropna:
                interior = nan_mask.copy()
                # leading/trailing NaNs are less harmful than holes
                finite_idx = np.where(~nan_mask)[0]
                if finite_idx.size:
                    lo, hi = int(finite_idx[0]), int(finite_idx[-1])
                    if np.any(nan_mask[lo : hi + 1]):
                        flags.append(
                            flag(
                                QualityCode.INTERIOR_MISSING,
                                QualityLevel.WARN,
                                "Dropped interior NaNs; sampling frequency may be irregular",
                            )
                        )
                keep = np.isfinite(sliced)
                dropped = int((~keep).sum())
                sliced = sliced[keep]
                if sliced_ts is not None:
                    sliced_ts = sliced_ts[keep]
            else:
                return PreparedSeries(
                    values=np.asarray([], dtype=np.float64),
                    timestamps=None,
                    sample=SampleWindow(
                        n_obs_input=n_input,
                        n_obs_used=0,
                        start_index=0 if exclusive_end else None,
                        end_index=exclusive_end - 1 if exclusive_end else None,
                        start_timestamp=_datetime_from_ns(sliced_ts[0]) if sliced_ts is not None and sliced_ts.size else None,
                        end_timestamp=_datetime_from_ns(sliced_ts[-1]) if sliced_ts is not None and sliced_ts.size else None,
                        frequency=frequency,
                        dropped_missing=int(nan_mask.sum()),
                        as_of_index=exclusive_end - 1 if exclusive_end else None,
                    ),
                    flags=tuple(flags),
                    as_of=as_of_dt,
                    usable=False,
                )
        if np.any(inf_mask) and not allow_dropna:
            return PreparedSeries(
                values=np.asarray([], dtype=np.float64),
                timestamps=None,
                sample=empty_sample(n_input),
                flags=tuple(flags),
                as_of=as_of_dt,
                usable=False,
            )

    if sliced.size < min_obs:
        flags.append(
            flag(
                QualityCode.SHORT_SAMPLE,
                QualityLevel.FAIL,
                f"Need at least {min_obs} observations after point-in-time slicing; got {sliced.size}",
            )
        )

    if sliced.size >= 2 and variance_is_degenerate(sliced):
        flags.append(
            flag(
                QualityCode.DEGENERATE_VARIANCE,
                QualityLevel.FAIL,
                "Variance is degenerate (constant or near-constant series)",
            )
        )
        if sliced.size and np.nanmax(sliced) - np.nanmin(sliced) <= 1e-18:
            flags.append(
                flag(
                    QualityCode.CONSTANT_SERIES,
                    QualityLevel.FAIL,
                    "Series is constant in the formation window",
                )
            )

    usable = not any(f.level is QualityLevel.FAIL for f in flags)
    start_index = 0 if sliced.size else None
    end_index = exclusive_end - 1 if exclusive_end else None
    if allow_dropna and sliced.size and timestamps is not None:
        # indices refer to original PIT-sliced positions of kept rows
        pass

    sample = SampleWindow(
        n_obs_input=n_input,
        n_obs_used=int(sliced.size),
        start_index=start_index,
        end_index=end_index,
        start_timestamp=_datetime_from_ns(sliced_ts[0]) if sliced_ts is not None and sliced_ts.size else None,
        end_timestamp=_datetime_from_ns(sliced_ts[-1]) if sliced_ts is not None and sliced_ts.size else None,
        frequency=frequency,
        dropped_missing=dropped,
        as_of_index=end_index,
    )
    return PreparedSeries(
        values=sliced if usable else sliced,
        timestamps=sliced_ts,
        sample=sample,
        flags=tuple(flags),
        as_of=as_of_dt,
        usable=usable,
    )


def prepare_panel(
    values: ArrayLike,
    *,
    timestamps: Sequence[datetime] | np.ndarray | None = None,
    as_of: datetime | int | None = None,
    min_obs: int,
    frequency: str | None = None,
) -> tuple[np.ndarray | None, PreparedSeries]:
    """Prepare a 2d panel using the first column's PIT rules applied row-wise."""

    matrix = to_float_matrix(values)
    n_obs, n_series = matrix.shape
    if n_series < 1:
        dummy = prepare_series([], as_of=as_of, timestamps=timestamps, min_obs=min_obs, frequency=frequency)
        return None, dummy

    first = prepare_series(
        matrix[:, 0],
        timestamps=timestamps,
        as_of=as_of,
        min_obs=min_obs,
        frequency=frequency,
    )
    exclusive_end = 0 if first.sample.end_index is None else first.sample.end_index + 1
    panel = matrix[:exclusive_end]
    flags = list(first.flags)

    if not np.all(np.isfinite(panel)):
        flags.append(
            flag(
                QualityCode.NON_FINITE if np.any(np.isinf(panel)) else QualityCode.MISSING_DATA,
                QualityLevel.FAIL,
                "Panel contains NaN/Inf values in the point-in-time window",
            )
        )

    if panel.shape[0] < min_obs:
        if not any(f.code == QualityCode.SHORT_SAMPLE for f in flags):
            flags.append(
                flag(
                    QualityCode.SHORT_SAMPLE,
                    QualityLevel.FAIL,
                    f"Need at least {min_obs} rows; got {panel.shape[0]}",
                )
            )

    if np.all(np.isfinite(panel)):
        flags.extend(panel_rank_flags(panel))

    usable = not any(f.level is QualityLevel.FAIL for f in flags)
    sample = SampleWindow(
        n_obs_input=n_obs,
        n_obs_used=int(panel.shape[0]) if usable or panel.size else int(panel.shape[0]),
        start_index=0 if panel.shape[0] else None,
        end_index=exclusive_end - 1 if exclusive_end else None,
        start_timestamp=first.sample.start_timestamp,
        end_timestamp=first.sample.end_timestamp,
        frequency=frequency,
        dropped_missing=0,
        as_of_index=exclusive_end - 1 if exclusive_end else None,
    )
    prepared = PreparedSeries(
        values=panel.reshape(-1) if panel.size else np.asarray([], dtype=np.float64),
        timestamps=first.timestamps,
        sample=sample,
        flags=tuple(flags),
        as_of=first.as_of,
        usable=usable,
    )
    return (panel if panel.size else None), prepared


_RANK_REL_TOL = 1e-8
_DUPLICATE_ATOL = 1e-12


def panel_rank_flags(panel: np.ndarray) -> tuple[QualityFlag, ...]:
    """Fail closed on constant, duplicate, rank-deficient, or near-collinear columns.

    Johansen / basket diagnostics cannot use an invalid covariance system.
    High economic correlation (e.g. cointegrated series with a non-degenerate
    residual) is allowed; numerical rank deficiency is not.
    """

    if panel.ndim != 2 or panel.size == 0:
        return ()
    n_obs, n_series = panel.shape
    if n_series < 2:
        return ()

    flags: list[QualityFlag] = []
    for j in range(n_series):
        col = panel[:, j]
        if variance_is_degenerate(col):
            flags.append(
                flag(
                    QualityCode.CONSTANT_SERIES,
                    QualityLevel.FAIL,
                    f"Panel column {j} is constant or near-constant",
                )
            )
            flags.append(
                flag(
                    QualityCode.NEAR_SINGULAR,
                    QualityLevel.FAIL,
                    "A constant column makes the panel covariance system unusable",
                )
            )
            flags.append(
                flag(
                    QualityCode.INSUFFICIENT_RANK,
                    QualityLevel.FAIL,
                    f"Panel rank is deficient because column {j} has degenerate variance",
                )
            )
            return tuple(flags)

    for i in range(n_series):
        for j in range(i + 1, n_series):
            if np.allclose(panel[:, i], panel[:, j], rtol=0.0, atol=_DUPLICATE_ATOL):
                flags.append(
                    flag(
                        QualityCode.COLLINEAR_SERIES,
                        QualityLevel.FAIL,
                        f"Panel columns {i} and {j} are duplicates",
                    )
                )
                flags.append(
                    flag(
                        QualityCode.NEAR_SINGULAR,
                        QualityLevel.FAIL,
                        "Duplicate columns make the panel covariance system unusable",
                    )
                )
                flags.append(
                    flag(
                        QualityCode.INSUFFICIENT_RANK,
                        QualityLevel.FAIL,
                        "Duplicate columns reduce panel rank below the number of series",
                    )
                )
                return tuple(flags)

    if n_obs < n_series:
        flags.append(
            flag(
                QualityCode.INSUFFICIENT_RANK,
                QualityLevel.FAIL,
                f"Need at least as many rows as series for a full-rank panel; got rows={n_obs}, series={n_series}",
            )
        )
        flags.append(
            flag(
                QualityCode.NEAR_SINGULAR,
                QualityLevel.FAIL,
                "Panel is rank-deficient because n_obs < n_series",
            )
        )
        return tuple(flags)

    centered = panel - np.mean(panel, axis=0, keepdims=True)
    try:
        singular_values = np.linalg.svd(centered, compute_uv=False)
    except np.linalg.LinAlgError:
        return (
            flag(
                QualityCode.NEAR_SINGULAR,
                QualityLevel.FAIL,
                "Panel SVD failed; treating the covariance system as unusable",
            ),
            flag(
                QualityCode.INSUFFICIENT_RANK,
                QualityLevel.FAIL,
                "Could not establish full column rank",
            ),
        )

    smax = float(singular_values[0]) if singular_values.size else 0.0
    if not np.isfinite(smax) or smax <= 0:
        return (
            flag(
                QualityCode.NEAR_SINGULAR,
                QualityLevel.FAIL,
                "Panel has a degenerate singular-value spectrum",
            ),
            flag(
                QualityCode.INSUFFICIENT_RANK,
                QualityLevel.FAIL,
                "Centered panel rank is zero",
            ),
        )

    rel = singular_values / smax
    rank = int(np.sum(rel > _RANK_REL_TOL))
    if rank < n_series:
        flags.append(
            flag(
                QualityCode.NEAR_SINGULAR,
                QualityLevel.FAIL,
                f"Panel is rank-deficient or near-collinear (rank={rank}, series={n_series}, "
                f"smallest_relative_sv={float(rel[-1]):.3e})",
            )
        )
        flags.append(
            flag(
                QualityCode.INSUFFICIENT_RANK,
                QualityLevel.FAIL,
                f"Centered panel rank {rank} is below n_series={n_series}",
            )
        )
        flags.append(
            flag(
                QualityCode.COLLINEAR_SERIES,
                QualityLevel.FAIL,
                "Columns are linearly dependent or near-collinear in the formation window",
            )
        )
    return tuple(flags)


def length_mismatch_flag(y_len: int, x_len: int, *, what: str = "y and x") -> QualityFlag | None:
    if y_len == x_len:
        return None
    return flag(
        QualityCode.LENGTH_MISMATCH,
        QualityLevel.FAIL,
        f"{what} have unequal lengths ({y_len} vs {x_len}); refusing to truncate or pair misaligned rows",
    )


def timestamp_mismatch_flag(
    timestamps: Sequence[datetime] | np.ndarray | None,
    other_timestamps: Sequence[datetime] | np.ndarray | None,
) -> QualityFlag | None:
    """Require timestamps to match when either side supplies them."""

    if timestamps is None and other_timestamps is None:
        return None
    if timestamps is None or other_timestamps is None:
        return flag(
            QualityCode.TIMESTAMP_MISMATCH,
            QualityLevel.FAIL,
            "Timestamps were supplied for only one series; both legs must share aligned timestamps",
        )
    try:
        left = _timestamps_to_datetime64(timestamps)
        right = _timestamps_to_datetime64(other_timestamps)
    except (TypeError, ValueError) as exc:
        return flag(
            QualityCode.INVALID_INPUT,
            QualityLevel.FAIL,
            f"Could not parse timestamps for alignment: {exc}",
        )
    if left.size != right.size or not np.array_equal(left, right):
        return flag(
            QualityCode.TIMESTAMP_MISMATCH,
            QualityLevel.FAIL,
            "y and x timestamps are not identical; refusing to pair misaligned dates",
        )
    return None


def ols_with_intercept(y: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    """Return (coef, resid, rank) for y = a + B x + e. ``x`` may be 1d or 2d."""

    y = np.asarray(y, dtype=np.float64).reshape(-1)
    x_arr = np.asarray(x, dtype=np.float64)
    if x_arr.ndim == 1:
        x_arr = x_arr.reshape(-1, 1)
    if x_arr.shape[0] != y.shape[0]:
        raise ValueError("y and x must have the same number of rows")
    design = np.column_stack([np.ones(y.shape[0]), x_arr])
    coef, _, rank, _ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ coef
    return coef, resid, int(rank)
