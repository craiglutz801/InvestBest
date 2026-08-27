"""Deterministic synthetic series for Stage 2 eligibility tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np

from northstar_diagnostics.efr import FrictionInputs
from northstar_mean_reversion.liquidity import LiquiditySnapshot
from northstar_mean_reversion.types import MeanReversionEligibilityConfig
from northstar_mean_reversion.universe import EconomicCandidate, RelationshipKind


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


def cointegrated_pair(
    n: int, beta: float = 2.0, phi: float = 0.4, seed: int = 0, residual_scale: float = 0.3
) -> tuple[np.ndarray, np.ndarray]:
    x = random_walk(n, seed=seed)
    resid = ar1(n, phi=phi, seed=seed + 1, scale=residual_scale)
    y = beta * x + resid
    return y, x


def independent_walks(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Two unrelated integrated series (one drifted) — a false pairs candidate."""
    y = random_walk(n, seed=seed)
    x = np.cumsum(white_noise(n, seed=seed + 7, scale=1.0) + 0.2)
    return y, x


def cointegrated_triple(n: int, seed: int = 0) -> np.ndarray:
    x1 = random_walk(n, seed=seed)
    x2 = random_walk(n, seed=seed + 3)
    resid = ar1(n, phi=0.3, seed=seed + 5, scale=0.25)
    x3 = 0.6 * x1 + 0.4 * x2 + resid
    return np.column_stack([x1, x2, x3])


def independent_triple(n: int, seed: int = 0) -> np.ndarray:
    return np.column_stack(
        [
            random_walk(n, seed=seed),
            random_walk(n, seed=seed + 11),
            random_walk(n, seed=seed + 23),
        ]
    )


def broken_cointegrated_pair(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    half = n // 2
    y1, x1 = cointegrated_pair(half, seed=seed)
    y2, x2 = independent_walks(n - half, seed=seed + 17)
    # Continue the second half from the first-half levels so there is no jump
    # that is only a level break; the hedge relationship itself disappears.
    x = np.concatenate([x1, x1[-1] + x2 - x2[0]])
    y = np.concatenate([y1, y1[-1] + y2 - y2[0]])
    return y, x


def unstable_hedge_pair(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    x = random_walk(n, seed=seed)
    resid = ar1(n, phi=0.35, seed=seed + 2, scale=0.25)
    beta = np.ones(n)
    beta[n // 2 :] = 3.0
    y = beta * x + resid
    return y, x


def mean_break_pair(n: int, seed: int = 0, shift: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    y, x = cointegrated_pair(n, seed=seed)
    y = y.copy()
    y[n // 2 :] += shift
    return y, x


def oversold_nonstationary_pair(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    y, x = independent_walks(n, seed=seed)
    y = y.copy()
    y[-1] = y[-1] - 10.0 * float(np.std(y))
    return y, x


def daily_timestamps(n: int, start: datetime | None = None) -> list[datetime]:
    start = start or datetime(2020, 1, 1, tzinfo=timezone.utc)
    return [start + timedelta(days=i) for i in range(n)]


def cheap_friction() -> FrictionInputs:
    return FrictionInputs(
        commission=0.002,
        spread=0.003,
        slippage=0.002,
        market_impact=0.001,
        borrow_fees=0.001,
        other=0.001,
    )


def expensive_friction() -> FrictionInputs:
    return FrictionInputs(
        commission=0.02,
        spread=0.03,
        slippage=0.02,
        market_impact=0.02,
        borrow_fees=0.01,
        other=0.01,
    )


def liquid_snapshots(*symbols: str, as_of: datetime | None = None) -> dict[str, LiquiditySnapshot]:
    return {
        symbol: LiquiditySnapshot(
            symbol=symbol,
            as_of=as_of,
            adv=5_000_000,
            spread_bps=4.0,
            shortable=True,
            locate_available=True,
            borrow_fee_rate=0.01,
        )
        for symbol in symbols
    }


def make_config(**overrides: object) -> MeanReversionEligibilityConfig:
    params = dict(
        min_obs=40,
        rolling_window=40,
        rolling_step=10,
        hedge_beta_relative_std_max=0.75,
        spread_vol_cv_max=1.25,
        half_life_max_multiple_of_horizon=8.0,
        half_life_min_fraction_of_horizon=0.01,
        efr_min=2.5,
        structural_break_method="cusum_ols_resid",
    )
    params.update(overrides)
    return MeanReversionEligibilityConfig(**params)  # type: ignore[arg-type]


def pair_candidate(
    y: np.ndarray,
    x: np.ndarray,
    *,
    candidate_id: str = "KO-PEP",
    holding_horizon: float = 10.0,
    expected_gross_edge: float = 0.05,
    friction: FrictionInputs | None = None,
    **kwargs: object,
) -> EconomicCandidate:
    timestamps = kwargs.pop("timestamps", None)
    as_of = kwargs.pop("as_of", None)
    return EconomicCandidate(
        candidate_id=candidate_id,
        symbols=("KO", "PEP"),
        relationship_kind=RelationshipKind.SECTOR_PEERS,
        relationship_rationale="Large-cap beverage peers with overlapping demand and input costs",
        legs={"KO": y, "PEP": x},
        holding_horizon=holding_horizon,
        timestamps=timestamps,  # type: ignore[arg-type]
        as_of=as_of,  # type: ignore[arg-type]
        expected_gross_edge=expected_gross_edge,
        friction=friction if friction is not None else cheap_friction(),
        liquidity=liquid_snapshots("KO", "PEP"),
        **kwargs,  # type: ignore[arg-type]
    )


def basket_candidate(panel: np.ndarray, **kwargs: object) -> EconomicCandidate:
    return EconomicCandidate(
        candidate_id="BASKET-XLY",
        symbols=("XLY", "AMZN", "HD"),
        relationship_kind=RelationshipKind.INDEX_CONSTITUENT,
        relationship_rationale="Consumer-discretionary ETF vs two large declared constituents",
        legs={"XLY": panel[:, 0], "AMZN": panel[:, 1], "HD": panel[:, 2]},
        holding_horizon=12.0,
        expected_gross_edge=0.06,
        friction=cheap_friction(),
        liquidity=liquid_snapshots("XLY", "AMZN", "HD"),
        **kwargs,  # type: ignore[arg-type]
    )
