# Chan morning test plan (Craig / ChatGPT review)

**Date target:** 2026-08-27 morning  
**Scope:** NorthstarAlpha Chan Stages 1–6 research stack  
**Safety:** Research / paper only. No merge. No deploy. No broker keys. No live orders. No strategy activation.

This plan is executable against **synthetic/mock fixtures**. Anything that later needs real market or broker credentials is listed at the end and is **out of scope** for this morning pass.

---

## 0. What should already exist as draft PRs

Inspect open PRs first; do not merge them.

```bash
gh pr list --state open
```

Expected at start of overnight work (2026-08-27 ~04:00 UTC):

| Stage | Issue | Branch / PR | Role |
|---|---|---|---|
| Paper safety | #1 | `cursor/paper-only-safety-hardening-072f` (draft PR #2) | Execution/admission gates. Disjoint from research packages. Authoritative. |
| 1 Diagnostics | #3 | `cursor/chan-stage1-statistical-diagnostics-fd6c` (draft PR #4) | `research/statistical_diagnostics` (`northstar_diagnostics`) |
| 2 Mean-reversion eligibility | #5 | in flight overnight | Native eligibility engine; Stage 6 adapter wraps when importable |
| 3 Trend + futures carry | #6 | `cursor/chan-stage3-trend-carry-1042` (draft PR #10) | `research/trend_carry` (`northstar_trend_carry`). Stage 6 adapter wraps when installed. |
| 4 Edge health | #7 | in flight overnight | Native health states; Stage 6 adapter wraps when importable |
| 5 Anti-overfit + sizing | #8 | in flight overnight | Native DSR/PBO/Kelly ceiling; Stage 6 adapter wraps when importable |
| 6 Research loop + harness | #9 | `cursor/chan-stage6-research-loop-6fec` (this PR) | Schemas, adapters, pipeline, registry, synthetic harness, this doc |

Re-check before review: later-stage PRs may have landed after this file was written. Stage 6 discovery prints which native packages are importable.

---

## 1. One command (preferred)

From the repository root, no secrets required:

```bash
bash research/run_chan_research_tests.sh
```

This editable-installs Stage 1 + Stage 6, runs their pytest suites, then prints the synthetic harness JSON.

Equivalent explicit sequence:

```bash
python3 -m pip install -e "research/statistical_diagnostics[test]"
python3 -m pip install -e "research/research_loop[test]"
python3 -m pytest research/statistical_diagnostics research/research_loop -q
python3 -m northstar_research_loop
```

Optional Stage 1-only (PR #4):

```bash
python3 -m pytest research/statistical_diagnostics -q
```

If later Chan packages are on `PYTHONPATH`, re-run the same commands; Stage 6 discovery will switch those stages from `synthetic_fail_closed` to `native` without changing the harness scenario names.

Optional Stage 3 (draft PR #10) — only if `research/trend_carry` is on the checkout (it is **not** vendored into the Stage 6 stacked branch):

```bash
python3 -m pip install -e "research/trend_carry[test]"
python3 -m pytest research/trend_carry -q
```

The Stage 6 adapter already looks for import name `northstar_trend_carry`.

---

## 2. Expected outputs

### 2.1 Pytest

- `research/statistical_diagnostics`: Stage 1 diagnostics tests pass (50 tests on PR #4).
- `research/research_loop`: Stage 6 schema, safety, state-machine, adapter, pipeline, isolation, and harness tests pass (34 tests in this PR).

A green run ends with pytest `passed` summaries and:

```text
CHAN_RESEARCH_SUITE_OK
```

from the shell script.

### 2.2 Synthetic harness JSON (`python3 -m northstar_research_loop`)

Look for:

```text
CHAN_HARNESS_OK: good candidate passed; overfit/high-friction/broken/invalid failed closed
```

and JSON with:

| `outcomes[].name` | Expected `actual` status |
|---|---|
| `good_candidate` | `shadow-ready` (or `research-qualified`) |
| `overfit_candidate` | `rejected` |
| `high_friction_candidate` | `rejected` |
| `structurally_broken_candidate` | `paused` or `rejected` (fail-closed; not shadow-ready) |
| `statistically_invalid_candidate` | `rejected` |

Also required:

- `"all_passed": true`
- `"places_trade": false`
- `"promotes_to_live": false`
- `retained_winners >= 1` and `retained_failures >= 3` (failed experiments are kept)
- `discovered["1"].available == true` when Stage 1 is installed
- no candidate status equal to `live`

### 2.3 Isolation / safety smoke

Harness and pipeline results must keep:

- agent capability `can_place_trade`, `can_self_merge`, `can_self_deploy`, `can_self_promote_to_live` all false
- sizing `subordinate_to_risk_governor: true` and `fractional_kelly_ceiling < 1`
- health multiplier advisory only (`mutates_positions: false`)

---

## 3. What this morning pass does **not** do

- Merge any Chan PR.
- Deploy Vercel/Render/any host.
- Load Alpaca/IB/broker keys.
- Activate production buy/sell rules or `hourlyMarketAgent`.
- Self-promote a candidate from `shadow-ready` to paper/live.
- Call Twelve Data, Finnhub, Polygon, or OpenAI.

If `apps/web` paper-trading tests are wanted as an extra regression (unrelated to Chan research packages):

```bash
cd apps/web && npm test
```

That suite is the existing InvestBest paper MVP. It is not required to prove Stage 6.

---

## 4. Credentials required only **after** synthetic tests (do not use this morning)

| Later activity | Credential / env | Why it is not needed now |
|---|---|---|
| Live or paper broker orders | Alpaca / IB keys | Forbidden. Research loop cannot place trades. |
| Hosted paper agent | `DATABASE_URL`, `CRON_SECRET`, `TWELVE_DATA_API_KEY` | Execution path; disjoint paper-safety PR #2. |
| LLM research planner | `OPENAI_API_KEY` | Optional Karpathy loop in `apps/web`; not used by Stage 6. |
| Real futures chains (Stage 3 shadow) | Provider contract symbol, expiry, price, timestamp, volume/OI | Stage 3 issue specifies synthetic fixtures first. |
| Real borrow/shortability | Broker locate / HTB feed | Stage 2 eligibility uses caller-supplied interfaces. |

Synthetic CADF/EFR/health/robustness fixtures are sufficient to prove the loop’s fail-closed behavior.

---

## 5. Review checklist (ChatGPT / Craig)

1. Draft PRs only; stacking map in `docs/CHAN_INTEGRATION_STACK.md`.
2. Stage 6 did not copy Stage 1–5 engines; it adapts their contracts.
3. Good synthetic candidate can reach `shadow-ready`; bad ones cannot.
4. Failed experiments remain in the registry.
5. No `live` state, no broker imports, no `hourlyMarketAgent` coupling.
6. Paper-safety PR #2 file set remains disjoint; do not merge or deploy without explicit approval.

**Stop here.** Morning testing is the gate. Merge remains a separate explicit approval.
