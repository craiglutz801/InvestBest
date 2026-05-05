# InvestBest — Cursor Task Breakdown for Karpathy Loop
**Version:** 1.0  
**Date:** 2026-04-20

This file is the implementation companion to `InvestBest_Karpathy_Loop_Addendum.md`.

Its purpose is to give Cursor a concrete build plan with:
- exact phases
- files to create or update
- database migrations
- API routes
- background jobs
- UI pages
- acceptance criteria

---

## 1) Build goal

Add a safe Karpathy-style continuous improvement loop to InvestBest.

This means Cursor must build:
1. strategy versioning
2. experiment tracking
3. evaluation and backtesting hooks
4. promotion gates
5. shadow mode
6. research dashboard
7. bounded AI agent workflow for proposing config changes

Do not start by building autonomous code-editing agents.
Start with versioned configs and controlled experiments.

---

## 2) High-level implementation phases

### Phase 1 — Strategy versioning foundation
Build the versioned strategy system first.

### Phase 2 — Experiment registry and evaluation plumbing
Create experiments, run evaluations, and store results.

### Phase 3 — Research loop orchestration
Add the slower agent-driven improvement jobs.

### Phase 4 — Promotion gate and shadow mode
Safely compare challenger strategies to the baseline.

### Phase 5 — Research UI
Make the entire loop visible and auditable.

---

## 3) Recommended repo structure

If the current repo already has a web app and optional ML service, extend it like this:

```text
investbest/
  apps/
    web/
      src/
        app/
          research/
          strategies/
          shadow/
          api/
        components/
          research/
          strategies/
          shadow/
        lib/
          research/
          strategy/
          promotion/
          evaluation/
          agents/
          backtests/
          jobs/
      prisma/
    ml-service/
      app/
      training/
      backtests/
      evaluation/
  docs/
    INVESTBEST_KARPATHY_LOOP_ADDENDUM.md
    INVESTBEST_KARPATHY_TASK_BREAKDOWN.md
```

---

## 4) Files Cursor should create

### Strategy versioning
Create:

- `apps/web/src/lib/strategy/types.ts`
- `apps/web/src/lib/strategy/schema.ts`
- `apps/web/src/lib/strategy/defaultStrategy.ts`
- `apps/web/src/lib/strategy/registry.ts`
- `apps/web/src/lib/strategy/diff.ts`
- `apps/web/src/lib/strategy/cloneStrategy.ts`

### Experiment system
Create:

- `apps/web/src/lib/research/types.ts`
- `apps/web/src/lib/research/experimentRegistry.ts`
- `apps/web/src/lib/research/createExperiment.ts`
- `apps/web/src/lib/research/evaluateExperiment.ts`
- `apps/web/src/lib/research/verdict.ts`
- `apps/web/src/lib/research/logResearchNote.ts`

### Evaluation / scoring
Create:

- `apps/web/src/lib/evaluation/compositeScore.ts`
- `apps/web/src/lib/evaluation/metricThresholds.ts`
- `apps/web/src/lib/evaluation/compareBaselineVsChallenger.ts`
- `apps/web/src/lib/evaluation/regimeSlices.ts`
- `apps/web/src/lib/evaluation/antiOverfitChecks.ts`

### Promotion gate
Create:

- `apps/web/src/lib/promotion/promotionGate.ts`
- `apps/web/src/lib/promotion/checkPromotionEligibility.ts`
- `apps/web/src/lib/promotion/promoteStrategy.ts`

### Agents
Create:

- `apps/web/src/lib/agents/researchPlanner.ts`
- `apps/web/src/lib/agents/criticAgent.ts`
- `apps/web/src/lib/agents/narratorAgent.ts`
- `apps/web/src/lib/agents/generateStrategyVariants.ts`

### Jobs
Create:

- `apps/web/src/lib/jobs/runResearchLoop.ts`
- `apps/web/src/lib/jobs/runExperiment.ts`
- `apps/web/src/lib/jobs/runShadowComparison.ts`

### UI pages
Create:

- `apps/web/src/app/research/page.tsx`
- `apps/web/src/app/research/[id]/page.tsx`
- `apps/web/src/app/strategies/page.tsx`
- `apps/web/src/app/strategies/[id]/page.tsx`
- `apps/web/src/app/shadow/page.tsx`

### UI components
Create:

- `apps/web/src/components/research/ResearchDashboard.tsx`
- `apps/web/src/components/research/ExperimentTable.tsx`
- `apps/web/src/components/research/ExperimentSummaryCard.tsx`
- `apps/web/src/components/research/MetricDeltaTable.tsx`
- `apps/web/src/components/strategies/StrategyVersionTable.tsx`
- `apps/web/src/components/strategies/StrategyDiffViewer.tsx`
- `apps/web/src/components/shadow/ShadowComparisonChart.tsx`

---

## 5) Files Cursor should update

Update these existing areas if they already exist:

- current trading loop / agent orchestrator
- settings schema
- database schema
- dashboard navigation
- background scheduler config
- model scoring integration
- existing decision run models

