"""Provider-neutral futures contract-chain, roll, and carry interfaces.

Callers supply contract observations. This package does not fetch paid futures
data and does not place futures orders.

Economics: the front/deferred **price gap is carry/curve**, not execution
friction. Execution roll friction is estimated only from bid/ask (and remains
unknown / caller-supplied when those fields are absent). Curve quotes must be
fresh vs ``as_of`` and temporally aligned with each other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Protocol, Sequence

from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import QualityFlag, RESEARCH_ONLY_NOTE, jsonable

CARRY_ASSUMPTIONS = (
    "Roll yield uses only caller-supplied contract prices with timestamp <= as_of.",
    "Annualized roll yield ≈ (F_front / F_next - 1) * (365 / days_between_expiries).",
    "Contango (F_next > F_front) produces negative roll yield for a long; backwardation positive.",
    "curve_gap / roll_gap is the signed relative front/deferred price gap. It is economic carry, not transaction friction.",
    "Execution roll friction is estimated only from bid/ask half-spreads when both legs quote a book; otherwise it is unknown and must be caller-supplied.",
    "Never copy curve_gap into Edge-to-Friction futures_roll — that double-counts carry as a cost.",
    "Front and deferred quotes must be fresh vs as_of and aligned with each other; stale/misaligned pairs fail closed.",
    "Observed observation.root must match ContractChain.root.",
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

DEFAULT_MAX_QUOTE_AGE = timedelta(days=3)
DEFAULT_MAX_FRONT_NEXT_SKEW = timedelta(days=1)
EXECUTION_FRICTION_BID_ASK = "bid_ask_half_spreads"
EXECUTION_FRICTION_UNKNOWN = "unknown_caller_supplied"


def _as_utc(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def _as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return _as_utc(value).date()
    return value


@dataclass(frozen=True)
class QuoteSyncConfig:
    """Fail-closed freshness and alignment for curve quotes."""

    max_quote_age: timedelta = DEFAULT_MAX_QUOTE_AGE
    max_front_next_skew: timedelta = DEFAULT_MAX_FRONT_NEXT_SKEW

    def to_dict(self) -> dict:
        return {
            "max_quote_age_seconds": self.max_quote_age.total_seconds(),
            "max_front_next_skew_seconds": self.max_front_next_skew.total_seconds(),
        }


@dataclass(frozen=True)
class FuturesContractObservation:
    """One point-in-time quote/settle for a listed contract.

    Required later for real-data shadow testing: contract_symbol, root, expiry,
    price, timestamp. Volume and open interest are recommended for roll rules.
    Bid/ask are recommended for *execution* roll friction; they are never
    inferred from the front/deferred settle gap.
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
    curve_gap: float | None
    roll_gap: float | None
    execution_roll_friction: float | None
    execution_roll_friction_source: str
    front_quote_age_seconds: float | None
    next_quote_age_seconds: float | None
    front_next_skew_seconds: float | None
    quote_sync: QuoteSyncConfig
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
            "curve_gap": jsonable(self.curve_gap),
            "roll_gap": jsonable(self.roll_gap),
            "execution_roll_friction": jsonable(self.execution_roll_friction),
            "execution_roll_friction_source": self.execution_roll_friction_source,
            "front_quote_age_seconds": jsonable(self.front_quote_age_seconds),
            "next_quote_age_seconds": jsonable(self.next_quote_age_seconds),
            "front_next_skew_seconds": jsonable(self.front_next_skew_seconds),
            "quote_sync": self.quote_sync.to_dict(),
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "is_usable": self.is_usable,
            "is_order": False,
            "is_live_futures_execution": False,
            "curve_gap_is_not_execution_friction": True,
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


