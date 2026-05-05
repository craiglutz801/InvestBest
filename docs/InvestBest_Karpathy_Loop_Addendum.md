# InvestBest — Karpathy-Loop Addendum for Cursor
**Version:** 1.0  
**Date:** 2026-04-20

This document extends the existing InvestBest build spec and overview. Treat this as an addendum focused on implementing a Karpathy-style improvement loop for InvestBest.

---

## 1) What this means in InvestBest

I want InvestBest to adopt a Karpathy Loop style workflow for continuous improvement.

### Interpretation for this project
The “Karpathy Loop” in this context means:

1. AI agents are given a clear improvement objective.
2. They propose small, testable changes to the system.
3. The system runs those changes in a controlled evaluation loop.
4. Results are measured automatically.
5. Better variants are kept.
6. Worse variants are rejected.
7. The loop repeats continuously.

This is not “let the AI freely control money.”
This is not “let the AI rewrite the whole app in production.”
This is not “let the LLM make unaudited trading decisions.”

For InvestBest, the correct implementation is:

- the live product remains a paper-trading, auditable system
- the agents run a continuous research-and-improvement loop
- every model or rules change is tested before promotion
- promotion is gated by measurable performance

---

## 2) Can this be done?

Yes, this can absolutely be done.

But it should be implemented in a safe and structured way.

### Correct framing
Use agents to improve:
- ranking logic
- feature engineering
- thresholds
- risk rules
- search profiles
- segment allocations
- model hyperparameters
- ensemble weights
- sell logic
- portfolio constraints

Do not let agents directly:
- place real trades
- bypass portfolio guardrails
- modify production trading code without evaluation
- self-approve promotion to live execution
- optimize for raw returns alone without risk controls

---

## 3) Core idea for InvestBest

Split InvestBest into two loops:

### Loop A — Trading loop
This is the existing hourly paper-trading loop.

It does:
- fetch data
- score opportunities
- revalue holdings
- simulate buys and sells
- update portfolio
- store decisions and P&L

This loop is the operator.

### Loop B — Improvement loop
This is the new Karpathy-style agent loop.

It does:
- inspect historical outcomes
- inspect current strategy config
- propose a small change
- run backtests and walk-forward tests
- compare metrics vs baseline
- keep or reject the change
- record the result
- optionally promote the better configuration

This loop is the researcher.

The improvement loop should improve the operator loop, not replace it.

---

## 4) The right architecture

Implement a system with these layers:

### Layer 1 — Production paper trader
The current InvestBest web app and scheduled agent.

### Layer 2 — Research sandbox
A separate environment where agent proposals are tested safely.

### Layer 3 — Experiment evaluation engine
A service that runs:
- backtests
- walk-forward tests
- ablation tests
- robustness checks
- metric comparisons

### Layer 4 — Promotion gate
A controlled step that decides whether an experiment becomes the new default strategy.

---

## 5) Key design rule

The agent must only be allowed to change bounded strategy surfaces, not arbitrary code everywhere.

### Allowed mutation surfaces
The agent may propose changes to:
- feature lists
- threshold values
- scoring weights
- search profile settings
- risk settings
- ranking formulas
- model hyperparameters
- segment weights
- rebalance behavior
- stop-loss and take-profit rules
- confidence thresholds
- position sizing parameters

### Restricted mutation surfaces
The agent may not directly modify:
- broker execution logic
- auth and security code
- payment code
- database migration history
- secrets and config handling
- production infrastructure code
- audit trail storage rules

### Strong recommendation
Start with config-first mutation, not full code mutation.

That means the improvement loop should mostly edit:
- JSON configs
- YAML strategy definitions
- model parameter files
- search profiles
- feature flags

Only later, if needed, allow bounded code edits in a sandbox.

---

## 6) The correct improvement objective

Do not optimize for “make the most money” as a single metric.

That is too naive and will likely produce unstable or overfit behavior.

### Primary optimization target
Optimize for risk-adjusted returns over paper and historical evaluation.

### Recommended objective stack
Use a weighted score such as:

- total return
- Sharpe ratio
- max drawdown penalty
- turnover penalty
- concentration penalty
- instability penalty
- regime robustness score

### Example composite objective
composite_score =
  0.35 * normalized_total_return
+ 0.25 * normalized_sharpe
- 0.20 * normalized_max_drawdown
- 0.10 * normalized_turnover
- 0.10 * normalized_concentration_risk

