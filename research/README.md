# Research

Master product and architecture document: [`docs/NORTHSTARALPHA.md`](../docs/NORTHSTARALPHA.md).

- **statistical_diagnostics/** — Stage 1 Chan/NorthstarAlpha statistical diagnostics (ADF, CADF, Johansen, half-life, Hurst, variance ratio, rolling stability, structural-break contract, Edge-to-Friction Ratio). Research/eligibility evidence only; not wired to execution. See `docs/statistical_diagnostics.md`.
- **strategy_library/** — Store AI-generated strategy ideas and backtest results.
- **experiments/** — One-off notebooks and scripts for strategy discovery.

Chan Stages 2–6 (mean-reversion eligibility, trend/carry, edge health, anti-overfit promotion, bounded research loop) live on draft PRs and must not be imported from the hourly paper-trading agent. This folder is the isolated research plane, not a live signal path.
