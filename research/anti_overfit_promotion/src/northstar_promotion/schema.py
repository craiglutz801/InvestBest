"""Shared serializable result helpers for Stage 5 evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from northstar_promotion.quality import QualityFlag, QualityLevel

SCHEMA_VERSION = "1.0.0"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
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
        return isoformat(value)
    if isinstance(value, QualityFlag):
        return value.to_dict()
    if isinstance(value, QualityLevel):
        return value.value
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    if isinstance(value, Mapping):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return str(value)


def library_versions() -> dict[str, str]:
    import numpy
    import scipy

    from northstar_promotion import __version__

    return {
        "northstar_promotion": __version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
    }


@dataclass(frozen=True)
class TimeWindow:
    """Half-open index window ``[start_index, end_index)``."""

    start_index: int
    end_index: int
    label: str = ""
    start_timestamp: datetime | None = None
    end_timestamp: datetime | None = None

    def __post_init__(self) -> None:
        if self.end_index < self.start_index:
            raise ValueError("end_index must be >= start_index")

    @property
    def length(self) -> int:
        return int(self.end_index - self.start_index)

    def overlaps(self, other: TimeWindow) -> bool:
        return self.start_index < other.end_index and other.start_index < self.end_index

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_index": self.start_index,
            "end_index": self.end_index,
            "label": self.label,
            "length": self.length,
            "start_timestamp": isoformat(self.start_timestamp),
            "end_timestamp": isoformat(self.end_timestamp),
        }


@dataclass(frozen=True)
class EvaluationMeta:
    schema_version: str
    package_version: str
    library_versions: Mapping[str, str]
    computed_at: datetime
    method: str
    parameters: Mapping[str, Any]
    assumptions: tuple[str, ...]
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return not any(flag.level is QualityLevel.FAIL for flag in self.quality_flags)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["computed_at"] = isoformat(self.computed_at)
        payload["library_versions"] = dict(self.library_versions)
        payload["parameters"] = jsonable(self.parameters)
        payload["assumptions"] = list(self.assumptions)
        payload["quality_flags"] = [flag.to_dict() for flag in self.quality_flags]
        payload["notes"] = list(self.notes)
        payload["details"] = jsonable(self.details)
        payload["is_usable"] = self.is_usable
        return payload


def make_meta(
    *,
    method: str,
    parameters: Mapping[str, Any],
    assumptions: Sequence[str],
    quality_flags: Sequence[QualityFlag],
    notes: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
    computed_at: datetime | None = None,
) -> EvaluationMeta:
    from northstar_promotion import __version__

    flags = tuple(quality_flags)
    return EvaluationMeta(
        schema_version=SCHEMA_VERSION,
        package_version=__version__,
        library_versions=library_versions(),
        computed_at=computed_at or utcnow(),
        method=method,
        parameters=dict(parameters),
        assumptions=tuple(assumptions),
        quality_flags=flags,
        notes=tuple(notes),
        details=dict(details or {}),
    )