Cursor should make this configurable.

### Promotion rule
A strategy variant should only be promoted if it beats the current baseline on:
- composite score
- max drawdown ceiling
- minimum sample size
- stability across multiple periods and regimes

---

## 7) What the agent loop should actually do

Use this sequence:

### Step 1 — Read current baseline
The agent reads:
- current strategy config
- recent run logs
- recent trade outcomes
- segment performance
- failed sell decisions
- missed opportunities
- historical backtest summary

### Step 2 — Form a hypothesis
The agent proposes a small improvement hypothesis, for example:
- “Reduce energy segment concentration from 35% to 20%”
- “Increase minimum confidence for agriculture buys”
- “Add 20-day momentum slope as a feature”
- “Tighten sell threshold for high-volatility names”
- “Increase cooldown after a sell from 24h to 48h”
- “Use regime filter to reduce buys during weak benchmark conditions”

### Step 3 — Generate candidate variants
The agent creates 1 to 5 candidate variants.

### Step 4 — Evaluate each variant
Run:
- backtest
- walk-forward test
- robustness checks
- compare to baseline

### Step 5 — Score results
Store:
- metrics
- differences vs baseline
- explanation of why it won or lost

### Step 6 — Keep or discard
Only keep variants that clear promotion rules.

### Step 7 — Promote cautiously
Promote the winner to:
- default search profile
- default model config
- candidate production strategy

### Step 8 — Log everything
Store complete experiment history.

---

## 8) Recommended agent roles

Do not start with a huge swarm.
Use a small, clear multi-agent design.

### Agent 1 — Research Planner
Responsibilities:
- inspect past performance
- identify weak spots
- create experiment ideas
- propose bounded strategy variants

### Agent 2 — Experiment Runner
Responsibilities:
- execute backtests
- execute walk-forward tests
- collect metrics
- validate output completeness

### Agent 3 — Critic / Risk Reviewer
Responsibilities:
- detect overfitting
- detect unstable improvements
- check drawdown, turnover, and concentration
- veto unsafe promotions

### Agent 4 — Promoter
Responsibilities:
- compare approved candidates to baseline
- promote only if acceptance criteria are met
- update default strategy version

### Agent 5 — Narrator
Responsibilities:
- summarize the latest experiments
- explain what changed
- write a human-readable research log

For MVP, Agents 1 to 3 can be enough.

---

## 9) Strong recommendation for v1

Use a declarative strategy system instead of letting the agent edit code directly.

### Build a strategy spec
Create strategy specs like:

```json
{
  "name": "baseline_v1",
  "buy_score_weights": {
    "momentum_5d": 0.25,
    "momentum_20d": 0.20,
    "rsi_reversion": 0.10,
    "volatility_penalty": -0.15,
    "liquidity_score": 0.10,
    "benchmark_regime": 0.20
  },
  "buy_threshold": 62,
  "sell_risk_threshold": 70,
  "stop_loss_pct": 0.08,
  "take_profit_pct": 0.16,
  "cash_reserve_pct": 0.10,
  "max_position_pct": 0.08,
  "cooldown_hours": 24,
  "segment_caps": {
    "defense": 0.25,
    "energy": 0.25,
    "agriculture": 0.20,
    "metals": 0.20,
    "broad_equities": 0.40
  }
}
```

The improvement loop should mutate these strategy specs first.

### Why
This is safer, easier to audit, easier to compare, and much easier for Cursor to build.

---

## 10) Experiment design rules

Each experiment should be:
- small
- isolated
- measurable
- reversible

### Good experiments
- adjust one threshold
- add one feature
- change one weighting family
- adjust one segment cap
- compare one sell rule variation
- compare two position-sizing formulas

### Bad experiments
- rewrite the whole scoring engine
- change 20 variables at once
- mix feature changes, risk changes, and execution changes in one run
- promote changes based on one lucky backtest period

### Cursor instruction
Default to one-factor or few-factor experiments unless explicitly configured otherwise.

---

## 11) Backtesting and evaluation requirements

This is the heart of the loop.

### Required evaluation modes
1. Historical backtest
2. Walk-forward validation
3. Out-of-sample holdout
4. Regime-based slicing
5. Paper-forward shadow test

