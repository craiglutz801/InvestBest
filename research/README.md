# Research

- **statistical_diagnostics/** — Stage 1 Chan/NorthstarAlpha statistical diagnostics (ADF, CADF, Johansen, half-life, Hurst, variance ratio, rolling stability, structural-break contract, Edge-to-Friction Ratio). Research/eligibility evidence only; not wired to execution. See `docs/statistical_diagnostics.md`.
- **research_loop/** — Stage 6 bounded research-loop schemas, Stage 1–5 adapters, deterministic evaluation pipeline, append-only experiment registry, and synthetic morning harness. See `docs/CHAN_MORNING_TEST_PLAN.md` and `docs/CHAN_INTEGRATION_STACK.md`.
- **strategy_library/** — Store AI-generated strategy ideas and backtest results.
- **experiments/** — One-off notebooks and scripts for strategy discovery.

This folder is used by the AI Strategy Generator (Phase 3) to persist and rank strategy candidates. Stage 1 diagnostics and Stage 6 research-loop code must not be imported from the hourly paper-trading agent.

Morning suite (no broker credentials):

```bash
bash research/run_chan_research_tests.sh
```
