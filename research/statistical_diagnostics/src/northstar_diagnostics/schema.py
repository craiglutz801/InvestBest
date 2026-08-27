"""Common Stage 1 diagnostic result schema.

Every diagnostic returns :class:`DiagnosticResult` (or a thin wrapper that
embeds one) so formation-window metadata, assumptions, statistics, and
quality flags are always present and serializable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from northstar_diagnostics.quality import QualityCode, QualityLevel

SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class QualityFlag:
    code: str
    level: QualityLevel
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "level": self.level.value, "message": self.message}


@dataclass(frozen=True)
class SampleWindow:
    """Inclusive formation window actually used in the calculation."""

    n_obs_input: int
    n_obs_used: int
    start_index: int | None
    end_index: int | None  # inclusive last used observation
    start_timestamp: datetime | None
    end_timestamp: datetime | None
    frequency: str | None = None
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
class DiagnosticResult:
    """Stable typed contract for Stage 1 diagnostics.

    This object is evidence for strategy eligibility research. It is not an
    order, signal, or permission to trade.
    """

    diagnostic_id: str
    name: str
    schema_version: str
    package_version: str
    library_versions: Mapping[str, str]
    computed_at: datetime
    as_of: datetime | None
    sample: SampleWindow
    method: str
    parameters: Mapping[str, Any]
    statistics: Mapping[str, float | int | None]
    pvalue: float | None
    critical_values: Mapping[str, float]
    hypotheses: Mapping[str, str]
    assumptions: tuple[str, ...]
    quality_flags: tuple[QualityFlag, ...]
    interpretation: str
    notes: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return not any(flag.level is QualityLevel.FAIL for flag in self.quality_flags)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["computed_at"] = _iso(self.computed_at)
        payload["as_of"] = _iso(self.as_of)
        payload["sample"] = self.sample.to_dict()
        payload["quality_flags"] = [flag.to_dict() for flag in self.quality_flags]
        payload["library_versions"] = dict(self.library_versions)
        payload["parameters"] = _jsonable(self.parameters)
        payload["statistics"] = _jsonable(self.statistics)
        payload["critical_values"] = dict(self.critical_values)
        payload["hypotheses"] = dict(self.hypotheses)
        payload["assumptions"] = list(self.assumptions)
        payload["notes"] = list(self.notes)
        payload["details"] = _jsonable(self.details)
        payload["is_usable"] = self.is_usable
        return payload


def library_versions() -> dict[str, str]:
    import numpy
    import scipy
    import statsmodels

    from northstar_diagnostics import __version__

    return {
        "northstar_diagnostics": __version__,
        "numpy": numpy.__version__,
        "scipy": scipy.__version__,
        "statsmodels": statsmodels.__version__,
    }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_result(
    *,
    diagnostic_id: str,
    name: str,
    sample: SampleWindow,
    method: str,
    parameters: Mapping[str, Any],
    statistics: Mapping[str, float | int | None],
    pvalue: float | None,
    critical_values: Mapping[str, float] | None = None,
    hypotheses: Mapping[str, str] | None = None,
    assumptions: Sequence[str] = (),
    quality_flags: Sequence[QualityFlag] = (),
    interpretation: str,
    notes: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
    as_of: datetime | None = None,
    computed_at: datetime | None = None,
) -> DiagnosticResult:
    from northstar_diagnostics import __version__

    flags = tuple(quality_flags)
    if not flags:
        flags = (
            QualityFlag(
                code="ok",
                level=QualityLevel.OK,
                message="Inputs were usable and the statistic was computed.",
            ),
        )
    return DiagnosticResult(
        diagnostic_id=diagnostic_id,
        name=name,
        schema_version=SCHEMA_VERSION,
        package_version=__version__,
        library_versions=library_versions(),
        computed_at=computed_at or utcnow(),
        as_of=as_of,
        sample=sample,
        method=method,
        parameters=dict(parameters),
        statistics=dict(statistics),
        pvalue=pvalue,
        critical_values=dict(critical_values or {}),
        hypotheses=dict(hypotheses or {}),
        assumptions=tuple(assumptions),
        quality_flags=flags,
        interpretation=interpretation,
        notes=tuple(notes),
        details=dict(details or {}),
    )


def failed_result(
    *,
    diagnostic_id: str,
    name: str,
    sample: SampleWindow,
    method: str,
    parameters: Mapping[str, Any],
    quality_flags: Sequence[QualityFlag],
    assumptions: Sequence[str] = (),
    notes: Sequence[str] = (),
    as_of: datetime | None = None,
    computed_at: datetime | None = None,
    interpretation: str = "not_computed",
) -> DiagnosticResult:
    flags = list(quality_flags)
    if not any(flag.code == QualityCode.NOT_COMPUTED for flag in flags):
        flags.append(
            QualityFlag(
                code=QualityCode.NOT_COMPUTED,
                level=QualityLevel.FAIL,
                message="Statistic was not computed because inputs failed quality checks.",
            )
        )
    return make_result(
        diagnostic_id=diagnostic_id,
        name=name,
        sample=sample,
        method=method,
        parameters=parameters,
        statistics={},
        pvalue=None,
        critical_values={},
        hypotheses={},
        assumptions=assumptions,
        quality_flags=flags,
        interpretation=interpretation,
        notes=notes,
        as_of=as_of,
        computed_at=computed_at,
    )


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _jsonable(value: Any) -> Any:
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
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value
