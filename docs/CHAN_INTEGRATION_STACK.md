# Chan integration stacking map

Overnight 2026-08-26 → morning 2026-08-27. **Draft PRs only. Do not merge. Do not deploy.**

```text
main
 ├── PR #2  paper-only safety          cursor/paper-only-safety-hardening-072f
 │     disjoint execution/admission files; authoritative for live/paper gates
 │
 └── PR #4  Stage 1 diagnostics        cursor/chan-stage1-statistical-diagnostics-fd6c
       research/statistical_diagnostics  (northstar_diagnostics)
       │
       ├── Issue #5 Stage 2 eligibility     (stack on Stage 1 when the PR exists)
       ├── PR #10 Stage 3 trend/carry       cursor/chan-stage3-trend-carry-1042
       │     research/trend_carry (`northstar_trend_carry`) — disjoint package; Stage 6 discovers it
       ├── Issue #7 Stage 4 edge health     (prefer Stage 1 DiagnosticResult)
       ├── Issue #8 Stage 5 anti-overfit    (strategy-agnostic research eval)
       └── PR Stage 6 research loop         cursor/chan-stage6-research-loop-6fec
             stacked on Stage 1
             adapters wrap Stages 2–5 when importable (`northstar_trend_carry` is the Stage 3 name)
             otherwise explicit evidence + fail-closed
```

## File ownership (avoid overlap)

| Area | Owner |
|---|---|
| `apps/web/src/lib/safety/**`, `hourlyMarketAgent.ts`, settings/prisma execution mode | PR #2 |
| `research/statistical_diagnostics/**`, `docs/statistical_diagnostics.md` | PR #4 / Stage 1 |
| Mean-reversion eligibility package (not yet imported here by name) | Stage 2 |
| Trend/carry research package `research/trend_carry/**`, `docs/trend_carry.md` | PR #10 / Stage 3 |
| Health snapshot package | Stage 4 |
| DSR/PBO/Kelly-ceiling package | Stage 5 |
| `research/research_loop/**`, `docs/CHAN_MORNING_TEST_PLAN.md`, this file, `research/run_chan_research_tests.sh` | Stage 6 |

Stage 3 PR #10 also edits `research/README.md`. This Stage 6 branch edits the same file to point at the research loop. Morning rebase/stack should keep **both** bullets (`trend_carry/` and `research_loop/`). Do not drop either package.

## Rebase rule

When Stages 2–5 draft branches exist:

1. Fetch the branch.
2. If Stage 6 needs a native wrapper, add the real import name to
   `northstar_research_loop.adapters.discovery.STAGE_CANDIDATES`.
3. Map native decision objects in the corresponding `adapters/stageN.py`.
4. Do not duplicate formulas that already live in that PR.

Until those packages are importable, `discover_stage(n).adapter_mode == "synthetic_fail_closed"` and the pipeline requires explicit evidence records.

## Test command

```bash
bash research/run_chan_research_tests.sh
```

See `docs/CHAN_MORNING_TEST_PLAN.md` for expected JSON and the credentials that must **not** be used this morning.