def _finite_price(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf")) and value > 0


def _age_seconds(as_of: datetime, quote: FuturesContractObservation) -> float:
    return (_as_utc(as_of) - _as_utc(quote.timestamp)).total_seconds()


def _root_mismatches(chain: ContractChain) -> tuple[str, ...]:
    bad: list[str] = []
    for obs in chain.observations:
        if obs.root != chain.root:
            bad.append(obs.contract_symbol)
    return tuple(bad)


def estimate_execution_roll_friction(
    front: FuturesContractObservation,
    nxt: FuturesContractObservation,
) -> tuple[float | None, str, tuple[QualityFlag, ...]]:
    """Half-spread crossing cost of rolling front→next. Never uses settle gap."""

    flags: list[QualityFlag] = []
    book = (front.bid, front.ask, nxt.bid, nxt.ask)
    if any(v is None for v in book):
        flags.append(
            flag(
                QualityCode.UNKNOWN_EXECUTION_FRICTION,
                QualityLevel.WARN,
                "Bid/ask missing on front or deferred; execution roll friction is unknown and must be caller-supplied",
            )
        )
        return None, EXECUTION_FRICTION_UNKNOWN, tuple(flags)

    assert front.bid is not None and front.ask is not None
    assert nxt.bid is not None and nxt.ask is not None
    values = (front.bid, front.ask, nxt.bid, nxt.ask)
    if any(not _finite_price(v) for v in values):
        flags.append(
            flag(
                QualityCode.NON_FINITE,
                QualityLevel.FAIL,
                "Bid/ask must be finite and strictly positive to estimate execution roll friction",
            )
        )
        return None, EXECUTION_FRICTION_UNKNOWN, tuple(flags)
    if front.bid > front.ask or nxt.bid > nxt.ask:
        flags.append(
            flag(
                QualityCode.INVALID_INPUT,
                QualityLevel.FAIL,
                "Inverted bid/ask book cannot estimate execution roll friction",
            )
        )
        return None, EXECUTION_FRICTION_UNKNOWN, tuple(flags)

    front_mid = 0.5 * (front.bid + front.ask)
    next_mid = 0.5 * (nxt.bid + nxt.ask)
    friction = ((front.ask - front.bid) / (2.0 * front_mid)) + ((nxt.ask - nxt.bid) / (2.0 * next_mid))
    return float(friction), EXECUTION_FRICTION_BID_ASK, tuple(flags)


def _carry(
    *,
    as_of: datetime,
    root: str,
    flags: Sequence[QualityFlag],
    quote_sync: QuoteSyncConfig,
    front: FuturesContractObservation | None = None,
    next_contract: FuturesContractObservation | None = None,
    curve_state: str = "unavailable",
    roll_yield_annualized: float | None = None,
    days_between_expiries: int | None = None,
    days_to_front_expiry: int | None = None,
    roll_recommended: bool = False,
    roll_direction: str | None = None,
    curve_gap: float | None = None,
    execution_roll_friction: float | None = None,
    execution_roll_friction_source: str = EXECUTION_FRICTION_UNKNOWN,
    front_quote_age_seconds: float | None = None,
    next_quote_age_seconds: float | None = None,
    front_next_skew_seconds: float | None = None,
) -> CarrySnapshot:
    return CarrySnapshot(
        as_of=as_of,
        root=root,
        front=front,
        next_contract=next_contract,
        curve_state=curve_state,
        roll_yield_annualized=roll_yield_annualized,
        days_between_expiries=days_between_expiries,
        days_to_front_expiry=days_to_front_expiry,
        roll_recommended=roll_recommended,
        roll_direction=roll_direction,
        curve_gap=curve_gap,
        roll_gap=curve_gap,
        execution_roll_friction=execution_roll_friction,
        execution_roll_friction_source=execution_roll_friction_source,
        front_quote_age_seconds=front_quote_age_seconds,
        next_quote_age_seconds=next_quote_age_seconds,
        front_next_skew_seconds=front_next_skew_seconds,
        quote_sync=quote_sync,
        quality_flags=tuple(flags),
    )


def evaluate_carry(
    chain: ContractChain,
    *,
    as_of: datetime,
    roll_lead_days: int = 5,
    quote_sync: QuoteSyncConfig | None = None,
    computed_at: datetime | None = None,  # reserved for envelope symmetry
) -> CarrySnapshot:
    del computed_at
    sync = quote_sync or QuoteSyncConfig()
    flags: list[QualityFlag] = []
    as_of_u = _as_utc(as_of)

    mismatched = _root_mismatches(chain)
    if mismatched:
        flags.append(
            flag(
                QualityCode.ROOT_MISMATCH,
                QualityLevel.FAIL,
                f"Observation root does not match chain root {chain.root!r}: {mismatched}",
            )
        )
        return _carry(as_of=as_of_u, root=chain.root, flags=flags, quote_sync=sync)

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
        return _carry(as_of=as_of_u, root=chain.root, flags=flags, quote_sync=sync)

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
    if not live:
        flags.append(
            flag(
                QualityCode.EXPIRED_CONTRACT,
                QualityLevel.FAIL,
                "All contracts with quotes at as_of are expired",
            )
        )
        return _carry(as_of=as_of_u, root=chain.root, flags=flags, quote_sync=sync)

    front = live[0]
    nxt = live[1] if len(live) > 1 else None
    front_age = _age_seconds(as_of_u, front)
    next_age = _age_seconds(as_of_u, nxt) if nxt is not None else None
    skew = None
    if nxt is not None:
        skew = abs((_as_utc(front.timestamp) - _as_utc(nxt.timestamp)).total_seconds())

    stale = False
    if front_age > sync.max_quote_age.total_seconds():
        stale = True
        flags.append(
            flag(
                QualityCode.STALE_QUOTE,
                QualityLevel.FAIL,
                f"Front quote age {front_age:.0f}s exceeds max_quote_age {sync.max_quote_age.total_seconds():.0f}s",
            )
        )
    if next_age is not None and next_age > sync.max_quote_age.total_seconds():
        stale = True
        flags.append(
            flag(
                QualityCode.STALE_QUOTE,
                QualityLevel.FAIL,
                f"Deferred quote age {next_age:.0f}s exceeds max_quote_age {sync.max_quote_age.total_seconds():.0f}s",
            )
        )
    if skew is not None and skew > sync.max_front_next_skew.total_seconds():
        stale = True
        flags.append(
            flag(
                QualityCode.MISALIGNED_QUOTES,
                QualityLevel.FAIL,
                f"Front/next timestamp skew {skew:.0f}s exceeds max_front_next_skew "
                f"{sync.max_front_next_skew.total_seconds():.0f}s",
            )
        )
    if stale:
        return _carry(
            as_of=as_of_u,
            root=chain.root,
            flags=flags,
            quote_sync=sync,
            front=front,
            next_contract=nxt,
            days_to_front_expiry=(front.expiry - as_of_u.date()).days,
            front_quote_age_seconds=front_age,
            next_quote_age_seconds=next_age,
            front_next_skew_seconds=skew,
        )

    if any(not _finite_price(q.price) for q in live[:2]):
        flags.append(flag(QualityCode.NON_FINITE, QualityLevel.FAIL, "Front/next price is not finite"))

    dte = (front.expiry - as_of_u.date()).days
    if nxt is None:
        flags.append(
            flag(
                QualityCode.INSUFFICIENT_CHAIN,
                QualityLevel.FAIL,
                "Need a deferred contract to compute carry / roll",
            )
        )
        return _carry(
            as_of=as_of_u,
            root=chain.root,
            flags=flags,
            quote_sync=sync,
            front=front,
            days_to_front_expiry=dte,
            front_quote_age_seconds=front_age,
        )

    days_between = (nxt.expiry - front.expiry).days
    roll_yield = None
    curve_state = "flat"
    curve_gap = None
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
        curve_gap = (nxt.price - front.price) / abs(front.price)
        if nxt.price > front.price:
            curve_state = "contango"
        elif nxt.price < front.price:
            curve_state = "backwardation"

    exec_friction, exec_source, exec_flags = estimate_execution_roll_friction(front, nxt)
    flags.extend(exec_flags)
    if any(f.level is QualityLevel.FAIL for f in exec_flags):
        return _carry(
            as_of=as_of_u,
            root=chain.root,
            flags=flags,
            quote_sync=sync,
            front=front,
            next_contract=nxt,
            days_to_front_expiry=dte,
            front_quote_age_seconds=front_age,
            next_quote_age_seconds=next_age,
            front_next_skew_seconds=skew,
            execution_roll_friction_source=exec_source,
        )

    roll_recommended = dte <= roll_lead_days and days_between > 0
    return _carry(
        as_of=as_of_u,
        root=chain.root,
        flags=flags,
        quote_sync=sync,
        front=front,
        next_contract=nxt,
        curve_state=curve_state if days_between > 0 else "unavailable",
        roll_yield_annualized=roll_yield,
        days_between_expiries=days_between if days_between > 0 else None,
        days_to_front_expiry=dte,
        roll_recommended=roll_recommended,
        roll_direction="front_to_next",
        curve_gap=curve_gap,
        execution_roll_friction=exec_friction,
        execution_roll_friction_source=exec_source,
        front_quote_age_seconds=front_age,
        next_quote_age_seconds=next_age,
        front_next_skew_seconds=skew,
    )


def required_provider_fields() -> dict[str, tuple[str, ...]]:
    return {
        "required": REQUIRED_REAL_DATA_FIELDS,
        "recommended": RECOMMENDED_REAL_DATA_FIELDS,
    }
