"""
Backtest service: runs a strategy over historical data and returns metrics.
Uses in-memory or DB price data; falls back to synthetic data for demo.
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Any
import pandas as pd
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Strategy, Price


class BacktestService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def run(
        self,
        strategy: Strategy,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Run backtest for strategy. Returns sharpe, max_drawdown, win_rate, annual_return."""
        # Default window: last 1 year of data if available
        end = end_date or datetime.utcnow().strftime("%Y-%m-%d")
        start = start_date or (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")

        # Try to load prices from DB for a small universe (e.g. SPY or first available)
        prices_df = await self._load_prices(start, end)
        if prices_df is None or prices_df.empty:
            # Synthetic data for demo when no DB data
            prices_df = self._synthetic_prices(start, end)

        # Dispatch to strategy module if present
        module_path = strategy.module_path or "backend.strategies.momentum"
        try:
            if "momentum" in module_path:
                returns_series = self._run_momentum(prices_df, strategy.config_json)
            else:
                returns_series = self._run_momentum(prices_df, strategy.config_json)
        except Exception as e:
            return {
                "error": str(e),
                "sharpe": None,
                "max_drawdown": None,
                "win_rate": None,
                "annual_return": None,
            }

        if returns_series is None or returns_series.empty:
            return {
                "sharpe": None,
                "max_drawdown": None,
                "win_rate": None,
                "annual_return": None,
                "message": "No returns generated",
            }

        metrics = self._compute_metrics(returns_series)
        metrics["start"] = start
        metrics["end"] = end
        return metrics

    async def _load_prices(self, start: str, end: str) -> pd.DataFrame | None:
        from datetime import datetime as dt
        start_dt = dt.fromisoformat(start.replace("Z", "") + "T00:00:00")
        end_dt = dt.fromisoformat(end.replace("Z", "") + "T23:59:59")
        result = await self.session.execute(
            select(Price).where(
                Price.timestamp >= start_dt,
                Price.timestamp <= end_dt,
            ).order_by(Price.symbol, Price.timestamp)
        )
        rows = result.scalars().all()
        if not rows:
            return None
        data = [
            {
                "symbol": r.symbol,
                "timestamp": r.timestamp,
                "open": r.open,
                "high": r.high,
                "low": r.low,
                "close": r.close,
                "volume": r.volume,
            }
            for r in rows
        ]
        df = pd.DataFrame(data)
        if df.empty:
            return None
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df

    def _synthetic_prices(self, start: str, end: str, symbols: list[str] | None = None) -> pd.DataFrame:
        """Generate synthetic OHLCV for backtest demo."""
        symbols = symbols or ["SPY", "QQQ", "IWM"]
        dates = pd.date_range(start=start, end=end, freq="B")
        np.random.seed(42)
        rows = []
        for sym in symbols:
            price = 100.0
            for d in dates:
                ret = np.random.randn() * 0.01
                price = price * (1 + ret)
                rows.append({
                    "symbol": sym,
                    "timestamp": d,
                    "open": price / (1 + ret),
                    "high": price * 1.005,
                    "low": price * 0.995,
                    "close": price,
                    "volume": 1e6,
                })
        return pd.DataFrame(rows)

    def _run_momentum(self, prices_df: pd.DataFrame, config_json: str | None) -> pd.Series | None:
        """Simple momentum: rank by past return, long top decile, short bottom. Returns daily strategy returns."""
        config = json.loads(config_json) if config_json else {}
        lookback = config.get("lookback_days", 126)  # ~6 months
        top_n = config.get("top_n", 1)  # top 1 symbol when we have 3

        pivot = prices_df.pivot(index="timestamp", columns="symbol", values="close")
        pivot = pivot.ffill().dropna(how="all")
        if pivot.shape[1] < 2 or len(pivot) < lookback:
            return None
        ret = pivot.pct_change()
        momentum = pivot.shift(1) / pivot.shift(lookback + 1) - 1
        # Long top performer, short bottom (if we have enough symbols)
        rank = momentum.rank(axis=1, ascending=False)
        top = rank <= top_n
        bottom = rank > rank.max(axis=1) - top_n
        daily_long = (ret * top).sum(axis=1) / top.sum(axis=1).replace(0, np.nan)
        daily_short = (ret * bottom).sum(axis=1) / bottom.sum(axis=1).replace(0, np.nan)
        strategy_ret = daily_long.fillna(0) - daily_short.fillna(0)
        return strategy_ret.dropna()

    def _compute_metrics(self, returns: pd.Series) -> dict[str, Any]:
        if returns.empty:
            return {"sharpe": None, "max_drawdown": None, "win_rate": None, "annual_return": None}
        rf = 0.0
        excess = returns - rf
        sharpe = np.sqrt(252) * excess.mean() / excess.std() if excess.std() > 0 else None
        cum = (1 + returns).cumprod()
        run_max = cum.cummax()
        drawdown = (cum - run_max) / run_max
        max_dd = drawdown.min()
        win_rate = (returns > 0).mean()
        ann_ret = (1 + returns.mean()) ** 252 - 1 if returns.mean() is not np.nan else None
        return {
            "sharpe": round(float(sharpe), 4) if sharpe is not None else None,
            "max_drawdown": round(float(max_dd), 4) if max_dd is not None else None,
            "win_rate": round(float(win_rate), 4),
            "annual_return": round(float(ann_ret), 4) if ann_ret is not None else None,
        }