### Required metrics
- total return
- annualized return
- Sharpe ratio
- Sortino ratio
- max drawdown
- Calmar ratio
- win rate
- average gain
- average loss
- turnover
- average holding period
- exposure
- benchmark relative return
- concentration score
- stability score across windows

### Regime slices
Compare strategy performance in:
- rising market
- falling market
- sideways market
- high-volatility market
- low-volatility market
- commodity-led market
- equity-led market

### Important
A strategy should not be promoted just because it did well in one narrow regime.

---

## 12) Anti-overfitting rules

The agent loop must include explicit anti-overfitting safeguards.

### Required safeguards
- minimum backtest window length
- out-of-sample evaluation
- walk-forward testing
- robustness penalty for unstable performance
- cap on experiment complexity
- novelty penalty if change is too broad
- require repeated wins across multiple windows

### Promotion guardrails
Do not promote if:
- max drawdown worsens beyond allowed threshold
- turnover spikes too much
- results improve only in one window
- confidence interval is too weak
- experiment relied on incomplete data
- benefit is too small relative to noise

---

## 13) Where AI should be used

### Good use of LLM agents
- reading logs
- proposing hypotheses
- suggesting config changes
- interpreting metric tables
- summarizing experiment results
- maintaining experiment notes
- generating candidate search profiles
- suggesting feature additions

### Good use of ML and quant logic
- scoring assets
- estimating expected returns
- estimating downside risk
- ranking candidates
- measuring portfolio effects
- computing metrics
- backtesting variants

### Bad use of LLM agents
- free-form deciding trades from raw news alone
- overriding hard risk rules
- approving live execution by themselves
- mutating production code without sandbox plus tests
- optimizing only for recent profits

---

## 14) Recommended system components to build

### New subsystem A — Strategy Registry
Store versioned strategy specs.

Fields:
- strategyId
- parentStrategyId
- version
- status
- configJson
- createdBy
- createdAt
- notes

Statuses:
- draft
- testing
- approved
- baseline
- rejected
- archived

### New subsystem B — Experiment Registry
Store every experiment.

Fields:
- experimentId
- strategyId
- baselineStrategyId
- hypothesis
- changedParameters
- datasetWindow
- evaluationMode
- resultMetricsJson
- verdict
- createdAt
- completedAt

### New subsystem C — Improvement Jobs
Scheduled jobs that:
- pick a research task
- create variants
- run evaluations
- store results
- request promotion if appropriate

### New subsystem D — Promotion Gate
A deterministic module that checks:
- metric thresholds
- stability rules
- risk rules
- anti-overfit rules

### New subsystem E — Research Dashboard
UI for:
- latest experiments
- baseline vs challenger
- promoted strategies
- rejected strategies
- experiment notes
- regime performance breakdown

---

## 15) Database additions

Add these tables.

### `strategy_versions`
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

### `experiments`
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

### `experiment_runs`
- id
- experimentId
- runType
- status
- startedAt
- finishedAt
- logsJson
- artifactsJson

### `promotion_decisions`
- id
- candidateStrategyVersionId
- baselineStrategyVersionId
- approved
- approvedBy
- decisionReason
- metricsDeltaJson
- createdAt

### `research_notes`
- id
- experimentId
- agentRole
- noteType
- content
- createdAt

---

## 16) Scheduler design

Implement two schedulers.

### Scheduler 1 — Trading operator
Runs hourly.
Does paper trading.

### Scheduler 2 — Improvement researcher
Runs on a slower cadence, such as:
- every 6 hours, or
- daily

### Why separate them
The trading loop should be stable and predictable.
The improvement loop should be slower, heavier, and experimental.

### Recommendation
Do not run continuous model mutation every hour.
Run research jobs daily or every 6 hours, depending on compute.

---

## 17) Promotion policy

Promotion should be conservative.

### Suggested policy
A challenger strategy becomes the new baseline only if:
1. it improves composite score by a minimum margin
2. it does not violate max drawdown ceiling
3. it does not materially worsen turnover
4. it wins across multiple windows or slices
5. it passes anti-overfitting checks
6. it passes smoke tests in paper-forward mode

### Best practice
Before making a challenger the default strategy, run it in:
- shadow mode
- alongside current baseline
- for a defined probation period

During shadow mode:
- it produces recommendations
- but does not replace the active baseline yet

---

## 18) Shadow mode requirement

This is strongly recommended.

