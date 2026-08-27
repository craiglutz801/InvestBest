"""NorthstarAlpha Stage 3 — multi-speed trend + futures carry (research only).

This package does not place orders, call a broker, enable live shorting or
futures execution, or modify production strategy thresholds.
"""

from __future__ import annotations

from northstar_trend_carry.continuous import (
    ExecutableContractEconomics,
    ResearchContinuousSeries,
    build_research_continuous_series,
    executable_contract_state,
    representations_are_separate,
)
from northstar_trend_carry.friction import FrictionInputs, merge_roll_friction, research_edge_to_friction
from northstar_trend_carry.futures import (
    CarrySnapshot,
    ContractChain,
    FuturesChainProvider,
    FuturesContractObservation,
    InMemoryFuturesProvider,
    evaluate_carry,
    required_provider_fields,
)
from northstar_trend_carry.health import TrendHealthReport, evaluate_trend_health
from northstar_trend_carry.momentum import (
    AssetTrendSignal,
    CrossAssetTrendSnapshot,
    EnsembleConfig,
    HorizonSignal,
    evaluate_asset_trend,
    evaluate_cross_asset_trend,
)
from northstar_trend_carry.quality import QualityCode, QualityLevel
from northstar_trend_carry.robustness import (
    HorizonSelectionRefusal,
    PlateauReport,
    neighboring_parameter_plateau,
    refuse_performance_sweep_selection,
)
from northstar_trend_carry.schema import DEFAULT_HORIZONS, HorizonSpec, SCHEMA_VERSION
from northstar_trend_carry.series import PriceSeries

__version__ = "0.1.0"

__all__ = [
    "SCHEMA_VERSION",
    "DEFAULT_HORIZONS",
    "HorizonSpec",
    "EnsembleConfig",
    "PriceSeries",
    "HorizonSignal",
    "AssetTrendSignal",
    "CrossAssetTrendSnapshot",
    "evaluate_asset_trend",
    "evaluate_cross_asset_trend",
    "TrendHealthReport",
    "evaluate_trend_health",
    "PlateauReport",
    "HorizonSelectionRefusal",
    "neighboring_parameter_plateau",
    "refuse_performance_sweep_selection",
    "FuturesContractObservation",
    "ContractChain",
    "FuturesChainProvider",
    "InMemoryFuturesProvider",
    "CarrySnapshot",
    "evaluate_carry",
    "required_provider_fields",
    "ResearchContinuousSeries",
    "ExecutableContractEconomics",
    "build_research_continuous_series",
    "executable_contract_state",
    "representations_are_separate",
    "FrictionInputs",
    "merge_roll_friction",
    "research_edge_to_friction",
    "QualityCode",
    "QualityLevel",
    "__version__",
]
