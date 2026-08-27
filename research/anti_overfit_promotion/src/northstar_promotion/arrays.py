"""Finite-array helpers shared by Stage 5 evaluators."""

from __future__ import annotations

from typing import Any

import numpy as np

from northstar_promotion.quality import QualityCode, QualityFlag, QualityLevel, fail_flag


def as_float_array(values: Any, *, name: str = "values") -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.ndim == 0:
        arr = arr.reshape(1)
    return arr


def finite_mask(values: np.ndarray) -> np.ndarray:
    return np.isfinite(values)


def validate_1d(values: Any, *, name: str = "returns") -> tuple[np.ndarray, tuple[QualityFlag, ...]]:
    flags: list[QualityFlag] = []
    try:
        arr = as_float_array(values, name=name)
    except (TypeError, ValueError) as exc:
        empty = np.asarray([], dtype=float)
        return empty, (fail_flag(QualityCode.INVALID_INPUT, f"{name} could not be parsed: {exc}"),)
    if arr.ndim != 1:
        return np.asarray([], dtype=float), (
            fail_flag(QualityCode.INVALID_INPUT, f"{name} must be 1-D, got shape {arr.shape}."),
        )
    n_input = int(arr.size)
    if n_input == 0:
        flags.append(fail_flag(QualityCode.MISSING_DATA, f"{name} is empty."))
        return arr, tuple(flags)
    mask = finite_mask(arr)
    n_bad = int((~mask).sum())
    if n_bad:
        flags.append(
            fail_flag(
                QualityCode.NON_FINITE,
                f"{name} contains {n_bad} NaN/Inf observations; fail-closed.",
            )
        )
        return arr[mask], tuple(flags)
    return arr, tuple(flags)


def validate_2d(values: Any, *, name: str = "returns") -> tuple[np.ndarray, tuple[QualityFlag, ...]]:
    try:
        arr = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        return np.zeros((0, 0), dtype=float), (
            fail_flag(QualityCode.INVALID_INPUT, f"{name} could not be parsed: {exc}"),
        )
    if arr.ndim != 2:
        return np.zeros((0, 0), dtype=float), (
            fail_flag(QualityCode.INVALID_INPUT, f"{name} must be 2-D (T x N), got shape {arr.shape}."),
        )
    if arr.size == 0:
        return arr, (fail_flag(QualityCode.MISSING_DATA, f"{name} is empty."),)
    if not np.all(np.isfinite(arr)):
        return arr, (
            fail_flag(QualityCode.NON_FINITE, f"{name} contains NaN/Inf observations; fail-closed."),
        )
    return arr, ()


def has_fail(flags: tuple[QualityFlag, ...] | list[QualityFlag]) -> bool:
    return any(flag.level is QualityLevel.FAIL for flag in flags)
