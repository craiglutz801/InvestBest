"""Liquidity and shortability snapshots supplied by the caller.

These types are eligibility interfaces only. They do not query a broker,
borrow desk, or order API. Live locates and live quotes are out of scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class LiquiditySnapshot:
    """Point-in-time liquidity / shortability facts provided by the caller."""

    symbol: str
    as_of: datetime | None = None
    adv: float | None = None
    spread_bps: float | None = None
    shortable: bool | None = None
    locate_available: bool | None = None
    borrow_fee_rate: float | None = None
    source: str = "caller_supplied"

    def to_dict(self) -> dict[str, float | str | bool | None]:
        return {
            "symbol": self.symbol,
            "as_of": self.as_of.isoformat() if self.as_of is not None else None,
            "adv": self.adv,
            "spread_bps": self.spread_bps,
            "shortable": self.shortable,
            "locate_available": self.locate_available,
            "borrow_fee_rate": self.borrow_fee_rate,
            "source": self.source,
        }
