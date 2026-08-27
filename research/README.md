# Research

- **trend_carry/** — Stage 3 Chan/NorthstarAlpha multi-speed time-series trend ensemble, trend-health diagnostics, neighboring-parameter robustness (never picks a lookback), and provider-neutral futures carry / roll context. Research only; not wired to execution. See `docs/trend_carry.md`.
- **strategy_library/** — Store AI-generated strategy ideas and backtest results.
- **experiments/** — One-off notebooks and scripts for strategy discovery.

This folder is used by the AI Strategy Generator (Phase 3) to persist and rank strategy candidates. Stage 3 trend/carry must not be imported from the hourly paper-trading agent.