### Specific updates
#### Trading loop
Update current trading loop so each run records:
- strategyVersionId
- experimentContextId if applicable
- baseline or challenger label
- shadowMode flag

#### Settings
Add settings for:
- active baseline strategy
- research loop enabled
- research cadence
- auto-promotion enabled or disabled
- shadow probation days
- experiment budget per day

---

## 6) Prisma schema changes

Add these models.

### `StrategyVersion`
Fields:
- id
- name
- parentStrategyVersionId
- versionTag
- status
- configJson
- createdBy
- createdAt
- promotedAt
- notes

Relations:
- parent
- children
- experiments

### `Experiment`
Fields:
- id
- strategyVersionId
- baselineStrategyVersionId
- hypothesis
- mutationType
- changedFieldsJson
- evaluationWindowStart
- evaluationWindowEnd
- evaluationMode
- resultMetricsJson
- verdict
- verdictReason
- createdAt
- completedAt

### `ExperimentRun`
Fields:
- id
- experimentId
- runType
- status
- startedAt
- finishedAt
- logsJson
- artifactsJson

### `PromotionDecision`
Fields:
- id
- candidateStrategyVersionId
- baselineStrategyVersionId
- approved
- approvedBy
- decisionReason
- metricsDeltaJson
- createdAt

### `ResearchNote`
Fields:
- id
- experimentId
- agentRole
- noteType
- content
- createdAt

### Optional `ShadowRun`
Fields:
- id
- baselineStrategyVersionId
- challengerStrategyVersionId
- runTimestamp
- baselineSummaryJson
- challengerSummaryJson
- deltaJson
- createdAt

### Important relation update
Add `strategyVersionId` to:
- decision runs
- paper trades
- portfolio snapshots

This is required so every outcome can be tied to the exact strategy version that generated it.

---

## 7) Database migration steps

Cursor should generate migrations in this order:

### Migration 1
Add:
- StrategyVersion
- Experiment
- ExperimentRun
- PromotionDecision
- ResearchNote

### Migration 2
Add foreign keys:
- strategyVersionId on decision runs
- strategyVersionId on paper trades
- strategyVersionId on portfolio snapshots

### Migration 3
Add optional:
- ShadowRun
- research settings fields

### Migration 4
Backfill:
- existing runs/trades/snapshots to the initial baseline strategy version

---

## 8) Strategy config schema

Create a Zod schema for strategy configs.

### Minimum fields
- strategy name
- buy score weights
- sell score weights
- buy threshold
- sell risk threshold
- stop loss pct
- take profit pct
- cooldown hours
- cash reserve pct
- max position pct
- max new positions per run
- segment caps
- search profile refs
- feature toggles
- evaluation metadata

### Requirements
- schema validation must run on every strategy create or clone
- invalid strategies must not be saved
- config diffs must be human-readable

---

## 9) APIs Cursor should build

### Strategy routes
- `GET /api/strategies`
- `GET /api/strategies/:id`
- `POST /api/strategies`
- `POST /api/strategies/:id/clone`
- `POST /api/strategies/:id/promote`

### Experiment routes
- `GET /api/experiments`
- `GET /api/experiments/:id`
- `POST /api/experiments`
- `POST /api/experiments/:id/run`
- `GET /api/experiments/:id/results`

### Research loop routes
- `POST /api/internal/research/run`
- `POST /api/internal/research/generate-variants`
- `POST /api/internal/research/evaluate`
- `POST /api/internal/research/promote`

### Shadow routes
- `GET /api/shadow/current`
- `GET /api/shadow/comparison`

### Response requirements
All routes must:
- be typed
- validate input with Zod
- return structured metric payloads
- include strategy ids and version tags where applicable

---

## 10) Background jobs Cursor should build

### Job 1 — hourly trading operator
Purpose:
- continue the main paper trading loop

Needs to:
- use active baseline strategy
- optionally record challenger shadow results too

### Job 2 — research planner
Cadence:
- every 6 hours or daily

Steps:
1. inspect latest results
2. identify a weak area
3. generate one or more bounded variant ideas
4. create experiment records

### Job 3 — experiment runner
Steps:
1. load experiment
2. clone baseline strategy config
3. apply mutation
4. validate config
5. run evaluation suite
6. store metrics
7. request verdict

### Job 4 — promotion evaluator
Steps:
1. compare challenger vs baseline
2. run anti-overfit checks
3. apply promotion gate
4. approve or reject
5. store decision

### Job 5 — shadow comparison job
Steps:
1. run challenger alongside baseline
2. compare picks and sell timing
3. store deltas
4. update shadow dashboard

---

## 11) Evaluation engine requirements

Cursor must implement a deterministic evaluation engine.

### Inputs
- baseline strategy config
- challenger strategy config
- data window
- benchmark symbol
- regime slicing rules

### Outputs
- total return
- annualized return
- Sharpe
- Sortino
- max drawdown
- turnover
- holding period
- concentration
- benchmark comparison
- regime slice breakdown
- composite score
- pass/fail flags

