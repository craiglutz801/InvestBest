"""NorthstarAlpha Stage 4 — edge health and structural-break monitoring.

Research / shadow only.

This package must not:
- place orders or call broker / order APIs
- mutate simulated paper positions
- change production buy/sell behavior
- authorize live trading
- bypass a RiskGovernor

Health snapshots may recommend a bounded risk multiplier (1.0 / reduced / 0).
That recommendation is advisory and subordinate to hard risk controls.
"""

from __future__ import annotations

__version__ = "0.4.0"

from northstar_edge_health.adapter import (
    extract_break_detected,
    mean_reversion_evidence_from_stage1,
)
from northstar_edge_health.advisory import (
    AdvisoryRiskRecommendation,
    NullRiskGovernor,
    RiskGovernorPort,
    apply_advisory,
    multiplier_for_state,
)
from northstar_edge_health.config import (
    AdvisoryRiskConfig,
    HealthConfig,
    HysteresisConfig,
    MeanReversionThresholds,
    TrendThresholds,
)
from northstar_edge_health.evaluator import HealthMonitor, family_identity
from northstar_edge_health.evidence import MeanReversionEvidence, TrendEvidence
from northstar_edge_health.schema import HealthSnapshot, StrategyIdentity
from northstar_edge_health.states import HealthState, ReasonCode

__all__ = [
    "AdvisoryRiskConfig",
    "AdvisoryRiskRecommendation",
    "HealthConfig",
    "HealthMonitor",
    "HealthSnapshot",
    "HealthState",
    "HysteresisConfig",
    "MeanReversionEvidence",
    "MeanReversionThresholds",
    "NullRiskGovernor",
    "ReasonCode",
    "RiskGovernorPort",
    "StrategyIdentity",
    "TrendEvidence",
    "TrendThresholds",
    "apply_advisory",
    "extract_break_detected",
    "family_identity",
    "mean_reversion_evidence_from_stage1",
    "multiplier_for_state",
    "__version__",
]
