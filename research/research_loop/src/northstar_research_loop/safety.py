"""Hard safety boundary for the Stage 6 research loop.

The research agent may propose bounded experiments. It cannot place a trade,
bypass risk, self-merge, self-deploy, or self-promote a candidate to live.
RiskGovernor / paper-safety gates remain authoritative. This module never
imports broker SDKs or execution code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class ForbiddenAction(str, Enum):
    PLACE_TRADE = "place_trade"
    BYPASS_RISK = "bypass_risk"
    SELF_MERGE = "self_merge"
    SELF_DEPLOY = "self_deploy"
    SELF_PROMOTE_TO_LIVE = "self_promote_to_live"
    MODIFY_BROKER_SAFETY = "modify_broker_safety"
    OPTIMIZE_RECENT_PNL_ONLY = "optimize_recent_pnl_only"
    HIDE_FAILED_EXPERIMENT = "hide_failed_experiment"
    FREE_FORM_NEWS_TRADE = "free_form_news_trade"


ALLOWED_MUTATION_TARGETS: frozenset[str] = frozenset(
    {
        "strategy_config",
        "thresholds",
        "feature_set",
        "formation_window",
        "health_settings",
    }
)

FORBIDDEN_MUTATION_KEYS: frozenset[str] = frozenset(
    {
        "broker",
        "broker_api_key",
        "order",
        "live_trading",
        "execution_mode",
        "risk_governor",
        "riskgovernor",
        "self_merge",
        "deploy",
        "promote_to_live",
        "place_trade",
        "bypass_risk",
    }
)

LIVE_STATUS_NAME = "live"


class ForbiddenActionError(PermissionError):
    """Raised when a caller attempts a disallowed research-loop action."""


@dataclass(frozen=True)
class AgentCapability:
    """Explicit capability bitmap. Production wiring must not expand this."""

    can_propose_bounded_experiments: bool = True
    can_place_trade: bool = False
    can_bypass_risk: bool = False
    can_self_merge: bool = False
    can_self_deploy: bool = False
    can_self_promote_to_live: bool = False
    can_modify_broker_safety: bool = False
    can_hide_failed_experiments: bool = False

    def as_dict(self) -> dict[str, bool]:
        return {
            "can_propose_bounded_experiments": self.can_propose_bounded_experiments,
            "can_place_trade": self.can_place_trade,
            "can_bypass_risk": self.can_bypass_risk,
            "can_self_merge": self.can_self_merge,
            "can_self_deploy": self.can_self_deploy,
            "can_self_promote_to_live": self.can_self_promote_to_live,
            "can_modify_broker_safety": self.can_modify_broker_safety,
            "can_hide_failed_experiments": self.can_hide_failed_experiments,
        }


RESEARCH_AGENT_CAPABILITY = AgentCapability()


def assert_action_allowed(action: str | ForbiddenAction) -> None:
    """Fail closed: listed forbidden actions always raise."""

    key = action.value if isinstance(action, ForbiddenAction) else str(action)
    try:
        forbidden = ForbiddenAction(key)
    except ValueError:
        return
    raise ForbiddenActionError(
        f"Research loop forbids action '{forbidden.value}'. "
        "No trade, risk bypass, self-merge, self-deploy, or live promotion is permitted."
    )


def assert_not_live_status(status: str) -> None:
    if str(status).strip().lower() == LIVE_STATUS_NAME:
        raise ForbiddenActionError(
            "Research candidate status 'live' is not a legal state. "
            "Human approval is required for any later paper/live promotion outside this loop."
        )


def mutation_contains_forbidden_keys(payload: Mapping[str, object] | None) -> tuple[str, ...]:
    if not payload:
        return ()
    hits: list[str] = []
    for raw_key, value in payload.items():
        key = str(raw_key).strip().lower()
        if key in FORBIDDEN_MUTATION_KEYS or any(tok in key for tok in FORBIDDEN_MUTATION_KEYS):
            hits.append(str(raw_key))
        if isinstance(value, Mapping):
            hits.extend(mutation_contains_forbidden_keys(value))
    return tuple(hits)
