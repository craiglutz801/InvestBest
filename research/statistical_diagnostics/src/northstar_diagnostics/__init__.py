"""NorthstarAlpha Stage 1 statistical diagnostics.

Research / strategy-eligibility evidence only.

This package must not:
- place orders or call broker / order APIs
- mutate simulated paper positions
- change production buy/sell behavior
- authorize live trading

Diagnostics never create trades. The RiskGovernor (when present) remains
authoritative for risk. Stage 1 does not wire these functions into the
hourly market agent or any execution path.
"""

from __future__ import annotations

__version__ = "0.1.0"

from northstar_diagnostics.adf import adf_stationarity
from northstar_diagnostics.cadf import cadf_cointegration
from northstar_diagnostics.efr import FrictionInputs, edge_to_friction_ratio
from northstar_diagnostics.half_life import mean_reversion_half_life
from northstar_diagnostics.hurst import hurst_diagnostic
from northstar_diagnostics.johansen import johansen_cointegration
from northstar_diagnostics.rolling import (
    rolling_parameter_stability,
    rolling_stationarity,
)
from northstar_diagnostics.schema import DiagnosticResult, QualityFlag, SampleWindow
from northstar_diagnostics.structural_break import (
    CUSUMOLSBreakDetector,
    ChowBreakDetector,
    StructuralBreakDetector,
    detect_structural_break,
)
from northstar_diagnostics.variance_ratio import variance_ratio_diagnostic

__all__ = [
    "CUSUMOLSBreakDetector",
    "ChowBreakDetector",
    "DiagnosticResult",
    "FrictionInputs",
    "QualityFlag",
    "SampleWindow",
    "StructuralBreakDetector",
    "adf_stationarity",
    "cadf_cointegration",
    "detect_structural_break",
    "edge_to_friction_ratio",
    "hurst_diagnostic",
    "johansen_cointegration",
    "mean_reversion_half_life",
    "rolling_parameter_stability",
    "rolling_stationarity",
    "variance_ratio_diagnostic",
    "__version__",
]
