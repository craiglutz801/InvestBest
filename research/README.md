# Research

Chan / NorthstarAlpha research plane. **Not** the hourly paper agent. These
packages must not be imported from `hourlyMarketAgent` or legacy heuristic
scoring (`buyRules` / `sellRules`). See `docs/NORTHSTARALPHA_VNEXT_ARCHITECTURE.md`
(PR #16) and `docs/CHAN_INTEGRATION_STACK.md`.

- **statistical_diagnostics/** — Stage 1 (PR #4) `northstar_diagnostics`
- **mean_reversion_eligibility/** — Stage 2 (PR #11) `northstar_mean_reversion`
- **trend_carry/** — Stage 3 (PR #10) `northstar_trend_carry`
- **edge_health/** — Stage 4 (PR #13) `northstar_edge_health`
- **anti_overfit_promotion/** — Stage 5 (PR #14) `northstar_promotion`
- **research_loop/** — Stage 6 (PR #12) `northstar_research_loop` adapters + harness
- **strategy_library/** / **experiments/** — placeholder idea store (unused by Chan stages)

Morning suite (no broker credentials; does not merge or deploy):

```bash
bash research/run_chan_research_tests.sh
```