### Required utilities
Create:

- `computeSharpe`
- `computeSortino`
- `computeMaxDrawdown`
- `computeTurnover`
- `computeCompositeScore`
- `slicePerformanceByRegime`

---

## 12) Anti-overfit gate requirements

Implement a deterministic module that rejects weak improvements.

### Required checks
- minimum evaluation window length
- out-of-sample performance check
- walk-forward consistency
- max drawdown ceiling
- max turnover increase
- minimum improvement margin
- stability across time slices
- stability across market regimes

### Output
Return:
- approved true or false
- failed checks
- summary explanation
- metric deltas

---

## 13) Shadow mode implementation

### Objective
Do not immediately replace the baseline after a promising backtest.

### Required behavior
- baseline continues to drive official paper trades
- challenger runs in parallel
- challenger recommendations are logged separately
- portfolio comparison is shown in UI
- after probation period, promotion can be reconsidered

### Storage
Use either:
- separate `ShadowRun` records, or
- an extension of decision runs with `mode = baseline | challenger_shadow`

---

## 14) AI agent prompts and boundaries

Cursor should implement bounded agent prompts.

### Research planner prompt should include
- current baseline summary
- worst recent metrics
- weak segments
- recent rejected candidates
- recent trade outcome summary
- current strategy config
- allowed mutation surfaces

### Research planner should output
- hypothesis
- mutation type
- changed parameters
- rationale
- expected benefit
- risk concerns

### Critic agent prompt should include
- experiment metrics
- baseline metrics
- regime slice table
- turnover and drawdown changes
- anti-overfit check outputs

### Critic should output
- approve for promotion review or not
- top concerns
- risk summary
- whether shadow mode is required

### Hard boundary
Prompts must instruct agents:
- they may propose changes only within allowed config fields
- they may not bypass hard risk constraints
- they may not output code patches in v1
- they may not approve live trading

---

## 15) Research UI requirements

### Research dashboard
Show:
- current baseline strategy
- latest challenger
- recent experiments
- win/loss rate
- promotion decisions
- recent research notes
- average metric delta

### Strategy versions page
Show:
- all strategy versions
- status
- createdAt
- parent version
- key config summary
- promote button for approved candidates only

### Strategy detail page
Show:
- full config
- config diff vs parent
- linked experiments
- linked runs
- promotion history

### Experiment detail page
Show:
- hypothesis
- changed parameters
- raw metrics
- baseline vs challenger
- regime slices
- agent notes
- verdict
- promotion status

### Shadow page
Show:
- baseline vs challenger equity
- pick overlap
- sell timing differences
- drawdown comparison
- turnover comparison

---

## 16) Navigation changes

Add these top-level nav items:
- Research
- Strategies
- Shadow

If the app has role-based access later, these can become admin or research-only sections.
For now, expose them directly.

---

## 17) Acceptance criteria for Cursor

The Karpathy Loop feature is complete only when:

1. I can create and store versioned strategy configs.
2. I can see which strategy version powered each paper-trading run.
3. The system can create an experiment from a baseline strategy.
4. The system can mutate bounded strategy config fields.
5. The system can backtest and evaluate the candidate.
6. The system computes a composite score and anti-overfit checks.
7. The system can approve or reject a candidate.
8. I can inspect experiment results in the UI.
9. I can compare baseline vs challenger in shadow mode.
10. Promotion does not happen without passing the gate.
11. All experiment changes are logged and auditable.
12. No AI agent directly rewrites production trading code in v1.

---

## 18) Recommended build order in exact sequence

Cursor should implement in this exact order:

### Step 1
Create `StrategyVersion` model and registry utilities.

### Step 2
Add `strategyVersionId` to paper-trading records.

### Step 3
Create strategy config schema and default baseline strategy.

### Step 4
Create experiment models and experiment creation flow.

### Step 5
Build evaluation utilities and composite score logic.

### Step 6
Build anti-overfit gate.

### Step 7
Create research planner agent with bounded output schema.

### Step 8
Create experiment runner job.

### Step 9
Create promotion decision flow.

### Step 10
Create shadow mode.

### Step 11
Create research UI pages.

### Step 12
Wire in slower scheduled research loop.

---

## 19) What Cursor should avoid

Do not:
- let the agent freely edit TypeScript or Python source code in production
- let the LLM become the direct trading model
- auto-promote based on one backtest
- optimize only for raw return
- remove auditability
- mix production execution with research mutation
- add live broker support as part of this phase

---

## 20) Final instruction to Cursor

Build the InvestBest Karpathy Loop as a safe, auditable, config-driven improvement system.

The first version must focus on:
- versioned strategies
- controlled experiments
- deterministic evaluation
- promotion gates
- shadow mode
- research visibility

Do not build a free-form autonomous trading AI.
Build a bounded research-and-improvement loop around the existing paper-trading engine.

That is the correct implementation for v1.
