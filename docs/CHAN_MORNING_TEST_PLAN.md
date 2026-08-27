# Chan morning test plan (Craig / ChatGPT review)

**Date target:** 2026-08-27 morning  
**Scope:** NorthstarAlpha Chan Stages 1–6 **native** integration  
**Safety:** Research / paper only. No merge. No deploy. No broker keys. No live orders. No strategy activation.

This plan is executable against **synthetic fixtures fed into native Stage 1–5 APIs**. Anything that later needs real market or broker credentials is listed at the end and is **out of scope** for this morning pass.

> **This integration checkout is NOT the merge path.**  
> PR #12 copies Stage 1–5 *research packages* onto `cursor/chan-stage6-research-loop-6fec` so the morning harness can call typed public APIs. Owning PRs remain #4 / #11 / #10 / #13 / #14. Do **not** merge this checkout to `main`. After review, keep Stage 2–5 ownership on those draft PRs.

---

## 0. Draft PRs (do not merge)

```bash
gh pr list --state open
```

| Stage | Issue | PR | Branch | Package |
|---|---|---|---|---|
| Paper safety | #1 | #2 | `cursor/paper-only-safety-hardening-072f` | `apps/web` safety (disjoint) |
| vNext architecture | — | #16 | `cursor/northstaralpha-vnext-architecture-3dfb` | docs only |
| 1 Diagnostics | #3 | #4 | `cursor/chan-stage1-statistical-diagnostics-fd6c` @ `d2b3218` | `northstar_diagnostics` |
| 2 Mean-reversion | #5 | #11 | `cursor/chan-stage2-mean-reversion-eligibility-7dee` @ `55e2af7` | `northstar_mean_reversion` |
| 3 Trend + carry | #6 | #10 | `cursor/chan-stage3-trend-carry-1042` @ **`40a41e4`** | `northstar_trend_carry` |
| 4 Edge health | #7 | #13 | `cursor/chan-stage4-edge-health-136d` @ `75146a5` | `northstar_edge_health` |
| 5 Anti-overfit | #8 | #14 | `cursor/chan-stage5-anti-overfit-promotion-add0` @ **`4ac1fa0`** | `northstar_promotion` |
| 6 Research loop | #9 | #12 | `cursor/chan-stage6-research-loop-6fec` | `northstar_research_loop` |

Heads copied onto this integration branch (2026-08-27 Stage 3/5 freshness pass): Stage 1 `d2b3218`, Stage 2 `55e2af7`, Stage 3 **`40a41e4`**, Stage 4 `75146a5`, Stage 5 **`4ac1fa0`**. That is a temporary assembly, **not** a merge to `main`.

