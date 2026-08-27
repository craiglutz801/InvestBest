"""Deterministic synthetic series for Stage 5 tests."""

from __future__ import annotations

import numpy as np


def rng(seed: int = 7) -> np.random.Generator:
    return np.random.default_rng(seed)


def iid_normal(n: int, mu: float, sigma: float, seed: int = 7) -> np.ndarray:
    return rng(seed).normal(mu, sigma, size=n)


def noisy_edge_matrix(
    n_obs: int,
    n_noise: int,
    *,
    edge_mu: float = 0.02,
    edge_sigma: float = 0.02,
    noise_sigma: float = 0.02,
    seed: int = 7,
) -> np.ndarray:
    """Column 0 has a persistent edge; remaining columns are mean-zero noise."""
    g = rng(seed)
    edge = g.normal(edge_mu, edge_sigma, size=n_obs)
    noise = g.normal(0.0, noise_sigma, size=(n_obs, n_noise))
    return np.column_stack([edge, noise])


def overfit_spike_matrix(n_slices: int, slice_len: int, seed: int = 11) -> np.ndarray:
    """Each strategy i is profitable only inside slice i and noise elsewhere.

    IS selection then tends to pick a slice-specific spike that fails OOS,
    so CSCV PBO should be high.
    """
    g = rng(seed)
    t = n_slices * slice_len
    n = n_slices
    mat = g.normal(0.0, 0.02, size=(t, n))
    for i in range(n):
        start = i * slice_len
        mat[start : start + slice_len, i] = g.normal(0.08, 0.01, size=slice_len)
    return mat