### How shadow mode works
- baseline strategy continues to drive actual paper trades
- challenger strategy runs in parallel
- challenger decisions are logged separately
- results are compared over time

### Why
This makes promotion safer and more realistic.

---

## 19) UI pages to add

### A. Research Dashboard
Show:
- current baseline strategy
- latest challenger
- latest experiments
- experiment win/loss rate
- promoted variants
- rejected variants
- research summaries

### B. Strategy Versions page
Show:
- all strategy versions
- version diffs
- parent-child lineage
- status
- key parameters

### C. Experiment Detail page
Show:
- hypothesis
- changed parameters
- evaluation windows
- metrics table
- regime slice results
- promotion verdict
- agent notes

### D. Shadow Comparison page
Show:
- baseline vs challenger returns
- drawdown comparison
- turnover comparison
- overlap in picks
- differences in sell timing

---

## 20) API routes to add

### Strategy versioning
- `GET /api/strategies`
- `GET /api/strategies/:id`
- `POST /api/strategies`
- `POST /api/strategies/:id/clone`
- `POST /api/strategies/:id/promote`

### Experiments
- `GET /api/experiments`
- `GET /api/experiments/:id`
- `POST /api/experiments`
- `POST /api/experiments/:id/run`
- `GET /api/experiments/:id/results`

### Improvement loop
- `POST /api/internal/research/run`
- `POST /api/internal/research/generate-variants`
- `POST /api/internal/research/evaluate`
- `POST /api/internal/research/promote`

### Shadow mode
- `GET /api/shadow/current`
- `GET /api/shadow/comparison`

---

## 21) Recommended implementation order

### Phase 1 — Foundations
Build:
- strategy registry
- experiment registry
- backtest comparison engine
- promotion gate

### Phase 2 — Simple agent loop
Build:
- research planner agent
- experiment runner
- critic
- experiment summaries

### Phase 3 — Shadow mode
Build:
- challenger strategy tracking
- shadow comparison UI
- promotion workflow

### Phase 4 — More advanced improvements
Build:
- richer feature mutations
- ensemble variants
- smarter regime-specific profiles
- bounded code-edit sandbox if truly needed

---

## 22) What Cursor should build first

Cursor should not begin by creating a swarm of autonomous code-editing agents.

Cursor should first build this minimal viable improvement loop:

1. versioned strategy configs
2. experiment runner
3. backtest and walk-forward evaluation
4. promotion gate
5. research dashboard
6. single agent that proposes small config changes
7. optional critic agent
8. shadow mode

This is the safest and most useful first implementation.

---

## 23) Recommended technical stack for the improvement loop

Use the existing InvestBest stack where possible.

### Web app
- Next.js
- TypeScript
- Tailwind
- shadcn/ui

### Database
- Postgres
- Prisma

### Research and evaluation
- Python service
- FastAPI
- pandas
- numpy
- scikit-learn
- LightGBM or XGBoost if ML ranking is enabled

### Background orchestration
- Trigger.dev preferred
- or Vercel cron calling internal routes if simpler initially

### LLM usage
- OpenAI API for:
  - hypothesis generation
  - experiment planning
  - experiment summaries
  - config suggestion
  - critique notes

---

## 24) Key operational rule

Every improvement must be traceable.

For every experiment, save:
- baseline config
- candidate config
- exact diffs
- evaluation window
- metrics
- verdict
- agent explanation
- promotion decision

Nothing should be hidden.

---

## 25) Final build instruction to Cursor

Implement a Karpathy-style continuous improvement loop for InvestBest, but do it safely and systematically.

InvestBest should have:

- a stable hourly paper-trading operator loop
- a separate slower research loop that proposes small improvements
- versioned strategy configs
- controlled experiments
- backtest and walk-forward evaluation
- anti-overfitting checks
- conservative promotion rules
- shadow-mode comparisons
- full experiment logging and research dashboards

The system should use AI agents to improve strategy logic and configuration over time, but only through bounded, auditable, testable workflows.

Do not let agents directly control real trading or make unconstrained production code changes.

---

## 26) Plain-English summary

Yes, I want InvestBest to have a Karpathy-style autonomous improvement loop.

But I want the safe trading-app version of it:
- agents propose improvements,
- the system tests them,
- only winning variants survive,
- and everything stays auditable.

That is the correct implementation.
