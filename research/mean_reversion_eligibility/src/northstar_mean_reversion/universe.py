"""Economically related candidate-universe interface.

This module does **not** discover a tradable universe. Callers must supply
groups that already have a declared economic relationship (share class, dual
listing, sector peers, calendar futures, etc.). LLM ticker lists without that
declaration are rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping, Sequence

from northstar_diagnostics.efr import FrictionInputs
from northstar_diagnostics.series import ArrayLike

from northstar_mean_reversion.events import EventVetoFlags
from northstar_mean_reversion.liquidity import LiquiditySnapshot
from northstar_mean_reversion.reasons import EligibilityReasonCode


class RelationshipKind(str, Enum):
    SHARE_CLASS = "share_class"
    DUAL_LISTING = "dual_listing"
    SAME_ISSUER = "same_issuer"
    ETF_AND_NAV_PROXY = "etf_and_nav_proxy"
    INDEX_CONSTITUENT = "index_constituent"
    SECTOR_PEERS = "sector_peers"
    SUPPLY_CHAIN = "supply_chain"
    FUTURES_CALENDAR = "futures_calendar"
    OTHER_DECLARED = "other_declared"


@dataclass(frozen=True)
class UniverseValidationIssue:
    reason_code: EligibilityReasonCode
    message: str


@dataclass(frozen=True)
class EconomicCandidate:
    """One pair or basket the caller asserts is economically related."""

    candidate_id: str
    symbols: tuple[str, ...]
    relationship_kind: RelationshipKind | str | None
    relationship_rationale: str
    legs: Mapping[str, ArrayLike]
    holding_horizon: float
    timestamps: Sequence[datetime] | None = None
    as_of: datetime | int | None = None
    expected_gross_edge: float | None = None
    friction: FrictionInputs | None = None
    liquidity: Mapping[str, LiquiditySnapshot] | None = None
    event_flags: EventVetoFlags | None = None
    event_flags_by_symbol: Mapping[str, EventVetoFlags] | None = None

    @property
    def kind(self) -> str:
        return "pair" if len(self.symbols) == 2 else "basket"


@dataclass(frozen=True)
class EconomicCandidateUniverse:
    """Caller-supplied candidate groups. Not an LLM discovery engine."""

    name: str
    candidates: tuple[EconomicCandidate, ...]
    as_of: datetime | None = None
    notes: tuple[str, ...] = (
        "Universe membership is declared by the caller from economic structure.",
        "This object must not be populated by unconstrained LLM ticker generation.",
    )

    def get(self, candidate_id: str) -> EconomicCandidate:
        for candidate in self.candidates:
            if candidate.candidate_id == candidate_id:
                return candidate
        raise KeyError(candidate_id)


def validate_economic_candidate(candidate: EconomicCandidate) -> tuple[UniverseValidationIssue, ...]:
    """Return issues that block formation. Empty tuple means the identity is usable."""

    issues: list[UniverseValidationIssue] = []
    if not str(candidate.candidate_id or "").strip():
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
                "candidate_id is required",
            )
        )

    symbols = tuple(str(s).strip() for s in candidate.symbols)
    if len(symbols) < 2:
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.INSUFFICIENT_LEGS,
                "Mean-reversion eligibility requires at least two economically related legs",
            )
        )
    if any(not s for s in symbols):
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
                "Every symbol must be a non-empty identifier",
            )
        )
    if len(set(symbols)) != len(symbols):
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
                "Duplicate symbols are not a valid candidate group",
            )
        )

    kind = candidate.relationship_kind
    if kind is None or (isinstance(kind, str) and not kind.strip()):
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.MISSING_ECONOMIC_RELATIONSHIP,
                "Caller must declare an economic relationship; LLM discovery is not accepted",
            )
        )
    rationale = (candidate.relationship_rationale or "").strip()
    if not rationale:
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.MISSING_ECONOMIC_RELATIONSHIP,
                "relationship_rationale is required so the economic link is explicit",
            )
        )

    if candidate.holding_horizon is None or candidate.holding_horizon != candidate.holding_horizon:
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
                "holding_horizon must be a finite number of bars/periods",
            )
        )
    elif float(candidate.holding_horizon) <= 0:
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
                "holding_horizon must be strictly positive",
            )
        )

    missing_legs = [s for s in symbols if s and s not in candidate.legs]
    extra_legs = [s for s in candidate.legs if s not in set(symbols)]
    if missing_legs:
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.MISSING_OR_INVALID_DATA,
                f"Missing price legs for symbols: {missing_legs}",
            )
        )
    if extra_legs:
        issues.append(
            UniverseValidationIssue(
                EligibilityReasonCode.INVALID_CANDIDATE_UNIVERSE,
                f"legs contains symbols not listed on the candidate: {extra_legs}",
            )
        )

    return tuple(issues)