vNext constraint (PR #16): this research plane stays unwired to `hourlyMarketAgent` / legacy heuristic scoring.

---

## 0.1 Dependency / stacking map

```text
main
 ├── PR #2   paper-only safety           (disjoint; do not touch)
 ├── PR #16  vNext architecture          research plane unwired to hourlyMarketAgent
 ├── PR #4   Stage 1  d2b3218            northstar_diagnostics
 │     ├── PR #11 Stage 2  55e2af7       northstar_mean_reversion
 │     └── PR #13 Stage 4  75146a5       northstar_edge_health
 ├── PR #10  Stage 3  40a41e4            northstar_trend_carry
 │           curve gap = carry; futures_roll = execution friction only
 ├── PR #14  Stage 5  4ac1fa0            northstar_promotion
 │           DSR N>1 requires trial_sharpes or sharpe_trials_variance
 └── PR #12  Stage 6  (this checkout)    copies the five packages above
                                         NOT the merge path to main
```

See `docs/CHAN_INTEGRATION_STACK.md` for the same map with native call signatures.

---

## 1. One command (preferred)

From the repository root of PR #12, no secrets required:

```bash
bash research/run_chan_research_tests.sh
```

This editable-installs Stages 1–6, runs each package’s pytest suite **separately** (avoids colliding `test_isolation.py` names), then prints the synthetic harness JSON.

Equivalent short sequence:

```bash
python3 -m pip install -e "research/statistical_diagnostics[test]" \
  -e "research/mean_reversion_eligibility[test]" \
  -e "research/trend_carry[test]" \
  -e "research/edge_health[test]" \
  -e "research/anti_overfit_promotion[test]" \
  -e "research/research_loop[test]"

python3 -m pytest research/statistical_diagnostics
python3 -m pytest research/mean_reversion_eligibility
python3 -m pytest research/trend_carry
python3 -m pytest research/edge_health
python3 -m pytest research/anti_overfit_promotion
python3 -m pytest research/research_loop

python3 -m northstar_research_loop
```

Do **not** run all six pytest directories in one invocation; several packages ship `tests/test_isolation.py`.

---

## 2. Expected outputs

### 2.1 Pytest

Each focused suite should pass. Stage 6 includes contract tests that fail if Stage 2–5 public functions are renamed (for example Stage 5 must export `evaluate_promotion` and `kelly_ceiling`, not `evaluate_robustness`). Stage 5 DSR must require `trial_sharpes` or `sharpe_trials_variance` when N>1; Stage 3 `merge_roll_friction` must not treat the listed-contract curve gap as execution friction.

Observed on this integration branch (2026-08-27, heads `d2b3218` / `55e2af7` / `40a41e4` / `75146a5` / `4ac1fa0`):

| Suite | Passed |
|---|---|
| Stage 1 `research/statistical_diagnostics` | 65 |
| Stage 2 `research/mean_reversion_eligibility` | 39 |
| Stage 3 `research/trend_carry` | 67 |
| Stage 4 `research/edge_health` | 69 |
| Stage 5 `research/anti_overfit_promotion` | 60 |
| Stage 6 `research/research_loop` | 49 |
| **Total** | **349** |

A green script ends with:

```text
CHAN_RESEARCH_SUITE_OK
```

### 2.2 Synthetic harness JSON (`python3 -m northstar_research_loop`)

Look for:

```text
CHAN_HARNESS_OK: native Stages 1–5 used; good candidate passed; overfit/high-friction/broken/invalid failed closed
```

| `outcomes[].name` | Expected `actual` |
|---|---|
| `good_candidate` | `shadow-ready` (or `research-qualified`) |
| `overfit_candidate` | `rejected` |
| `high_friction_candidate` | `rejected` |
| `structurally_broken_candidate` | `paused` (or fail-closed `rejected` / `retired`) |
| `statistically_invalid_candidate` | `rejected` |

Also required:

- `"all_passed": true`
- `"native_required": true`
- `"places_trade": false`
- `"promotes_to_live": false`
- every `discovered["1"…"5"].adapter_mode == "native"`
- no `synthetic_fail_closed`
- every outcome `native_sources` maps:
  - `diagnostics` → `northstar_diagnostics`
  - `eligibility` → `northstar_mean_reversion`
  - `trend_context` → `northstar_trend_carry`
  - `health` → `northstar_edge_health`
  - `robustness` / `sizing` → `northstar_promotion`

If any required package is missing, the harness exits 1 with `CHAN_HARNESS_FAIL` and does **not** silently use `synthetic_fail_closed`.

Observed harness on this branch: `CHAN_HARNESS_OK`, all five `adapter_mode` values `native`, `good_candidate` → `shadow-ready`, `overfit_candidate` → `rejected` (`ISOLATED_OPTIMUM`, `HOLDOUT_CONTAMINATION`), `high_friction_candidate` → `rejected` (`insufficient_efr`), `structurally_broken_candidate` → `paused` (`mr.structural_break` from Stage 4), `statistically_invalid_candidate` → `rejected` (Stage 2), `places_trade: false`, `promotes_to_live: false`, 1 retained winner, 4 retained failures.

---

## 3. Native APIs the harness actually calls

| Stage | Call |
|---|---|
| 1 | `cadf_cointegration(y, x)`, `edge_to_friction_ratio(edge, FrictionInputs)` |
| 2 | `evaluate_candidate(EconomicCandidate, *, config=MeanReversionEligibilityConfig)` |
| 3 | `evaluate_asset_trend(PriceSeries)`, `refuse_performance_sweep_selection({lookback: metric})`. Package contract: curve/basis gap is carry; `futures_roll` is execution friction only. |
| 4 | `HealthMonitor.evaluate(MeanReversionEvidence, *, identity=StrategyIdentity)` |
| 5 | `evaluate_promotion(PromotionEvidence, config=PromotionConfig)`, `kelly_ceiling(returns, *, caps=RiskCapBundle)` with explicit harness `risk_governor_cap`; health multiplier applied once. DSR is fed registry `trial_sharpes` from experiment return paths (no invented `sharpe_trials_variance`). |

---

## 4. What this morning pass does **not** do

- Merge any Chan PR to `main` (this checkout is **not** the merge path).
- Deploy Vercel/Render/any host (ignore Vercel preview noise on this research-only PR).
- Load Alpaca/IB/broker keys.
- Activate production buy/sell rules or `hourlyMarketAgent`.
- Self-promote a candidate from `shadow-ready` to paper/live.
- Call Twelve Data, Finnhub, Polygon, or OpenAI.

Optional extra (unrelated to Chan research packages):

```bash
cd apps/web && npm test
```

---

## 5. Credentials required only **after** synthetic tests (do not use this morning)

| Later activity | Credential | Why not needed now |
|---|---|---|
| Broker orders | Alpaca / IB keys | Forbidden. Research loop cannot place trades. |
| Hosted paper agent | `DATABASE_URL`, `CRON_SECRET`, `TWELVE_DATA_API_KEY` | Execution path; PR #2. |
| LLM planner | `OPENAI_API_KEY` | Not used by Stage 6. |
| Real futures chains | Provider contract fields | Stage 3 fixtures are synthetic. |

---

## 6. Review checklist

1. Draft PRs only; stacking map in `docs/CHAN_INTEGRATION_STACK.md`. This checkout is **not** the merge path.
2. Stage 6 calls native Stage 2–5 typed APIs (no `getattr` name guessing as the primary path). All adapters `native`; no `synthetic_fail_closed`.
3. Stage 5 DSR uses real trial-Sharpe dispersion from the registry; N>1 without it fails closed.
4. Good synthetic candidate can reach `shadow-ready`; bad ones cannot.
5. Failed experiments remain in the Stage 6 registry.
6. No `live` state; no broker imports; no `hourlyMarketAgent` coupling.
7. Paper-safety PR #2 and vNext PR #16 remain disjoint. Do not merge or deploy without explicit approval.

**Stop here.** Morning testing is the gate. Merge remains a separate explicit approval.
