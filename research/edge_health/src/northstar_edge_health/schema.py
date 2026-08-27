"""Persistable Stage 4 health snapshot schema (audit / attribution)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from northstar_edge_health.states import HealthState

SCHEMA_VERSION = "4.0.0"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class StrategyIdentity:
    strategy_family: str
    strategy_id: str
    instrument_id: str
    horizon: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "strategy_family": self.strategy_family,
            "strategy_id": self.strategy_id,
            "instrument_id": self.instrument_id,
            "horizon": self.horizon,
        }


@dataclass(frozen=True)
class ReasonDetail:
    code: str
    state: HealthState
    message: str
    hard: bool = False
    metric: str | None = None
    value: float | None = None
    threshold: float | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ReasonDetail:
        return cls(
            code=str(payload["code"]),
            state=HealthState(payload["state"]),
            message=str(payload["message"]),
            hard=bool(payload.get("hard", False)),
            metric=payload.get("metric"),
            value=payload.get("value"),
            threshold=payload.get("threshold"),
        )


@dataclass(frozen=True)
class HysteresisState:
    consecutive_instantaneous: int = 0
    last_instantaneous: HealthState | None = None
    consecutive_healthy_instantaneous: int = 0
    consecutive_pause_emitted: int = 0
    cooldown_remaining: int = 0
    held: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "consecutive_instantaneous": self.consecutive_instantaneous,
            "last_instantaneous": None if self.last_instantaneous is None else self.last_instantaneous.value,
            "consecutive_healthy_instantaneous": self.consecutive_healthy_instantaneous,
            "consecutive_pause_emitted": self.consecutive_pause_emitted,
            "cooldown_remaining": self.cooldown_remaining,
            "held": self.held,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any] | None) -> HysteresisState:
        if not payload:
            return cls()
        last = payload.get("last_instantaneous")
        return cls(
            consecutive_instantaneous=int(payload.get("consecutive_instantaneous", 0)),
            last_instantaneous=HealthState(last) if last else None,
            consecutive_healthy_instantaneous=int(payload.get("consecutive_healthy_instantaneous", 0)),
            consecutive_pause_emitted=int(payload.get("consecutive_pause_emitted", 0)),
            cooldown_remaining=int(payload.get("cooldown_remaining", 0)),
            held=bool(payload.get("held", False)),
        )


@dataclass(frozen=True)
class HealthSnapshot:
    """Versioned, JSON-serializable health snapshot.

    Advisory only: ``may_create_order`` and ``may_mutate_positions`` are always
    false. ``subordinate_to_risk_governor`` is always true. Persistence is for
    later audit/attribution, not execution.
    """

    schema_version: str
    snapshot_id: str
    identity: StrategyIdentity
    as_of: datetime
    computed_at: datetime
    state: HealthState
    instantaneous_state: HealthState
    previous_state: HealthState | None
    reason_codes: tuple[str, ...]
    reason_details: tuple[ReasonDetail, ...]
    recommended_risk_multiplier: float
    hysteresis: HysteresisState
    evidence_digest: Mapping[str, Any]
    fail_closed: bool
    notes: tuple[str, ...] = ()
    may_create_order: bool = field(default=False, init=True)
    may_mutate_positions: bool = field(default=False, init=True)
    subordinate_to_risk_governor: bool = field(default=True, init=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "may_create_order", False)
        object.__setattr__(self, "may_mutate_positions", False)
        object.__setattr__(self, "subordinate_to_risk_governor", True)
        if self.recommended_risk_multiplier < 0.0 or self.recommended_risk_multiplier > 1.0:
            raise ValueError("recommended_risk_multiplier must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "identity": self.identity.to_dict(),
            "as_of": isoformat(self.as_of),
            "computed_at": isoformat(self.computed_at),
            "state": self.state.value,
            "instantaneous_state": self.instantaneous_state.value,
            "previous_state": None if self.previous_state is None else self.previous_state.value,
            "reason_codes": list(self.reason_codes),
            "reason_details": [item.to_dict() for item in self.reason_details],
            "recommended_risk_multiplier": self.recommended_risk_multiplier,
            "hysteresis": self.hysteresis.to_dict(),
            "evidence_digest": dict(self.evidence_digest),
            "fail_closed": self.fail_closed,
            "notes": list(self.notes),
            "may_create_order": False,
            "may_mutate_positions": False,
            "subordinate_to_risk_governor": True,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, default=str)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> HealthSnapshot:
        identity_raw = payload["identity"]
        identity = StrategyIdentity(
            strategy_family=str(identity_raw["strategy_family"]),
            strategy_id=str(identity_raw["strategy_id"]),
            instrument_id=str(identity_raw["instrument_id"]),
            horizon=identity_raw.get("horizon"),
        )
        previous = payload.get("previous_state")
        details_raw = payload.get("reason_details") or []
        return cls(
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
            snapshot_id=str(payload["snapshot_id"]),
            identity=identity,
            as_of=parse_datetime(payload["as_of"]),  # type: ignore[arg-type]
            computed_at=parse_datetime(payload["computed_at"]),  # type: ignore[arg-type]
            state=HealthState(payload["state"]),
            instantaneous_state=HealthState(payload["instantaneous_state"]),
            previous_state=HealthState(previous) if previous else None,
            reason_codes=tuple(payload.get("reason_codes") or ()),
            reason_details=tuple(ReasonDetail.from_dict(item) for item in details_raw),
            recommended_risk_multiplier=float(payload["recommended_risk_multiplier"]),
            hysteresis=HysteresisState.from_dict(payload.get("hysteresis")),
            evidence_digest=dict(payload.get("evidence_digest") or {}),
            fail_closed=bool(payload.get("fail_closed", False)),
            notes=tuple(payload.get("notes") or ()),
        )

    @classmethod
    def from_json(cls, raw: str) -> HealthSnapshot:
        return cls.from_dict(json.loads(raw))


def make_snapshot_id(
    *,
    identity: StrategyIdentity,
    as_of: datetime,
    state: HealthState,
    instantaneous_state: HealthState,
    reason_codes: Sequence[str],
    multiplier: float,
) -> str:
    payload = {
        "identity": identity.to_dict(),
        "as_of": isoformat(as_of),
        "state": state.value,
        "instantaneous_state": instantaneous_state.value,
        "reason_codes": list(reason_codes),
        "multiplier": multiplier,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return digest[:16]
