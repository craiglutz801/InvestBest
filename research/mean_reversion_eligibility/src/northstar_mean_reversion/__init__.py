"""NorthstarAlpha Stage 2 mean-reversion eligibility engine.

Research / shadow-only. This package must not:
- place orders or call broker / order APIs
- mutate simulated paper positions
- change production buy/sell behavior
- authorize live trading
- be imported by hourlyMarketAgent

Eligibility is candidate formation evidence. Residual z-score entry timing is a
separate shadow observation and cannot override failed formation gates.
"""

from __future__ import annotations

__version__ = "0.1.0"

from northstar_mean_reversion.engine import evaluate_candidate, evaluate_universe
from northstar_mean_reversion.events import EventVetoFlags
from northstar_mean_reversion.liquidity import LiquiditySnapshot
from northstar_mean_reversion.reasons import EligibilityReasonCode
from northstar_mean_reversion.shadow_signal import ShadowSignalResult, evaluate_shadow_entry
from northstar_mean_reversion.types import (
    EligibilityDecision,
    GateResult,
    MeanReversionEligibilityConfig,
)
from northstar_mean_reversion.universe import (
    EconomicCandidate,
    EconomicCandidateUniverse,
    RelationshipKind,
    validate_economic_candidate,
)

__all__ = [
    "EconomicCandidate",
    "EconomicCandidateUniverse",
    "EligibilityDecision",
    "EligibilityReasonCode",
    "EventVetoFlags",
    "GateResult",
    "LiquiditySnapshot",
    "MeanReversionEligibilityConfig",
    "RelationshipKind",
    "ShadowSignalResult",
    "evaluate_candidate",
    "evaluate_shadow_entry",
    "evaluate_universe",
    "validate_economic_candidate",
    "__version__",
]
