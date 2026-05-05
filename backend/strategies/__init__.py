"""
Strategy plug-ins. Each strategy implements:
- generate_signals() -> list of signals
- optional: backtest logic (or use BacktestService with strategy-specific logic)
"""
from backend.strategies.momentum import MomentumStrategy

__all__ = ["MomentumStrategy"]
