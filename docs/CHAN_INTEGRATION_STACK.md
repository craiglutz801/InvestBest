# Chan integration stacking map

Overnight 2026-08-26 → morning 2026-08-27. **Draft PRs only. Do not merge. Do not deploy.**

This Stage 6 branch (`cursor/chan-stage6-research-loop-6fec`) is a **temporary
integration checkout**. It copies Stage 1–5 *research packages* onto the Stage 6
branch so adapters can call native APIs. It does **not** merge those PRs to `main`.

### Integration package heads (refreshed 2026-08-27)

| Stage | PR | Owning branch head | Copied onto Stage 6? |
|---|---|---|---|
| 1 | #4 | `d2b3218` Fail closed on misaligned CADF inputs and rank-deficient panels | **yes** (refreshed this pass) |
| 2 | #11 | `b0d3e7f` Add Stage 2 mean-reversion eligibility engine | yes (no newer head this pass) |
| 3 | #10 | `30cf67e` Add Stage 3 multi-speed trend and futures carry research module | yes (unchanged) |
| 4 | #13 | `f5db175` Add Stage 4 edge-health and structural-break monitoring | yes (no newer head this pass) |
| 5 | #14 | `0c687c9` Add Stage 5 anti-overfit promotion gates and Kelly ceiling | yes (unchanged) |
| 6 | #12 | this branch | — |

Stage 2 and Stage 4 did **not** publish dependency-update heads during this pass. Their packages stay at the commits above and are re-tested against copied Stage 1 `d2b3218` on this integration branch.

```text
main
 ├── PR #2   paper-only safety           cursor/paper-only-safety-hardening-072f
 │     disjoint execution/admission files; authoritative for live/paper gates
 │
 ├── PR #16  vNext architecture          cursor/northstaralpha-vnext-architecture-3dfb
 │     docs only: research plane stays unwired to hourlyMarketAgent
 │
 ├── PR #4   Stage 1 diagnostics         cursor/chan-stage1-statistical-diagnostics-fd6c
 │     head d2b3218  research/statistical_diagnostics  (northstar_diagnostics)
 │     ├── PR #11 Stage 2 eligibility    cursor/chan-stage2-mean-reversion-eligibility-7dee
 │     │     head b0d3e7f  research/mean_reversion_eligibility  (northstar_mean_reversion)
 │     │     evaluate_candidate(candidate, *, config=)
 │     └── PR #13 Stage 4 edge health    cursor/chan-stage4-edge-health-136d
 │           head f5db175  research/edge_health  (northstar_edge_health)
 │           HealthMonitor.evaluate(evidence, *, identity=)
 │
 ├── PR #10  Stage 3 trend/carry         cursor/chan-stage3-trend-carry-1042  (from main)
 │     head 30cf67e  research/trend_carry  (northstar_trend_carry)
 │     evaluate_asset_trend(series, config=None, *, as_of=)
 │     refuse_performance_sweep_selection(lookback_to_metric)
 │
 ├── PR #14  Stage 5 anti-overfit        cursor/chan-stage5-anti-overfit-promotion-add0  (from main)
 │     head 0c687c9  research/anti_overfit_promotion  (northstar_promotion)
 │     evaluate_promotion(evidence: PromotionEvidence, config=None)
 │     kelly_ceiling(returns, *, caps=)
 │
 └── PR #12  Stage 6 research loop       cursor/chan-stage6-research-loop-6fec
       stacked on Stage 1, with Stage 2–5 packages checked out for integration
       adapters call the typed APIs above (no getattr-name guessing)
```

## Native API map used by Stage 6

| Stage | Package | Function Stage 6 calls | Input type |
|---|---|---|---|
| 1 | `northstar_diagnostics` | `cadf_cointegration`, `edge_to_friction_ratio` | series + `FrictionInputs` |
| 2 | `northstar_mean_reversion` | `evaluate_candidate` | `EconomicCandidate`, `MeanReversionEligibilityConfig` |
| 3 | `northstar_trend_carry` | `evaluate_asset_trend`, `refuse_performance_sweep_selection` | `PriceSeries` |
| 4 | `northstar_edge_health` | `HealthMonitor.evaluate` | `MeanReversionEvidence` / `TrendEvidence`, `StrategyIdentity` |
| 5 | `northstar_promotion` | `evaluate_promotion`, `kelly_ceiling` | `PromotionEvidence`, returns + `RiskCapBundle` |

Sizing: health multiplier is applied once after `kelly_ceiling` (not also injected as `drawdown_throttle`). Missing `risk_governor_cap` returns a 0 ceiling; Stage 6 does not invent `0.2`.

A missing package is **not** a silent `synthetic_fail_closed` pass. The harness calls `require_native_stages()` and fails.

## File ownership

| Area | Owner PR |
|---|---|
| `apps/web` safety / `hourlyMarketAgent.ts` | #2 (untouched) |
| `research/statistical_diagnostics/**` | #4 |
| `research/mean_reversion_eligibility/**` | #11 |
| `research/trend_carry/**` | #10 |
| `research/edge_health/**` | #13 |
| `research/anti_overfit_promotion/**` | #14 |
| `research/research_loop/**`, `docs/CHAN_*.md`, `research/run_chan_research_tests.sh` | #12 |
| `docs/NORTHSTARALPHA_VNEXT_ARCHITECTURE.md` | #16 |

`research/README.md` is the only shared file; this integration branch keeps bullets for all six packages.

## Test command

```bash
bash research/run_chan_research_tests.sh
```

Observed after Stage 1 `d2b3218` refresh: **322 passed** (65+33+58+66+54+46) and `CHAN_HARNESS_OK` with all five `adapter_mode: native`.

See `docs/CHAN_MORNING_TEST_PLAN.md`.
