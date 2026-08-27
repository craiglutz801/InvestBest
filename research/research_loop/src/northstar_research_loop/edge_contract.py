"""Versioned Edge Contract schema (Stage 6).

Every strategy family eventually carries one of these. The contract is
evidence and policy metadata, not an order. NorthstarAlpha should reason in
strategy × instrument × horizon, not just strategy × ticker.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

EDGE_CONTRACT_SCHEMA_VERSION = "1.0.0"

STRATEGY_FAMILIES = frozenset(
    {"mean_reversion", "trend", "futures_carry", "trend_carry", "other"}
)

CHAN_REVIEW_QUESTIONS: tuple[str, ...] = (
    "Why should this edge exist?",
    "Who/what creates the inefficiency?",
    "Why should it persist after costs and competition?",
    "What measurable property must be true?",
    "Is that property present out of sample?",
    "Is it stable through time?",
    "What is expected edge after realistic friction?",
    "What happens if costs are materially higher?",
    "What happens with delayed execution?",
    "Does it work around neighboring parameters?",
    "Does it work across multiple windows/regimes?",
    "How many variants were tested before this one won?",
    "Does multiple-testing-aware evaluation still support it?",
    "What does a structural break look like?",
    "What live metric stops new risk?",
    "What regime should hurt the strategy?",
    "What portfolio risk does it add?",
    "What existing risk does it diversify?",
    "How much capital survives uncertainty haircuts and hard risk limits?",
)


@dataclass(frozen=True)
class HoldingPeriod:
    amount: float
    unit: str  # trading_days | hours | bars
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"amount": self.amount, "unit": self.unit, "notes": self.notes}


@dataclass(frozen=True)
class ExpectedCosts:
    """Round-trip friction components. Aligns with Stage 1 FrictionInputs names."""

    commission: float = 0.0
    spread: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    borrow_fees: float = 0.0
    dividend_substitute: float = 0.0
    financing: float = 0.0
    futures_roll: float = 0.0
    other: float = 0.0
    currency: str = "return"

    def as_friction_dict(self) -> dict[str, float]:
        return {
            "commission": float(self.commission),
            "spread": float(self.spread),
            "slippage": float(self.slippage),
            "market_impact": float(self.market_impact),
            "borrow_fees": float(self.borrow_fees),
            "dividend_substitute": float(self.dividend_substitute),
            "financing": float(self.financing),
            "futures_roll": float(self.futures_roll),
            "other": float(self.other),
        }

    def total(self) -> float:
        return float(sum(self.as_friction_dict().values()))

    def to_dict(self) -> dict[str, Any]:
        payload = self.as_friction_dict()
        payload["currency"] = self.currency
        payload["total"] = self.total()
        return payload


@dataclass(frozen=True)
class NamedRule:
    code: str
    description: str
    metric: str | None = None
    threshold: float | None = None
    comparator: str | None = None  # lt | lte | gt | gte | eq | flag
    action: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EdgeContract:
    """Versioned contract required before research qualification.

    Diagnostics, eligibility, health, and promotion gates consume this
    metadata. Nothing here places an order or mutates a paper position.
    """

    contract_id: str
    name: str
    strategy_family: str
    mechanism: str
    required_statistical_property: str
    instruments: tuple[str, ...]
    horizon: str
    expected_holding_period: HoldingPeriod
    expected_costs: ExpectedCosts
    good_regimes: tuple[str, ...]
    bad_regimes: tuple[str, ...]
    formation_tests: tuple[NamedRule, ...]
    live_health_tests: tuple[NamedRule, ...]
    break_conditions: tuple[NamedRule, ...]
    retirement_rules: tuple[NamedRule, ...]
    throttle_rules: tuple[NamedRule, ...]
    schema_version: str = EDGE_CONTRACT_SCHEMA_VERSION
    notes: tuple[str, ...] = ()
    chan_review_answers: Mapping[str, str] = field(default_factory=dict)

    def identity_key(self) -> str:
        instruments = ",".join(self.instruments)
        return f"{self.strategy_family}|{instruments}|{self.horizon}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "contract_id": self.contract_id,
            "name": self.name,
            "strategy_family": self.strategy_family,
            "mechanism": self.mechanism,
            "required_statistical_property": self.required_statistical_property,
            "instruments": list(self.instruments),
            "horizon": self.horizon,
            "expected_holding_period": self.expected_holding_period.to_dict(),
            "expected_costs": self.expected_costs.to_dict(),
            "good_regimes": list(self.good_regimes),
            "bad_regimes": list(self.bad_regimes),
            "formation_tests": [rule.to_dict() for rule in self.formation_tests],
            "live_health_tests": [rule.to_dict() for rule in self.live_health_tests],
            "break_conditions": [rule.to_dict() for rule in self.break_conditions],
            "retirement_rules": [rule.to_dict() for rule in self.retirement_rules],
            "throttle_rules": [rule.to_dict() for rule in self.throttle_rules],
            "identity_key": self.identity_key(),
            "notes": list(self.notes),
            "chan_review_answers": dict(self.chan_review_answers),
            "chan_review_questions": list(CHAN_REVIEW_QUESTIONS),
        }


class EdgeContractError(ValueError):
    pass


def validate_edge_contract(contract: EdgeContract) -> tuple[str, ...]:
    """Return fail-closed reason codes. Empty tuple means structurally valid."""

    reasons: list[str] = []
    if not contract.contract_id.strip():
        reasons.append("edge.missing_contract_id")
    if not contract.name.strip():
        reasons.append("edge.missing_name")
    if contract.strategy_family not in STRATEGY_FAMILIES:
        reasons.append("edge.unknown_strategy_family")
    if not contract.mechanism.strip():
        reasons.append("edge.missing_mechanism")
    if not contract.required_statistical_property.strip():
        reasons.append("edge.missing_required_statistical_property")
    if not contract.instruments:
        reasons.append("edge.missing_instruments")
    if not contract.horizon.strip():
        reasons.append("edge.missing_horizon")
    if contract.expected_holding_period.amount <= 0:
        reasons.append("edge.invalid_holding_period")
    if contract.expected_costs.total() < 0:
        reasons.append("edge.negative_expected_costs")
    if not contract.formation_tests:
        reasons.append("edge.missing_formation_tests")
    if not contract.live_health_tests:
        reasons.append("edge.missing_live_health_tests")
    if not contract.break_conditions:
        reasons.append("edge.missing_break_conditions")
    if not contract.retirement_rules:
        reasons.append("edge.missing_retirement_rules")
    if contract.schema_version != EDGE_CONTRACT_SCHEMA_VERSION:
        reasons.append("edge.unsupported_schema_version")
    return tuple(reasons)


def require_valid_edge_contract(contract: EdgeContract) -> EdgeContract:
    reasons = validate_edge_contract(contract)
    if reasons:
        raise EdgeContractError("Invalid Edge Contract: " + ", ".join(reasons))
    return contract


def default_mean_reversion_contract(
    *,
    contract_id: str = "edge.mr.synthetic.v1",
    instruments: Sequence[str] = ("SYN_Y", "SYN_X"),
    horizon: str = "1d",
) -> EdgeContract:
    """Fixture-quality contract used by the synthetic harness; not a live strategy."""

    return EdgeContract(
        contract_id=contract_id,
        name="Synthetic residual mean-reversion (research fixture)",
        strategy_family="mean_reversion",
        mechanism=(
            "Economically related synthetic legs share a common stochastic trend; "
            "the residual is mean-reverting because the spread is an AR(1) by construction."
        ),
        required_statistical_property=(
            "CADF-rejectable residual stationarity with half-life compatible with the holding period "
            "and Edge-to-Friction Ratio above the research fragile band."
        ),
        instruments=tuple(instruments),
        horizon=horizon,
        expected_holding_period=HoldingPeriod(amount=5.0, unit="trading_days"),
        expected_costs=ExpectedCosts(commission=0.0002, spread=0.0004, slippage=0.0004),
        good_regimes=("range-bound", "stable-hedge-ratio"),
        bad_regimes=("structural-break", "one-leg-collapse", "volatility-shock"),
        formation_tests=(
            NamedRule("cadf_residual", "CADF residual stationary at 5%", "pvalue", 0.05, "lt"),
            NamedRule("half_life", "Half-life within 2–20 bars", "half_life", 20.0, "lte"),
            NamedRule("efr", "EFR at or above 2.5 research band", "efr", 2.5, "gte"),
        ),
        live_health_tests=(
            NamedRule("rolling_adf", "Rolling ADF remains usable", "adf_usable", 1.0, "eq"),
            NamedRule("hedge_drift", "Hedge-ratio drift below threshold", "hedge_cv", 0.35, "lt"),
        ),
        break_conditions=(
            NamedRule(
                "structural_break",
                "Stage 1/4 break_detected pauses new risk",
                "break_detected",
                1.0,
                "eq",
                "pause",
            ),
        ),
        retirement_rules=(
            NamedRule(
                "retire_on_repeated_breaks",
                "Repeated breaks or research_retire health state retire the candidate",
                "health_state",
                None,
                "eq",
                "retire",
            ),
        ),
        throttle_rules=(
            NamedRule(
                "advisory_multiplier",
                "Health may recommend 1.0 / reduced / 0.0 risk multiplier; RiskGovernor remains authoritative",
                "advisory_risk_multiplier",
                0.0,
                "gte",
                "throttle_advisory",
            ),
        ),
        notes=(
            "Research fixture only. Does not activate a production strategy.",
            "Sizing recommendations are advisory ceilings, never full-Kelly targets.",
        ),
        chan_review_answers={
            CHAN_REVIEW_QUESTIONS[0]: "Shared synthetic stochastic trend with AR(1) residual.",
            CHAN_REVIEW_QUESTIONS[3]: "Residual stationarity + compatible half-life + EFR cushion.",
        },
    )
