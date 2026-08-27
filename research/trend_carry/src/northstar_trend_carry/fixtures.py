"""Deterministic synthetic fixtures. No market-data vendor is required."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import numpy as np

from northstar_trend_carry.futures import ContractChain, FuturesContractObservation
from northstar_trend_carry.series import PriceSeries, make_daily_series


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def geometric_price_path(
    n: int,
    *,
    start_price: float = 100.0,
    daily_drift: float = 0.0,
    daily_vol: float = 0.01,
    seed: int = 1,
) -> np.ndarray:
    rng = _rng(seed)
    shocks = rng.normal(loc=daily_drift, scale=daily_vol, size=n - 1)
    log_p = np.empty(n, dtype=float)
    log_p[0] = np.log(start_price)
    log_p[1:] = log_p[0] + np.cumsum(shocks)
    return np.exp(log_p)


def uptrend_series(n: int = 400, *, seed: int = 11, symbol: str = "UP") -> PriceSeries:
    prices = geometric_price_path(n, daily_drift=0.0012, daily_vol=0.006, seed=seed)
    return make_daily_series(symbol, prices, asset_class="synthetic_equity")


def downtrend_series(n: int = 400, *, seed: int = 12, symbol: str = "DN") -> PriceSeries:
    prices = geometric_price_path(n, daily_drift=-0.0012, daily_vol=0.006, seed=seed)
    return make_daily_series(symbol, prices, asset_class="synthetic_equity")


def choppy_series(n: int = 400, *, seed: int = 13, period: int = 8, symbol: str = "CHOP") -> PriceSeries:
    rng = _rng(seed)
    t = np.arange(n)
    osc = 0.03 * np.sin(2 * np.pi * t / period)
    noise = rng.normal(0.0, 0.004, size=n)
    prices = 100.0 * np.exp(osc + np.cumsum(noise) * 0.0 + noise)
    return make_daily_series(symbol, prices, asset_class="synthetic_equity")


def mixed_horizon_series(n: int = 400, symbol: str = "MIX") -> PriceSeries:
    """Long uptrend followed by a short, sharp decline (short vs long disagreement)."""

    up = geometric_price_path(n - 30, daily_drift=0.0015, daily_vol=0.004, seed=21)
    down = geometric_price_path(31, start_price=float(up[-1]), daily_drift=-0.004, daily_vol=0.004, seed=22)
    prices = np.concatenate([up, down[1:]])
    return make_daily_series(symbol, prices, asset_class="synthetic_equity")


def vol_pair_same_drift(n: int = 400) -> tuple[PriceSeries, PriceSeries]:
    """Identical shock path; only the volatility scale differs."""

    rng = _rng(31)
    z = rng.normal(size=n - 1)
    drift = 0.001

    def _path(vol: float) -> np.ndarray:
        log_p = np.empty(n, dtype=float)
        log_p[0] = np.log(100.0)
        log_p[1:] = log_p[0] + np.cumsum(drift + vol * z)
        return np.exp(log_p)

    return (
        make_daily_series("LOWVOL", _path(0.004), asset_class="synthetic_equity"),
        make_daily_series("HIVOL", _path(0.02), asset_class="synthetic_equity"),
    )


def vol_shock_series(n: int = 400, symbol: str = "SHOCK") -> PriceSeries:
    calm = geometric_price_path(n - 20, daily_drift=0.0004, daily_vol=0.003, seed=41)
    shock = geometric_price_path(21, start_price=float(calm[-1]), daily_drift=0.0, daily_vol=0.04, seed=42)
    prices = np.concatenate([calm, shock[1:]])
    return make_daily_series(symbol, prices, asset_class="synthetic_equity")


def _session_days(n: int, start: datetime) -> list[datetime]:
    out = []
    current = start
    for _ in range(n):
        out.append(current)
        current = current + timedelta(days=1)
    return out


def synthetic_futures_chain(
    *,
    root: str,
    curve: str,
    n_sessions: int = 80,
    start: datetime | None = None,
    front_start: date | None = None,
    contract_months: int = 4,
    month_step: int = 1,
    include_future_quotes: bool = False,
) -> ContractChain:
    """Build a listed-contract chain in contango or backwardation.

    ``curve='contango'``: deferred contracts richer than the front.
    ``curve='backwardation'``: deferred cheaper than the front.
    """

    start_ts = start or datetime(2024, 1, 2, tzinfo=timezone.utc)
    sessions = _session_days(n_sessions, start_ts)
    first_expiry = front_start or date(2024, 3, 15)
    contracts: list[tuple[str, date]] = []
    year = first_expiry.year
    month = first_expiry.month
    day = first_expiry.day
    for i in range(contract_months):
        exp = date(year, month, min(day, 28))
        symbol = f"{root}{exp.strftime('%y%m')}"
        contracts.append((symbol, exp))
        month += month_step
        while month > 12:
            month -= 12
            year += 1

    slope = 0.015 if curve == "contango" else -0.015
    observations: list[FuturesContractObservation] = []
    for i, ts in enumerate(sessions):
        spot = 100.0 + 0.02 * i
        for j, (sym, exp) in enumerate(contracts):
            price = spot * (1.0 + slope * j)
            observations.append(
                FuturesContractObservation(
                    contract_symbol=sym,
                    root=root,
                    expiry=exp,
                    price=float(price),
                    timestamp=ts,
                    volume=1000.0 - 50.0 * j,
                    open_interest=5000.0 - 200.0 * j,
                    multiplier=50.0,
                    settlement_type="settle",
                    exchange="SYN",
                    currency="USD",
                )
            )

    if include_future_quotes:
        future_ts = sessions[-1] + timedelta(days=30)
        last_spot = 100.0 + 0.02 * (n_sessions - 1)
        for j, (sym, exp) in enumerate(contracts):
            observations.append(
                FuturesContractObservation(
                    contract_symbol=sym,
                    root=root,
                    expiry=exp,
                    price=float(last_spot * (1.0 + slope * j) * 10.0),  # lookahead spike
                    timestamp=future_ts,
                    volume=1.0,
                    open_interest=1.0,
                    multiplier=50.0,
                )
            )

    return ContractChain(root=root, observations=tuple(observations))


def two_leg_chain(
    *,
    root: str = "ES",
    front_price: float = 100.0,
    next_price: float = 105.0,
    as_of: datetime | None = None,
    front_timestamp: datetime | None = None,
    next_timestamp: datetime | None = None,
    front_root: str | None = None,
    next_root: str | None = None,
    front_bid: float | None = None,
    front_ask: float | None = None,
    next_bid: float | None = None,
    next_ask: float | None = None,
    front_expiry: date = date(2024, 3, 15),
    next_expiry: date = date(2024, 6, 14),
) -> ContractChain:
    """Minimal two-contract chain for carry / friction / freshness tests."""

    ts = as_of or datetime(2024, 1, 20, tzinfo=timezone.utc)
    front_obs = FuturesContractObservation(
        contract_symbol=f"{root}{front_expiry.strftime('%y%m')}",
        root=front_root if front_root is not None else root,
        expiry=front_expiry,
        price=front_price,
        timestamp=front_timestamp or ts,
        bid=front_bid,
        ask=front_ask,
        multiplier=50.0,
        settlement_type="settle",
        exchange="SYN",
        currency="USD",
    )
    next_obs = FuturesContractObservation(
        contract_symbol=f"{root}{next_expiry.strftime('%y%m')}",
        root=next_root if next_root is not None else root,
        expiry=next_expiry,
        price=next_price,
        timestamp=next_timestamp or ts,
        bid=next_bid,
        ask=next_ask,
        multiplier=50.0,
        settlement_type="settle",
        exchange="SYN",
        currency="USD",
    )
    return ContractChain(root=root, observations=(front_obs, next_obs))


def expired_only_chain(root: str = "XX") -> ContractChain:
    ts = datetime(2024, 6, 1, tzinfo=timezone.utc)
    obs = FuturesContractObservation(
        contract_symbol=f"{root}2303",
        root=root,
        expiry=date(2023, 3, 15),
        price=100.0,
        timestamp=ts,
    )
    return ContractChain(root=root, observations=(obs,))
