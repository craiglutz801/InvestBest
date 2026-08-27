"""Deterministic synthetic series with known statistical behavior."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np


def rng(seed: int = 0) -> np.random.Generator:
    return np.random.default_rng(seed)


def white_noise(n: int, seed: int = 0, scale: float = 1.0) -> np.ndarray:
    return rng(seed).normal(0.0, scale, size=n)


def ar1(n: int, phi: float, seed: int = 0, scale: float = 1.0) -> np.ndarray:
    e = white_noise(n, seed=seed, scale=scale)
    y = np.zeros(n, dtype=float)
    for t in range(1, n):
        y[t] = phi * y[t - 1] + e[t]
    return y


def random_walk(n: int, seed: int = 0, scale: float = 1.0) -> np.ndarray:
    return np.cumsum(white_noise(n, seed=seed, scale=scale))


def trending_rw(n: int, drift: float = 0.05, seed: int = 0, scale: float = 1.0) -> np.ndarray:
    return np.cumsum(white_noise(n, seed=seed, scale=scale) + drift)


def persistent_levels(n: int, phi: float = 0.4, seed: int = 0) -> np.ndarray:
    """Levels whose increments are positively autocorrelated (trend-like)."""
    return np.cumsum(ar1(n, phi=phi, seed=seed))


def cointegrated_pair(
    n: int, beta: float = 2.0, phi: float = 0.4, seed: int = 0, residual_scale: float = 0.3
) -> tuple[np.ndarray, np.ndarray]:
    x = random_walk(n, seed=seed)
    resid = ar1(n, phi=phi, seed=seed + 1, scale=residual_scale)
    y = beta * x + resid
    return y, x


def independent_walks(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    return random_walk(n, seed=seed), random_walk(n, seed=seed + 7)


def cointegrated_triple(n: int, seed: int = 0) -> np.ndarray:
    x1 = random_walk(n, seed=seed)
    x2 = random_walk(n, seed=seed + 3)
    resid = ar1(n, phi=0.3, seed=seed + 5, scale=0.25)
    x3 = 0.6 * x1 + 0.4 * x2 + resid
    return np.column_stack([x1, x2, x3])


def mean_break(n: int, break_at: int, shift: float = 4.0, seed: int = 0) -> np.ndarray:
    y = white_noise(n, seed=seed, scale=0.4)
    y[break_at:] += shift
    return y


def daily_timestamps(n: int, start: datetime | None = None) -> list[datetime]:
    start = start or datetime(2020, 1, 1, tzinfo=timezone.utc)
    return [start + timedelta(days=i) for i in range(n)]
