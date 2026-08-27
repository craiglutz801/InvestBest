"""NorthstarAlpha Stage 5 anti-overfit promotion + conservative sizing.

Research / falsification evidence only.

This package must not:
- place orders or call broker / order APIs
- mutate simulated paper positions
- change production buy/sell behavior
- authorize live trading
- self-promote a candidate to paper or live
- treat full Kelly as a target
"""

from __future__ import annotations

__version__ = "0.1.0"

from northstar_promotion.concentration import ConcentrationReport, trade_pnl_concentration
from northstar_promotion.dsr import (
    DSRResult,
    cross_sectional_sharpe_variance,
    deflated_sharpe_ratio,
    expected_max_sharpe,
)
from northstar_promotion.holdout import HoldoutAudit, HoldoutContract, audit_holdout, seal_holdout
from northstar_promotion.kelly import KellyCeilingResult, RiskCapBundle, kelly_ceiling
from northstar_promotion.neighborhood import ParameterPoint, PlateauReport, evaluate_plateau
from northstar_promotion.pbo import PBOResult, probability_of_backtest_overfitting
from northstar_promotion.promotion import (
    PromotionConfig,
    PromotionDecision,
    PromotionEvidence,
    PromotionVerdict,
    evaluate_promotion,
)
from northstar_promotion.quality import QualityFlag, QualityLevel, ReasonCode
from northstar_promotion.regimes import RegimeSliceReport, evaluate_regime_slices
from northstar_promotion.registry import ExperimentRegistry, TrialRecord
from northstar_promotion.schema import TimeWindow
from northstar_promotion.splits import (
    WalkForwardReport,
    WalkForwardSplit,
    evaluate_walk_forward,
    formation_windows,
    walk_forward_splits,
)
from northstar_promotion.stress import (
    StressReport,
    cost_stress,
    execution_delay_stress,
)

__all__ = [
    "ConcentrationReport",
    "DSRResult",
    "ExperimentRegistry",
    "HoldoutAudit",
    "HoldoutContract",
    "KellyCeilingResult",
    "PBOResult",
    "ParameterPoint",
    "PlateauReport",
    "PromotionConfig",
    "PromotionDecision",
    "PromotionEvidence",
    "PromotionVerdict",
    "QualityFlag",
    "QualityLevel",
    "ReasonCode",
    "RegimeSliceReport",
    "RiskCapBundle",
    "StressReport",
    "TimeWindow",
    "TrialRecord",
    "WalkForwardReport",
    "WalkForwardSplit",
    "audit_holdout",
    "cost_stress",
    "cross_sectional_sharpe_variance",
    "deflated_sharpe_ratio",
    "evaluate_plateau",
    "evaluate_promotion",
    "evaluate_regime_slices",
    "evaluate_walk_forward",
    "execution_delay_stress",
    "expected_max_sharpe",
    "formation_windows",
    "kelly_ceiling",
    "probability_of_backtest_overfitting",
    "seal_holdout",
    "trade_pnl_concentration",
    "walk_forward_splits",
    "__version__",
]
