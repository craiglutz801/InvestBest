"""Research continuous futures series vs executable contract economics.

These representations are intentionally distinct. Back-adjusted continuous
prices are for trend research only and are not executable P&L.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from northstar_trend_carry.futures import (
    CarrySnapshot,
    ContractChain,
    QuoteSyncConfig,
    evaluate_carry,
    last_quotes_by_contract,
    live_quotes,
    observations_as_of,
)
from northstar_trend_carry.quality import QualityCode, QualityLevel, flag
from northstar_trend_carry.schema import QualityFlag, RESEARCH_ONLY_NOTE, jsonable
from northstar_trend_carry.series import PriceSeries, _as_utc

CONTINUOUS_WARNING = (
    "Research continuous prices are back-adjusted and MUST NOT be treated as "
    "executable contract P&L or as an order."
)


@dataclass(frozen=True)
class RollEvent:
    timestamp: datetime
    from_contract: str
    to_contract: str
    from_price: float
    to_price: float
    adjustment: float
    method: str

    def to_dict(self) -> dict:
        return {
            "timestamp": jsonable(self.timestamp),
            "from_contract": self.from_contract,
            "to_contract": self.to_contract,
            "from_price": jsonable(self.from_price),
            "to_price": jsonable(self.to_price),
            "adjustment": jsonable(self.adjustment),
            "method": self.method,
        }


@dataclass(frozen=True)
class ResearchContinuousSeries:
    """Back-adjusted series for trend research. Not executable economics."""

    root: str
    method: str
    timestamps: tuple[datetime, ...]
    prices: tuple[float, ...]
    front_contract_at: tuple[str, ...]
    roll_events: tuple[RollEvent, ...]
    as_of: datetime
    not_executable_pnl: bool
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...] = (RESEARCH_ONLY_NOTE, CONTINUOUS_WARNING)

    def to_price_series(self, symbol: str | None = None) -> PriceSeries:
        return PriceSeries(
            symbol=symbol or f"{self.root}_CONTINUOUS_RESEARCH",
            timestamps=self.timestamps,
            prices=self.prices,
            asset_class="futures_research_continuous",
        )

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "method": self.method,
            "timestamps": [jsonable(t) for t in self.timestamps],
            "prices": [jsonable(p) for p in self.prices],
            "front_contract_at": list(self.front_contract_at),
            "roll_events": [e.to_dict() for e in self.roll_events],
            "as_of": jsonable(self.as_of),
            "not_executable_pnl": self.not_executable_pnl,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "is_order": False,
        }


@dataclass(frozen=True)
class ExecutableContractEconomics:
    """Point-in-time listed-contract selection and roll cost. Not a live order."""

    as_of: datetime
    root: str
    selected_contract: str | None
    next_contract: str | None
    selected_price: float | None
    days_to_expiry: int | None
    roll_recommended: bool
    roll_direction: str | None
    curve_gap: float | None
    roll_gap: float | None
    execution_roll_friction: float | None
    execution_roll_friction_source: str
    carry: CarrySnapshot
    not_research_continuous: bool
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...] = (
        RESEARCH_ONLY_NOTE,
        "Executable economics describe listed-contract identity, curve/carry gap, and execution roll friction when known.",
        "curve_gap/roll_gap is not transaction friction and is not an order.",
        "This object is not a broker instruction and does not enable futures execution.",
    )

    def to_dict(self) -> dict:
        return {
            "as_of": jsonable(self.as_of),
            "root": self.root,
            "selected_contract": self.selected_contract,
            "next_contract": self.next_contract,
            "selected_price": jsonable(self.selected_price),
            "days_to_expiry": self.days_to_expiry,
            "roll_recommended": self.roll_recommended,
            "roll_direction": self.roll_direction,
            "curve_gap": jsonable(self.curve_gap),
            "roll_gap": jsonable(self.roll_gap),
            "execution_roll_friction": jsonable(self.execution_roll_friction),
            "execution_roll_friction_source": self.execution_roll_friction_source,
            "carry": self.carry.to_dict(),
            "not_research_continuous": self.not_research_continuous,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "is_order": False,
            "is_live_futures_execution": False,
        }


def executable_contract_state(
    chain: ContractChain,
    *,
    as_of: datetime,
    roll_lead_days: int = 5,
    quote_sync: QuoteSyncConfig | None = None,
) -> ExecutableContractEconomics:
    carry = evaluate_carry(chain, as_of=as_of, roll_lead_days=roll_lead_days, quote_sync=quote_sync)
    return ExecutableContractEconomics(
        as_of=carry.as_of,
        root=chain.root,
        selected_contract=None if carry.front is None else carry.front.contract_symbol,
        next_contract=None if carry.next_contract is None else carry.next_contract.contract_symbol,
        selected_price=None if carry.front is None else carry.front.price,
        days_to_expiry=carry.days_to_front_expiry,
        roll_recommended=carry.roll_recommended,
        roll_direction=carry.roll_direction,
        curve_gap=carry.curve_gap,
        roll_gap=carry.roll_gap,
        execution_roll_friction=carry.execution_roll_friction,
        execution_roll_friction_source=carry.execution_roll_friction_source,
        carry=carry,
        not_research_continuous=True,
        quality_flags=carry.quality_flags,
    )


def build_research_continuous_series(
    chain: ContractChain,
    *,
    as_of: datetime,
    method: str = "ratio",
    roll_lead_days: int = 5,
) -> ResearchContinuousSeries:
    """Build a PIT back-adjusted series using only quotes at or before as_of.

    At each session date t <= as_of, the then-front live contract (respecting
    ``roll_lead_days``) is used. When the front identity changes, the adjustment
    uses that date's prices only — never later quotes.
    """

    if method not in {"ratio", "difference", "stitched_front"}:
        raise ValueError("method must be 'ratio', 'difference', or 'stitched_front'")

    as_of_u = _as_utc(as_of)
    pit = observations_as_of(chain.observations, as_of_u)
    flags: list[QualityFlag] = []
    later = [o for o in chain.observations if _as_utc(o.timestamp) > as_of_u]
    if later:
        flags.append(
            flag(
                QualityCode.LOOKAHEAD_BLOCKED,
                QualityLevel.OK,
                f"Continuous series ignored {len(later)} post-as_of quotes",
            )
        )
    if not pit:
        flags.append(
            flag(QualityCode.MISSING_CONTRACT, QualityLevel.FAIL, "No PIT observations for continuous series")
        )
        return ResearchContinuousSeries(
            root=chain.root,
            method=method,
            timestamps=(),
            prices=(),
            front_contract_at=(),
            roll_events=(),
            as_of=as_of_u,
            not_executable_pnl=True,
            quality_flags=tuple(flags),
        )

    sessions = sorted({_as_utc(o.timestamp) for o in pit})
    raw_prices: list[float] = []
    stamps: list[datetime] = []
    fronts: list[str] = []
    events: list[RollEvent] = []
    prev_front: str | None = None
    prev_price: float | None = None

    for t in sessions:
        live = live_quotes(pit, t)
        if not live:
            continue
        # Roll lead: if front DTE <= roll_lead_days and a next exists, use next as research front.
        chosen = live[0]
        dte = (chosen.expiry - t.date()).days
        if dte <= roll_lead_days and len(live) > 1:
            chosen = live[1]
        quotes = last_quotes_by_contract(pit, t)
        q = quotes.get(chosen.contract_symbol)
        if q is None or q.price <= 0 or q.price != q.price:
            flags.append(
                flag(
                    QualityCode.MISSING_CONTRACT,
                    QualityLevel.WARN,
                    f"Missing usable quote for {chosen.contract_symbol} at {t.isoformat()}",
                )
            )
            continue

        if prev_front is not None and chosen.contract_symbol != prev_front and method != "stitched_front":
            old_q = quotes.get(prev_front)
            if old_q is None:
                flags.append(
                    flag(
                        QualityCode.LOOKAHEAD_BLOCKED,
                        QualityLevel.WARN,
                        f"Roll at {t.isoformat()} missing old-front quote; no lookahead fill",
                    )
                )
            else:
                if method == "ratio":
                    if old_q.price == 0:
                        adj = 1.0
                    else:
                        adj = q.price / old_q.price
                    raw_prices = [p * adj for p in raw_prices]
                else:
                    adj = q.price - old_q.price
                    raw_prices = [p + adj for p in raw_prices]
                events.append(
                    RollEvent(
                        timestamp=t,
                        from_contract=prev_front,
                        to_contract=chosen.contract_symbol,
                        from_price=old_q.price,
                        to_price=q.price,
                        adjustment=float(adj),
                        method=method,
                    )
                )

        stamps.append(t)
        raw_prices.append(float(q.price))
        fronts.append(chosen.contract_symbol)
        prev_front = chosen.contract_symbol
        prev_price = float(q.price)

    del prev_price
    if not stamps:
        flags.append(
            flag(QualityCode.INSUFFICIENT_CHAIN, QualityLevel.FAIL, "No live contracts in the PIT window")
        )

    return ResearchContinuousSeries(
        root=chain.root,
        method=method,
        timestamps=tuple(stamps),
        prices=tuple(float(p) for p in raw_prices),
        front_contract_at=tuple(fronts),
        roll_events=tuple(events),
        as_of=as_of_u,
        not_executable_pnl=True,
        quality_flags=tuple(flags),
    )


def representations_are_separate(
    continuous: ResearchContinuousSeries,
    executable: ExecutableContractEconomics,
) -> bool:
    """Guard: research continuous objects are not executable economics."""

    return (
        continuous.not_executable_pnl is True
        and executable.not_research_continuous is True
        and type(continuous) is not type(executable)
    )
