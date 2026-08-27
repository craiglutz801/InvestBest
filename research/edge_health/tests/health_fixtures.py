"""Shared fixtures for Stage 4 health tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from northstar_edge_health.config import HealthConfig, HysteresisConfig
from northstar_edge_health.evidence import MeanReversionEvidence, TrendEvidence
from northstar_edge_health.schema import StrategyIdentity

TZ = timezone.utc


def ts(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=TZ)


def later(stamp: datetime, days: int = 1) -> datetime:
    return stamp + timedelta(days=days)


def instant_config() -> HealthConfig:
    """Confirm on a single observation without promoting pause to retire."""

    return HealthConfig(
        hysteresis=HysteresisConfig(
            degraded_confirmations=1,
            paused_confirmations=1,
            retire_confirmations=8,
            recovery_confirmations=1,
            cooldown_observations=1,
        )
    )


MR_IDENTITY = StrategyIdentity(
    strategy_family="mean_reversion",
    strategy_id="mr_cadf_residual",
    instrument_id="PAIR:GLD-GDX",
    horizon="5d",
)

TREND_IDENTITY = StrategyIdentity(
    strategy_family="trend",
    strategy_id="tsmom_ensemble",
    instrument_id="ES",
    horizon="multi",
)


def healthy_mr(as_of: datetime, **overrides: object) -> MeanReversionEvidence:
    payload: dict[str, object] = {
        "as_of": as_of,
        "rolling_adf_pvalues": (0.01, 0.02, 0.01, 0.015),
        "rolling_adf_reject_fraction": 1.0,
        "rolling_cadf_pvalues": (0.01, 0.02, 0.01),
        "rolling_cadf_reject_fraction": 1.0,
        "half_life": 10.0,
        "half_life_baseline": 10.0,
        "hedge_ratio": 1.00,
        "hedge_ratio_baseline": 1.00,
        "residual_volatility": 0.02,
        "residual_volatility_baseline": 0.02,
        "convergence_rate": 0.06931471805599453,
        "convergence_rate_baseline": 0.06931471805599453,
        "structural_break_detected": False,
        "realized_friction": 0.0010,
        "expected_friction": 0.0010,
        "usable": True,
    }
    payload.update(overrides)
    return MeanReversionEvidence(**payload)  # type: ignore[arg-type]


def healthy_trend(as_of: datetime, **overrides: object) -> TrendEvidence:
    payload: dict[str, object] = {
        "as_of": as_of,
        "horizon_signs": (1, 1, 1, 1),
        "persistence": 0.72,
        "whipsaw_rate": 0.10,
        "volatility_shock": False,
        "realized_implementation_cost": 0.0008,
        "expected_implementation_cost": 0.0008,
        "cross_market_breadth": 0.70,
        "usable": True,
    }
    payload.update(overrides)
    return TrendEvidence(**payload)  # type: ignore[arg-type]
