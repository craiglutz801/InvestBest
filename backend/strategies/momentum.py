"""
Cross-sectional momentum: rank by lookback return, long top, short bottom.
"""
from __future__ import annotations
from typing import Any
import pandas as pd
import numpy as np


class MomentumStrategy:
    """Config-driven momentum. Expects config: lookback_days, top_pct, bottom_pct."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.lookback = int(self.config.get("lookback_days", 126))
        self.top_pct = float(self.config.get("top_pct", 0.1))
        self.bottom_pct = float(self.config.get("bottom_pct", 0.1))

    def generate_signals(self, prices: pd.DataFrame) -> pd.DataFrame:
        """
        prices: DataFrame with columns timestamp, symbol, close (or pivot with symbols as columns).
        Returns DataFrame with timestamp, symbol, signal (long/short/exit), confidence.
        """
        if "close" in prices.columns and "symbol" in prices.columns:
            pivot = prices.pivot(index="timestamp", columns="symbol", values="close")
        else:
            pivot = prices
        pivot = pivot.ffill().dropna(how="all")
        if len(pivot) < self.lookback + 1:
            return pd.DataFrame(columns=["timestamp", "symbol", "signal", "confidence"])
        momentum = pivot.shift(1) / pivot.shift(self.lookback + 1) - 1
        n = momentum.shape[1]
        top_n = max(1, int(n * self.top_pct))
        bottom_n = max(1, int(n * self.bottom_pct))
        rows = []
        for ts, row in momentum.iterrows():
            rank = row.rank(ascending=False)
            for sym in row.index:
                r = rank[sym]
                if r <= top_n:
                    rows.append({"timestamp": ts, "symbol": sym, "signal": "long", "confidence": 1.0 - (r - 1) / n})
                elif r > n - bottom_n:
                    rows.append({"timestamp": ts, "symbol": sym, "signal": "short", "confidence": (r - 1) / n})
                else:
                    rows.append({"timestamp": ts, "symbol": sym, "signal": "exit", "confidence": 0.0})
        return pd.DataFrame(rows)
