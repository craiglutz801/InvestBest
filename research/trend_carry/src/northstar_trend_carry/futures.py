"""Provider-neutral futures contract-chain, roll, and carry interfaces.

Callers supply contract observations. This package does not fetch paid futures
data and does not place futures orders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Protocol, Sequence

from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import QualityFlag, RESEARCH_ONLY_NOTE, jsonable, utcnow

CARRY_ASSUMPTIONS = (
    "Roll yield uses only caller-supplied contract prices with timestamp <= as_of.",
    "Annualized roll yield ≈ (F_front / F_next - 1) * (365 / days_between_expiries).",
    "Contango (F_next > F_front) produces negative roll yield for a long; backwardation positive.",
    "Curve shape is not a trade. Carry informs research confidence and must not double-count trend.",
    "Live contract selection / roll execution is out of scope.",
)

REQUIRED_REAL_DATA_FIELDS = (
    "contract_symbol",
    "root",
    "expiry",
    "price",
    "timestamp",
)
RECOMMENDED_REAL_DATA_FIELDS = (
    "volume",
    "open_interest",
    "multiplier",
    "bid",
    "ask",
    "settlement_type",
    "exchange",
    "currency",
    "last_trade_date",
)


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return _as_utc(value).date()
    return value


@dataclass(frozen=True)
class FuturesContractObservation:
    """One point-in-time quote/settle for a listed contract.

    Required later for real-data shadow testing: contract_symbol, root, expiry,
    price, timestamp. Volume and open interest are recommended for roll rules.
    """

    contract_symbol: str
    root: str
    expiry: date
    price: float
    timestamp: datetime
    volume: float | None = None
    open_interest: float | None = None
    multiplier: float | None = None
    bid: float | None = None
    ask: float | None = None
    settlement_type: str | None = None
    exchange: str | None = None
    currency: str | None = None

    def to_dict(self) -> dict:
        return {
            "contract_symbol": self.contract_symbol,
            "root": self.root,
            "expiry": self.expiry.isoformat(),
            "price": jsonable(self.price),
            "timestamp": jsonable(_as_utc(self.timestamp)),
            "volume": jsonable(self.volume),
            "open_interest": jsonable(self.open_interest),
            "multiplier": jsonable(self.multiplier),
            "bid": jsonable(self.bid),
            "ask": jsonable(self.ask),
            "settlement_type": self.settlement_type,
            "exchange": self.exchange,
            "currency": self.currency,
        }


@dataclass(frozen=True)
class ContractChain:
    root: str
    observations: tuple[FuturesContractObservation, ...]

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "n_observations": len(self.observations),
            "observations": [o.to_dict() for o in self.observations],
        }


class FuturesChainProvider(Protocol):
    """Provider-neutral adapter. Real vendors implement this later."""

    def contract_observations(
        self,
        root: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[FuturesContractObservation]:
        ...


@dataclass(frozen=True)
class InMemoryFuturesProvider:
    """Deterministic fixture adapter. Not a paid data client."""

    chains: dict[str, ContractChain]

    def contract_observations(
        self,
        root: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> Sequence[FuturesContractObservation]:
        chain = self.chains.get(root)
        if chain is None:
            return ()
        rows = chain.observations
        if start is not None:
            start_u = _as_utc(start)
            rows = tuple(o for o in rows if _as_utc(o.timestamp) >= start_u)
        if end is not None:
            end_u = _as_utc(end)
            rows = tuple(o for o in rows if _as_utc(o.timestamp) <= end_u)
        return rows


@dataclass(frozen=True)
class CarrySnapshot:
    as_of: datetime
    root: str
    front: FuturesContractObservation | None
    next_contract: FuturesContractObservation | None
    curve_state: str
    roll_yield_annualized: float | None
    days_between_expiries: int | None
    days_to_front_expiry: int | None
    roll_recommended: bool
    roll_direction: str | None
    estimated_roll_friction: float | None
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...] = (RESEARCH_ONLY_NOTE, *CARRY_ASSUMPTIONS)

    @property
    def is_usable(self) -> bool:
        return not any(f.level is QualityLevel.FAIL for f in self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "as_of": jsonable(self.as_of),
            "root": self.root,
            "front": None if self.front is None else self.front.to_dict(),
            "next_contract": None if self.next_contract is None else self.next_contract.to_dict(),
            "curve_state": self.curve_state,
            "roll_yield_annualized": jsonable(self.roll_yield_annualized),
            "days_between_expiries": self.days_between_expiries,
            "days_to_front_expiry": self.days_to_front_expiry,
            "roll_recommended": self.roll_recommended,
            "roll_direction": self.roll_direction,
            "estimated_roll_friction": jsonable(self.estimated_roll_friction),
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "is_usable": self.is_usable,
            "is_order": False,
            "is_live_futures_execution": False,
        }


def observations_as_of(
    observations: Sequence[FuturesContractObservation],
    as_of: datetime,
) -> tuple[FuturesContractObservation, ...]:
    cutoff = _as_utc(as_of)
    return tuple(o for o in observations if _as_utc(o.timestamp) <= cutoff)


def last_quotes_by_contract(
    observations: Sequence[FuturesContractObservation],
    as_of: datetime,
) -> dict[str, FuturesContractObservation]:
    latest: dict[str, FuturesContractObservation] = {}
    for obs in observations_as_of(observations, as_of):
        prev = latest.get(obs.contract_symbol)
        if prev is None or _as_utc(obs.timestamp) >= _as_utc(prev.timestamp):
            latest[obs.contract_symbol] = obs
    return latest


def live_quotes(
    observations: Sequence[FuturesContractObservation],
    as_of: datetime,
) -> list[FuturesContractObservation]:
    as_of_d = _as_date(as_of)
    quotes = last_quotes_by_contract(observations, as_of)
    live = [q for q in quotes.values() if q.expiry >= as_of_d]
    live.sort(key=lambda q: (q.expiry, q.contract_symbol))
    return live


def evaluate_carry(
    chain: ContractChain,
    *,
    as_of: datetime,
    roll_lead_days: int = 5,
    computed_at: datetime | None = None,  # reserved for envelope symmetry
) -> CarrySnapshot:
    del computed_at
    flags: list[QualityFlag] = []
    as_of_u = _as_utc(as_of)
    pit = observations_as_of(chain.observations, as_of_u)
    if not pit:
        flags.append(
            flag(
                QualityCode.MISSING_CONTRACT,
                QualityLevel.FAIL,
                "No contract observations at or before as_of (lookahead blocked)",
            )
        )
        flags.append(
            flag(
                QualityCode.LOOKAHEAD_BLOCKED,
                QualityLevel.OK,
                "Quotes after as_of were ignored",
            )
        )
        return CarrySnapshot(
            as_of=as_of_u,
            root=chain.root,
            front=None,
            next_contract=None,
            curve_state="unavailable",
            roll_yield_annualized=None,
            days_between_expiries=None,
            days_to_front_expiry=None,
            roll_recommended=False,
            roll_direction=None,
            estimated_roll_friction=None,
            quality_flags=tuple(flags),
        )

    later = [o for o in chain.observations if _as_utc(o.timestamp) > as_of_u]
    if later:
        flags.append(
            flag(
                QualityCode.LOOKAHEAD_BLOCKED,
                QualityLevel.OK,
                f"Ignored {len(later)} observations after as_of",
            )
        )

    live = live_quotes(chain.observations, as_of_u)
    expired_only = not live
    if expired_only:
        flags.append(
            flag(
                QualityCode.EXPIRED_CONTRACT,
                QualityLevel.FAIL,
                "All contracts with quotes at as_of are expired",
            )
        )
        return CarrySnapshot(
            as_of=as_of_u,
            root=chain.root,
            front=None,
            next_contract=None,
            curve_state="unavailable",
            roll_yield_annualized=None,
            days_between_expiries=None,
            days_to_front_expiry=None,
            roll_recommended=False,
            roll_direction=None,
            estimated_roll_friction=None,
            quality_flags=tuple(flags),
        )

    front = live[0]
    nxt = live[1] if len(live) > 1 else None
    if any(not _finite_price(q.price) for q in live[:2]):
        flags.append(flag(QualityCode.NON_FINITE, QualityLevel.FAIL, "Front/next price is not finite"))

    dte = (front.expiry - as_of_u.date()).days
    roll_direction = "front_to_next"
    roll_recommended = False
    if nxt is None:
        flags.append(
            flag(
                QualityCode.INSUFFICIENT_CHAIN,
                QualityLevel.FAIL,
                "Need a deferred contract to compute carry / roll",
            )
        )
        roll_direction = None
        return CarrySnapshot(
            as_of=as_of_u,
            root=chain.root,
            front=front,
            next_contract=None,
            curve_state="unavailable",
            roll_yield_annualized=None,
            days_between_expiries=None,
            days_to_front_expiry=dte,
            roll_recommended=False,
            roll_direction=None,
            estimated_roll_friction=None,
            quality_flags=tuple(flags),
        )

    days_between = (nxt.expiry - front.expiry).days
    roll_yield = None
    curve_state = "flat"
    friction = None
    if days_between <= 0:
        flags.append(
            flag(
                QualityCode.INVALID_INPUT,
                QualityLevel.FAIL,
                "Deferred expiry must be after front expiry",
            )
        )
    elif not _finite_price(front.price) or not _finite_price(nxt.price) or nxt.price == 0:
        flags.append(flag(QualityCode.NON_FINITE, QualityLevel.FAIL, "Invalid front/next prices"))
    else:
        roll_yield = (front.price / nxt.price - 1.0) * (365.0 / float(days_between))
        if nxt.price > front.price:
            curve_state = "contango"
        elif nxt.price < front.price:
            curve_state = "backwardation"
        friction = abs(nxt.price - front.price) / abs(front.price)
        roll_recommended = dte <= roll_lead_days

    return CarrySnapshot(
        as_of=as_of_u,
        root=chain.root,
        front=front,
        next_contract=nxt,
        curve_state=curve_state,
        roll_yield_annualized=roll_yield,
        days_between_expiries=days_between if days_between > 0 else None,
        days_to_front_expiry=dte,
        roll_recommended=roll_recommended,
        roll_direction=roll_direction,
        estimated_roll_friction=friction,
        quality_flags=tuple(flags),
    )


def _finite_price(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf")) and value > 0


def required_provider_fields() -> dict[str, tuple[str, ...]]:
    return {
        "required": REQUIRED_REAL_DATA_FIELDS,
        "recommended": RECOMMENDED_REAL_DATA_FIELDS,
    }
