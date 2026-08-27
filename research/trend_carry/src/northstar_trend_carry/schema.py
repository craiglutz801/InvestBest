"""Typed research contracts for Stage 3 trend and futures carry.

Results are evidence for research / shadow testing. They are not orders,
broker instructions, or permission to change live or paper positions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from northstar_trend_carry.quality import QualityLevel

SCHEMA_VERSION = "0.1.1"
PACKAGE_VERSION = "0.1.1"

RESEARCH_ONLY_NOTE = (
    "Research-only. Not an order, not portfolio-engine input, and not a live "
    "or paper-trading instruction."
)


@dataclass(frozen=True)
class QualityFlag:
    code: str
    level: QualityLevel
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "level": self.level.value, "message": self.message}


@dataclass(frozen=True)
class SampleWindow:
    """Inclusive window actually used at the evaluation timestamp."""

    n_obs_input: int
    n_obs_used: int
    start_index: int | None
    end_index: int | None
    start_timestamp: datetime | None
    end_timestamp: datetime | None
    frequency: str | None = "trading_day"
    dropped_missing: int = 0
    as_of_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_obs_input": self.n_obs_input,
            "n_obs_used": self.n_obs_used,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "start_timestamp": _iso(self.start_timestamp),
            "end_timestamp": _iso(self.end_timestamp),
            "frequency": self.frequency,
            "dropped_missing": self.dropped_missing,
            "as_of_index": self.as_of_index,
        }


@dataclass(frozen=True)
class HorizonSpec:
    """Named lookback. Defaults approximate 1m / 3m / 6m / 12m trading days."""

    name: str
    lookback_bars: int
    intended_holding_bars: int | None = None
    annualization_bars: int = 252

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "lookback_bars": self.lookback_bars,
            "intended_holding_bars": self.intended_holding_bars,
            "annualization_bars": self.annualization_bars,
        }


DEFAULT_HORIZONS: tuple[HorizonSpec, ...] = (
    HorizonSpec(name="1m", lookback_bars=21, intended_holding_bars=21),
    HorizonSpec(name="3m", lookback_bars=63, intended_holding_bars=63),
    HorizonSpec(name="6m", lookback_bars=126, intended_holding_bars=126),
    HorizonSpec(name="12m", lookback_bars=252, intended_holding_bars=252),
)


@dataclass(frozen=True)
class EnsembleConfig:
    """Multi-speed ensemble settings. None of these are live strategy thresholds."""

    horizons: tuple[HorizonSpec, ...] = DEFAULT_HORIZONS
    vol_lookback_bars: int = 60
    annualization_bars: int = 252
    signal_cap: float = 2.0
    vol_target: float = 0.15
    allow_short: bool = True
    min_horizon_obs: int = 5

    def to_dict(self) -> dict[str, Any]:
        return {
            "horizons": [h.to_dict() for h in self.horizons],
            "vol_lookback_bars": self.vol_lookback_bars,
            "annualization_bars": self.annualization_bars,
            "signal_cap": float(self.signal_cap),
            "vol_target": float(self.vol_target),
            "allow_short": self.allow_short,
            "min_horizon_obs": self.min_horizon_obs,
            "ensemble_method": "equal_weight_capped_horizons",
            "does_not_select_optimized_lookback": True,
        }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def library_versions() -> dict[str, str]:
    import numpy

    return {
        "northstar_trend_carry": PACKAGE_VERSION,
        "numpy": numpy.__version__,
    }


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


def has_fail(flags: Sequence[QualityFlag]) -> bool:
    return any(flag.level is QualityLevel.FAIL for flag in flags)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, QualityFlag):
        return value.to_dict()
    if isinstance(value, QualityLevel):
        return value.value
    if isinstance(value, HorizonSpec):
        return value.to_dict()
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def result_envelope(
    *,
    result_id: str,
    name: str,
    sample: SampleWindow,
    method: str,
    parameters: Mapping[str, Any],
    statistics: Mapping[str, float | int | None],
    quality_flags: Sequence[QualityFlag],
    interpretation: str,
    assumptions: Sequence[str] = (),
    notes: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
    as_of: datetime | None = None,
    computed_at: datetime | None = None,
) -> dict[str, Any]:
    flags = tuple(quality_flags)
    if not flags:
        flags = (
            QualityFlag(
                code="ok",
                level=QualityLevel.OK,
                message="Inputs were usable and the statistic was computed.",
            ),
        )
    payload = {
        "result_id": result_id,
        "name": name,
        "schema_version": SCHEMA_VERSION,
        "package_version": PACKAGE_VERSION,
        "library_versions": library_versions(),
        "computed_at": _iso(computed_at or utcnow()),
        "as_of": _iso(as_of),
        "sample": sample.to_dict(),
        "method": method,
        "parameters": jsonable(parameters),
        "statistics": jsonable(statistics),
        "quality_flags": [f.to_dict() for f in flags],
        "interpretation": interpretation,
        "assumptions": list(assumptions),
        "notes": list(notes) if notes else [RESEARCH_ONLY_NOTE],
        "details": jsonable(details or {}),
        "is_usable": not has_fail(flags),
        "is_order": False,
        "activates_production_signal": False,
    }
    return payload
