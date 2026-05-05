# InvestBest Strategy Upgrade + Agent Scheduler Cursor Spec
**Version:** 1.1  
**Date:** 2026-04-29  
**Purpose:** Make InvestBest materially better after recent paper-trading losses and ensure the agent can run automatically on a configurable schedule, including every hour by default.

---

## 0) Executive Summary

InvestBest has been losing money because the current strategy is too simple for the market conditions it is trying to trade.

The current engine is an explainable, long-only, rules-based momentum system. It mostly uses recent daily price/volume data, simple moving averages, RSI, volatility, volume spikes, fixed stop-loss/take-profit thresholds, and a broad SPY regime throttle. That is a good MVP foundation, but it is not enough to reliably adapt across different market regimes, sectors, commodities, volatility states, and whipsaw environments.

This upgrade plan should transform InvestBest from:

> “A simple technical stock/ETF picker”

into:

> “A research-driven, regime-aware, risk-managed paper-trading system with robust backtesting, adaptive strategies, portfolio-level intelligence, AI-assisted continuous improvement, and reliable scheduled agent execution.”

This does **not** mean promising profits. It means making the system much harder to fool, much easier to measure, and much better at rejecting weak trades.

---

## 1) New Required Addition: Automatic Agent Scheduler

This must be part of the core InvestBest product.

### 1.1 The problem

The app currently has a manual **Run Agent Now** action, but InvestBest needs a reliable automation layer that can kick off the same agent run automatically.

### 1.2 Required behavior

InvestBest must support:

1. A manual **Run Agent Now** button.
2. A scheduled automatic agent run.
3. Default schedule: **every hour**.
4. User-configurable run frequency.
5. Ability to enable/disable scheduled runs.
6. Ability to see when the next run will happen.
7. Ability to see when the last run completed.
8. Ability to see whether the last run succeeded, failed, was skipped, or is still running.
9. Protection against overlapping runs.
10. Secure internal route protection so random users cannot trigger the agent.

### 1.3 Important scheduling decision

Cursor should implement the scheduler using a provider abstraction, not hardcoded directly into one platform.

Use a `SchedulerProvider` interface so the app can support:

- Trigger.dev scheduled jobs,
- Vercel Cron,
- database-driven polling,
- or another external scheduler later.

### 1.4 Recommended scheduler provider

Use **Trigger.dev** as the preferred implementation for production-like behavior because InvestBest needs:
- hourly or configurable schedules,
- durable jobs,
- retries,
- logging,
- visibility,
- concurrency controls,
- and better long-running task support.

Vercel Cron can be used as a fallback for simple deployments, but Cursor must understand that Vercel Cron is better for fixed schedules defined at deploy time and may have plan-specific frequency limitations. If the user needs dynamic frequency changes from the UI, Trigger.dev or a database-driven scheduler is the better design.

### 1.5 Core rule

The manual button and the cron/scheduled job must call the **same core function**.

Do not duplicate logic.

Correct architecture:

```text
Manual Run Agent Now button
        |
        v
POST /api/runs/trigger
        |
        v
runInvestBestAgent()

Scheduled hourly job
        |
        v
POST /api/internal/hourly-run
        |
        v
runInvestBestAgent()
```

There should be one shared orchestrator:

`runInvestBestAgent({ triggerSource, strategyVersionId, searchProfileId, dryRun })`

Where `triggerSource` can be:
- `manual`
- `scheduled`
- `research_shadow`
- `backtest`
- `retry`

---

## 2) Scheduler Settings UI

Add scheduler controls to Settings.

### 2.1 Settings fields

Add a Settings section called:

**Agent Automation**

Fields:

- `scheduledRunsEnabled` boolean
- `runFrequencyMinutes` number
- `schedulePreset` enum
- `customCronExpression` string optional
- `timezone` string
- `runOnlyDuringMarketHours` boolean
- `runOnMarketDaysOnly` boolean
- `skipIfRunAlreadyActive` boolean
- `maxRunDurationMinutes` number
- `retryFailedRuns` boolean
- `maxRetries` number
- `lastRunAt` datetime
- `nextRunAt` datetime
- `lastRunStatus` enum
- `lastRunError` string optional

### 2.2 Schedule presets

Support these presets:

- every 15 minutes
- every 30 minutes
- every hour
- every 2 hours
- every 4 hours
- daily after market close
- daily before market open
- custom cron

Default:
- every hour

### 2.3 Market-hours warning

If the strategy uses mostly daily indicators, the UI should warn:

> This strategy uses daily indicators. Hourly runs may repeat decisions from stale daily signals unless intraday data is enabled.

This is important because the current strategy mostly uses daily OHLCV indicators.

### 2.4 Recommended default for current strategy

For the current daily-data strategy:
- scheduled runs should be enabled,
- default frequency can be hourly because the user requested it,
- but the app should clearly expose a recommended option: `daily after market close`.

Cursor should not remove hourly support. Hourly must exist.

---

## 3) Scheduler Database Changes

Add or update these database tables.

### 3.1 `agent_schedule_settings`

Fields:
- id
- userId
- enabled
- frequencyMinutes
- schedulePreset
- customCronExpression
- timezone
- runOnlyDuringMarketHours
- runOnMarketDaysOnly
- skipIfRunAlreadyActive
- maxRunDurationMinutes
- retryFailedRuns
- maxRetries
- nextRunAt
- lastRunAt
- lastRunStatus
- lastRunError
- createdAt
- updatedAt

### 3.2 `agent_run_locks`

Used to prevent overlapping runs.

Fields:
- id
- userId
- lockKey
- acquiredAt
- expiresAt
- runId
- status

Rules:
- before a scheduled/manual run starts, acquire lock
- if lock exists and is not expired, skip or fail gracefully
- if lock expired, allow recovery

### 3.3 Update `decision_runs`

Add:
- triggerSource
- scheduleId
- startedBy
- requestedAt
- queuedAt
- lockId
- idempotencyKey
- runMode
- dryRun
- strategyVersionId
- searchProfileId

Possible `triggerSource` values:
- `manual`
- `scheduled`
- `retry`
- `research`
- `shadow`
- `backtest`

Possible `runMode` values:
- `paper_trade`
- `dry_run`
- `shadow`
- `backtest`

---

## 4) Scheduler API Routes

Create or update these routes.

### 4.1 Manual run

`POST /api/runs/trigger`

Payload:
```json
{
  "strategyVersionId": "optional",
  "searchProfileId": "optional",
  "dryRun": false,
  "force": false
}
```

Behavior:
- validates user permission
- checks run lock
- calls shared `runInvestBestAgent`
- returns run id and status

### 4.2 Internal scheduled run

`POST /api/internal/hourly-run`

Headers:
- must require `x-internal-cron-secret`

Payload:
```json
{
  "scheduleId": "optional",
  "triggerSource": "scheduled"
}
```

Behavior:
- validates internal secret
- loads enabled schedule settings
- checks whether run is due
- checks market-hours rules
- checks run lock
- calls shared `runInvestBestAgent`
- records skipped status if not due

### 4.3 Scheduler settings

`GET /api/settings/agent-schedule`

Returns current schedule settings.

`PUT /api/settings/agent-schedule`

Updates:
- enabled
- frequency
- preset
- custom cron
- market-hours settings
- retry behavior

### 4.4 Next run calculation

`GET /api/settings/agent-schedule/next-run`

Returns:
- nextRunAt
- lastRunAt
- lastRunStatus
- schedule description
- warnings

### 4.5 Run status

`GET /api/runs/latest`

Returns:
- latest run
- status
- trigger source
- startedAt
- completedAt
- error if failed

---

## 5) Scheduler Implementation Files

Create:

- `apps/web/src/lib/scheduler/types.ts`
- `apps/web/src/lib/scheduler/scheduleSettings.ts`
- `apps/web/src/lib/scheduler/calculateNextRun.ts`
- `apps/web/src/lib/scheduler/marketHours.ts`
- `apps/web/src/lib/scheduler/runLock.ts`
- `apps/web/src/lib/scheduler/triggerAgentRun.ts`
- `apps/web/src/lib/jobs/hourlyAgentScheduler.ts`
- `apps/web/src/app/api/internal/hourly-run/route.ts`
- `apps/web/src/app/api/settings/agent-schedule/route.ts`
- `apps/web/src/app/api/settings/agent-schedule/next-run/route.ts`

Update:

- `apps/web/src/app/api/runs/trigger/route.ts`
- existing Settings page
- existing Run Agent Now button
- existing decision run creation logic
- existing internal hourly-run route if present

---

## 6) Scheduler Provider Abstraction

Create:

`apps/web/src/lib/scheduler/provider.ts`

Interface:

```ts
export interface SchedulerProvider {
  name: string;

  registerSchedule(input: RegisterScheduleInput): Promise<RegisterScheduleResult>;

  updateSchedule(input: UpdateScheduleInput): Promise<UpdateScheduleResult>;

  disableSchedule(input: DisableScheduleInput): Promise<void>;

  getScheduleStatus(input: GetScheduleStatusInput): Promise<ScheduleStatus>;
}
```

### 6.1 Trigger.dev provider

Create:

`apps/web/src/lib/scheduler/providers/triggerDevScheduler.ts`

Responsibilities:
- define scheduled job
- call internal agent route or directly call `runInvestBestAgent`
- apply concurrency rules
- log retries

### 6.2 Vercel Cron fallback

Create:

`apps/web/src/lib/scheduler/providers/vercelCronScheduler.ts`

Responsibilities:
- support fixed cron configured in `vercel.json`
- call `/api/internal/hourly-run`
- warn if user expects dynamic frequency changes from UI

### 6.3 Database scheduler fallback

Optional but useful for local development.

Create:

`apps/web/src/lib/scheduler/providers/databaseScheduler.ts`

Responsibilities:
- check due schedules when route is called
- useful with a single fixed cron that runs frequently and checks user settings dynamically

Example:
- Vercel Cron calls `/api/internal/scheduler-tick` every hour
- app checks database settings
- if user frequency says every 2 hours, only run when due

This approach allows dynamic frequency changes even when the hosting cron is static.

---

## 7) Recommended Scheduling Architecture

Cursor should implement this practical architecture:

### 7.1 Static external tick + dynamic database schedule

Use one external scheduler tick, ideally every hour by default.

The external scheduler calls:

`POST /api/internal/scheduler-tick`

Then the app checks database settings:
- is schedule enabled?
- is a run due?
- is market open if market-hours-only?
- is another run active?
- should this be skipped?
- should it call `runInvestBestAgent`?

This gives the app UI control over frequency without needing to redeploy for every schedule change.

### 7.2 Add route

`POST /api/internal/scheduler-tick`

Behavior:
1. validate cron secret
2. load schedule settings
3. compute due schedules
4. for each due schedule:
   - acquire lock
   - create decision run
   - execute agent
   - update nextRunAt
5. return summary

### 7.3 Why this is better

This design allows:
- default hourly schedule,
- configurable frequency,
- enable/disable without redeploy,
- market-hours logic,
- skip-on-active-run logic,
- retry logic,
- central run logging.

---

## 8) Vercel Cron Configuration

If using Vercel Cron fallback, add to `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/internal/scheduler-tick",
      "schedule": "0 * * * *"
    }
  ]
}
```

This triggers once per hour.

Important:
- keep actual user frequency in the database,
- the hourly cron is just a heartbeat,
- if user sets every 2 hours, database logic skips every other tick,
- if user sets daily, database logic runs only when due.

If the app needs every 15 or 30 minutes, the deployed cron provider must support that frequency. Otherwise use Trigger.dev.

---

## 9) Trigger.dev Scheduling

If using Trigger.dev, create a scheduled task:

`hourly-agent-scheduler`

It should:
- run on the configured cadence,
- or run as a frequent scheduler tick,
- call shared scheduler service,
- enforce no overlapping runs,
- log attempts and retries.

Preferred:
- Trigger.dev runs a scheduler tick every hour by default.
- InvestBest database decides whether the agent is due.
- If user selects 15/30 minutes, Trigger.dev schedule can be updated or a more frequent tick can be used.

---

## 10) Environment Variables

Add:

```env
INTERNAL_CRON_SECRET=
SCHEDULER_PROVIDER=triggerdev
DEFAULT_AGENT_RUN_FREQUENCY_MINUTES=60
AGENT_RUN_LOCK_TIMEOUT_MINUTES=45
TRIGGER_SECRET_KEY=
TRIGGER_PROJECT_ID=
```

Optional:

```env
ENABLE_AGENT_SCHEDULER=true
ENABLE_MARKET_HOURS_ONLY=false
DEFAULT_SCHEDULE_TIMEZONE=America/Denver
```

---

## 11) Scheduler UI Acceptance Criteria

The Settings page must show:

- scheduled runs enabled/disabled
- current frequency
- next run time
- last run time
- last run status
- manual Run Agent Now button
- dry-run option
- force-run option
- market-hours-only toggle
- run-on-market-days-only toggle
- current scheduler provider
- warning if scheduler is misconfigured

Dashboard should show:

- last agent run
- next scheduled run
- run status
- current lock/running state
- latest scheduled-run result

---

## 12) Scheduler Safety Requirements

### 12.1 Idempotency

Every scheduled run must have an idempotency key.

Example:
`userId:scheduleId:YYYY-MM-DDTHH`

If the same scheduled run is retried, it must not double-buy or double-sell.

### 12.2 Locking

Before running:
- acquire `agent_run_locks`
- release on success/failure
- expire after timeout

### 12.3 Run timeout

If run exceeds `maxRunDurationMinutes`:
- mark run as timed out
- release lock after lock expiry
- alert in UI

### 12.4 Error handling

If scheduled run fails:
- store error
- update schedule lastRunStatus
- optionally retry
- do not corrupt portfolio state
- do not execute partial duplicate trades

### 12.5 No duplicate trade execution

The paper-trading engine must be transaction-safe.

When executing a decision:
- create decision run
- create paper trades
- update positions
- update cash
- create portfolio snapshot

These should happen in a safe transaction or with clear recovery rules.

---

## 13) Strategy Improvement Principles

Cursor should follow these principles exactly.

### 13.1 Do not simply make the system more aggressive
The answer is not:
- lower buy thresholds,
- bigger position sizes,
- more trades,
- tighter profit chasing,
- or letting an LLM freely pick winners.

That will likely make losses worse.

### 13.2 Improve evidence quality first
Before adding more complexity, the system needs:
- better backtesting,
- better attribution,
- better data quality,
- better portfolio-level risk measurement,
- better regime classification,
- better evaluation of each rule.

### 13.3 Separate prediction from portfolio construction
A symbol can look good individually but still be bad for the portfolio.

InvestBest must separate:
1. asset scoring,
2. portfolio fit,
3. risk sizing,
4. execution simulation,
5. exit logic.

### 13.4 Build multiple strategy families
One generic momentum rule set is too brittle.

InvestBest should support multiple strategy families:
- trend-following,
- mean reversion,
- defensive rotation,
- commodity/macro rotation,
- quality momentum,
- cash-preservation mode.

### 13.5 Promote only what survives testing
No new rule, model, feature, or search profile should become default unless it passes:
- historical backtest,
- walk-forward validation,
- out-of-sample test,
- regime slice evaluation,
- drawdown limit,
- turnover limit,
- paper-forward shadow mode.

---

## 14) Diagnosis of Current Strategy

The current InvestBest strategy:

- trades long-only equities and ETF-style proxies,
- uses daily OHLCV data,
- scores based on 1d/5d/20d returns, moving average distance, RSI, volatility, volume spikes, and dollar volume,
- uses fixed defaults like 8% stop loss, 15% take profit, buy threshold 45, sell-risk threshold 65, 10% max position, 12 target holdings, and 10% cash reserve,
- uses SPY regime only as a throttle on new buys,
- does not use fundamentals, analyst revisions, macro data, news, learned ML models, factor exposure, correlation, or automatic parameter optimization.

This creates several likely failure modes.

---

## 15) Main Failure Modes to Fix

### 15.1 Whipsaw failure
The strategy buys recent strength, then gets chopped up when momentum reverses quickly.

Symptoms:
- many small losses,
- sells triggered after buying near local highs,
- repeated cooldown churn,
- high turnover with no sustained winners.

### 15.2 Late-entry failure
The strategy enters after the obvious move has already happened.

Current risk:
- 5d and 20d returns positive,
- above moving averages,
- RSI in a broad “healthy” range,
- but no measure of trend maturity, exhaustion, or reward/risk.

### 15.3 Weak exit failure
The sell system is mostly fixed-threshold based:
- 8% stop,
- 15% take profit,
- trailing giveback after progress,
- sell-risk score.

This may:
- sell strong winners too early,
- hold losers too long,
- fail to distinguish normal volatility from real trend failure.

### 15.4 One-size-fits-all failure
Defense stocks, energy, metals, agriculture ETFs, tech, bonds, and dollar proxies do not behave the same.

A single score formula across all of them is too blunt.

### 15.5 Portfolio blindness
The strategy currently looks mostly at symbols individually. It needs to ask:
- Are we already too exposed to the same theme?
- Are new buys highly correlated with existing holdings?
- Is the portfolio beta too high?
- Is one segment causing most losses?
- Are we increasing drawdown risk?

### 15.6 No feedback loop
The system records decisions, but it does not yet learn systematically from:
- which rules are profitable,
- which segments are losing,
- which entry types fail,
- which exit rules help or hurt,
- which market regimes are dangerous.

### 15.7 Scheduling weakness
If the agent is only run manually, InvestBest may:
- miss timely exits,
- fail to revalue holdings consistently,
- produce stale dashboards,
- fail to maintain a true paper-trading timeline.

The scheduled agent must become a core production feature.

---

## 16) New Target Architecture

InvestBest should be upgraded into seven major subsystems:

1. **Agent Scheduler & Run Orchestrator**
2. **Data & Feature Layer**
3. **Strategy Engine**
4. **Portfolio Risk Engine**
5. **Backtesting & Experiment Engine**
6. **AI Research Loop**
7. **Research & Performance UI**

---

## 17) Phase 1 — Scheduler + Run Reliability

This is now a top priority.

### 17.1 Build first

Cursor should first make sure the agent can run automatically and safely.

Required:
- shared `runInvestBestAgent` function,
- manual run calls same function,
- scheduled run calls same function,
- database schedule settings,
- Settings UI controls,
- internal scheduler tick route,
- idempotency keys,
- run locks,
- run status display.

### 17.2 Acceptance criteria

This phase is complete when:

1. I can click **Run Agent Now**.
2. The app can run the agent automatically every hour.
3. I can change frequency in Settings.
4. I can disable scheduled runs.
5. I can see last run and next run.
6. The app prevents overlapping runs.
7. Failed runs are visible.
8. The scheduled route is secret-protected.
9. Scheduled and manual runs produce the same kind of decision records.
10. No duplicate trades occur from retries or duplicate triggers.

---

## 18) Phase 2 — Strategy Diagnostics Layer

Before changing the strategy, Cursor must help reveal why it is losing.

### 18.1 Add performance attribution

Create attribution reports by:

- symbol,
- segment,
- sector,
- strategy family,
- entry rule,
- exit rule,
- holding period,
- market regime,
- volatility regime,
- signal score bucket,
- confidence bucket,
- position size bucket,
- day of week,
- time since last sell cooldown,
- trigger source: manual vs scheduled.

### 18.2 Required new page: Strategy Diagnostics

Create page:

`/diagnostics`

Show:

#### Top-level metrics
- total return
- benchmark return
- excess return
- max drawdown
- Sharpe
- Sortino
- win rate
- average win
- average loss
- profit factor
- expectancy per trade
- average holding period
- turnover
- exposure %
- cash drag
- worst 10 trades
- best 10 trades

#### Attribution tables
- P&L by segment
- P&L by symbol
- P&L by exit reason
- P&L by entry score bucket
- P&L by regime
- P&L by holding period bucket
- P&L by strategy version
- P&L by trigger source

#### Diagnostic warnings
Examples:
- “Energy segment generated 60% of drawdown.”
- “Trades with buy score 45–55 had negative expectancy.”
- “Take-profit exits underperformed trailing exits.”
- “Mean holding period is too short for daily momentum strategy.”
- “High-volatility names produce most losses.”
- “Hourly runs are reprocessing stale daily signals.”

### 18.3 New database table: `trade_attribution_snapshots`

Fields:
- id
- userId
- generatedAt
- windowStart
- windowEnd
- metricsJson
- bySymbolJson
- bySegmentJson
- byExitReasonJson
- byEntryScoreBucketJson
- byRegimeJson
- byHoldingPeriodJson
- byTriggerSourceJson
- warningsJson

### 18.4 Acceptance criteria
This phase is complete when I can answer:
- What exactly is losing money?
- Which rules are hurting?
- Which segments are helping?
- Are losses caused by entries, exits, sizing, schedule frequency, or market regime?

---

## 19) Phase 3 — Upgrade the Backtesting Engine

InvestBest cannot improve without serious backtesting.

### 19.1 Recommended tool approach

Cursor should implement a simple internal backtesting engine first, then optionally integrate stronger external tools.

Recommended options:

1. **Internal deterministic backtester**
   - best for matching InvestBest's paper engine exactly.
2. **vectorbt**
   - good for fast parameter sweeps and testing many strategy variants.
3. **QuantConnect LEAN**
   - good later for more realistic multi-asset research and execution modeling.
4. **PyPortfolioOpt**
   - useful for portfolio construction, covariance estimates, hierarchical risk parity, and Black-Litterman-style allocation.

### 19.2 Required backtest modes

Build these:

#### A. Single strategy backtest
Runs one strategy config across a historical window.

#### B. Parameter sweep
Tests ranges such as:
- buy threshold,
- sell-risk threshold,
- stop loss,
- trailing stop,
- take profit,
- max position size,
- target holdings,
- volatility cap,
- cooldown hours,
- cash reserve,
- segment caps,
- run frequency.

#### C. Walk-forward validation
Example:
- train/tune on 12 months,
- test on next 3 months,
- roll forward.

#### D. Out-of-sample holdout
Keep a final period untouched until candidates are selected.

#### E. Regime-sliced backtest
Report results separately in:
- bull,
- bear,
- sideways,
- high volatility,
- low volatility,
- commodity-led,
- rate-sensitive,
- dollar-up,
- dollar-down.

#### F. Shadow paper-forward test
Runs a challenger strategy beside the baseline without affecting official paper trades.

### 19.3 New UI page: Backtest Lab

Create:

`/backtests`

Features:
- choose strategy version,
- choose date range,
- choose universe,
- choose benchmark,
- choose run frequency,
- choose daily vs hourly simulation mode,
- run backtest,
- compare multiple runs,
- view equity curve,
- view drawdown curve,
- view trades,
- view attribution,
- export results.

### 19.4 New tables

#### `backtest_runs`
- id
- strategyVersionId
- status
- windowStart
- windowEnd
- benchmarkSymbol
- universeSnapshotJson
- settingsJson
- scheduleSettingsJson
- startedAt
- completedAt
- metricsJson
- artifactsJson
- error

#### `backtest_trades`
- id
- backtestRunId
- symbolId
- action
- quantity
- price
- executedAt
- reasonCode
- pnl
- pnlPct
- holdingPeriodHours

#### `backtest_daily_equity`
- id
- backtestRunId
- timestamp
- cash
- investedValue
- totalValue
- drawdownPct
- benchmarkValue

### 19.5 Acceptance criteria
Do not allow the strategy to be changed blindly. Every proposed change must be backtested and compared to current baseline.

---

## 20) Phase 4 — Replace One Generic Ruleset With Strategy Families

The current `rules-v1` should become only one baseline strategy.

Add strategy families.

### 20.1 Strategy Family A — Trend Following

Purpose:
Capture sustained trends and avoid sideways chop.

Features:
- 20d, 50d, 100d, 200d moving average structure,
- breakout confirmation,
- trend age,
- price above rising moving averages,
- volatility-adjusted momentum,
- relative strength vs SPY and segment ETF,
- trailing stop based on ATR.

Entry logic:
- enter only when trend score and relative strength are both strong,
- avoid late entries when price is too extended relative to ATR,
- avoid entries when trend is too mature without consolidation.

Exit logic:
- exit on trend structure break,
- exit on ATR trailing stop,
- exit on relative strength breakdown,
- avoid fixed take-profit as primary exit for strong trends.

### 20.2 Strategy Family B — Mean Reversion

Purpose:
Buy quality/liquid assets after controlled pullbacks, not collapsing knives.

Features:
- RSI below normal,
- distance below short-term moving average,
- positive longer-term trend,
- volatility not exploding,
- no major negative gap,
- mean-reversion z-score.

Entry logic:
- only buy dips inside a higher-timeframe uptrend,
- require reversal confirmation,
- avoid falling assets below long-term trend.

Exit logic:
- sell at mean reversion target,
- sell if bounce fails,
- use tighter risk control than trend-following.

### 20.3 Strategy Family C — Defensive / Risk-Off Rotation

Purpose:
Reduce losses when market regime is poor.

Candidate assets:
- SHY,
- IEF,
- TLT,
- GLD,
- UUP,
- low-volatility ETFs if added,
- cash.

Logic:
- if equity regime deteriorates, reduce equity exposure,
- rotate into defensive assets only if their own trend confirms,
- allow higher cash allocation.

### 20.4 Strategy Family D — Commodity / Macro Rotation

Purpose:
Treat commodity proxies differently from equities.

Segments:
- energy,
- agriculture,
- metals,
- dollar,
- rates.

Features:
- commodity ETF trend,
- inflation proxy trends,
- dollar trend,
- rates trend,
- roll-sensitive proxy caution,
- volatility regime.

Rules:
- use wider stops for commodity ETFs,
- avoid buying high-volatility spikes,
- apply segment-specific max exposure,
- use trend confirmation more heavily than RSI.

### 20.5 Strategy Family E — Quality Momentum

Purpose:
Favor stocks with better fundamentals and price strength.

Requires additional data:
- earnings growth,
- revenue growth,
- free cash flow,
- debt levels,
- margin trend,
- analyst estimate revisions,
- earnings date risk.

MVP version can use ETF/stock technicals only.
Phase 2 can add fundamentals.

### 20.6 Strategy selector

Each symbol/run should decide which strategy family applies.

Create:

`lib/strategy/selectStrategyFamily.ts`

Inputs:
- symbol asset type,
- segment,
- market regime,
- volatility regime,
- liquidity,
- trend state,
- search profile.

Output:
- active strategy family,
- reason.

---

## 21) Phase 5 — Better Market Regime Detection

The current SPY moving-average throttle is too simple.

### 21.1 Build a multi-factor regime engine

Create:

`lib/regime/regimeEngine.ts`

Inputs:
- SPY trend,
- QQQ trend,
- IWM trend,
- VIX or volatility proxy,
- TLT trend,
- UUP trend,
- GLD trend,
- DBC trend,
- sector breadth,
- percentage of universe above 50d/200d averages,
- realized volatility percentile,
- drawdown from recent high.

### 21.2 Regime labels

Assign one of:

- `RISK_ON_TREND`
- `RISK_ON_OVERHEATED`
- `CHOPPY_NEUTRAL`
- `RISK_OFF_BEAR`
- `HIGH_VOL_STRESS`
- `COMMODITY_INFLATION`
- `DEFENSIVE_RATES`
- `UNKNOWN`

### 21.3 Regime actions

#### RISK_ON_TREND
- allow trend-following,
- normal exposure,
- let winners run.

#### RISK_ON_OVERHEATED
- reduce new buys,
- avoid stretched entries,
- prefer pullbacks,
- tighten entry quality.

#### CHOPPY_NEUTRAL
- reduce trend-following,
- favor mean reversion,
- reduce max new positions,
- reduce total exposure.

#### RISK_OFF_BEAR
- block most long equity buys,
- allow defensive rotation,
- raise cash reserve,
- tighten sells.

#### HIGH_VOL_STRESS
- pause new speculative buys,
- reduce position size,
- sell weak holdings faster,
- only allow defensive assets.

#### COMMODITY_INFLATION
- allow energy/metals/agriculture rotation,
- reduce broad growth equity exposure,
- watch dollar/rates.

### 21.4 New table: `market_regime_snapshots`

Fields:
- id
- timestamp
- regime
- confidence
- inputsJson
- breadthJson
- volatilityJson
- trendJson
- actionJson

### 21.5 Dashboard addition
Show current regime, confidence, and what it means for the agent.

---

## 22) Phase 6 — Portfolio-Level Risk Engine

A better strategy must manage portfolio risk, not just individual trades.

### 22.1 Build portfolio risk engine

Create:

`lib/portfolio/riskEngine.ts`

Compute:
- portfolio beta vs SPY,
- volatility estimate,
- correlation matrix,
- concentration by symbol,
- concentration by segment,
- concentration by sector,
- marginal contribution to risk,
- max drawdown,
- current drawdown,
- risk budget usage,
- cash allocation,
- exposure by strategy family.

### 22.2 Portfolio risk rules

Add hard rules:

- max total equity exposure by regime,
- max segment exposure,
- max correlated exposure,
- max portfolio volatility,
- max single-name risk contribution,
- max drawdown action threshold,
- forced de-risking after drawdown breach.

### 22.3 Drawdown circuit breakers

Implement:

#### Portfolio drawdown level 1
If portfolio drawdown from recent high exceeds 3%:
- reduce max new positions,
- increase buy threshold,
- reduce position size.

#### Portfolio drawdown level 2
If drawdown exceeds 6%:
- pause new risky buys,
- only allow defensive rotation,
- tighten sell rules.

#### Portfolio drawdown level 3
If drawdown exceeds 10%:
- stop new buys,
- reduce weakest holdings,
- require manual review before reactivating aggressive mode.

Make thresholds configurable.

### 22.4 Position sizing upgrade

Replace fixed sizing with risk-aware sizing.

Inputs:
- portfolio value,
- asset volatility,
- stop distance,
- max risk per trade,
- portfolio drawdown state,
- regime,
- correlation penalty,
- segment cap.

Formula concept:

`shares = floor(maxDollarRiskPerTrade / dollarRiskPerShare)`

Where:

`dollarRiskPerShare = entryPrice - stopPrice`

Also cap by:
- max position pct,
- segment cap,
- available cash,
- cash reserve.

### 22.5 Target risk per trade

Default:
- risk no more than 0.50% to 1.00% of portfolio per trade.

Example:
If portfolio is $100,000 and risk per trade is 0.75%, max loss per trade is $750.

This is much better than simply buying 8–10% position sizes without tying size to stop distance.

---

## 23) Phase 7 — Improve Entry Quality

The current buy score is too coarse.

### 23.1 New buy-score architecture

Replace one buy score with component scores:

- trend score,
- momentum score,
- pullback quality score,
- relative strength score,
- volatility score,
- liquidity score,
- regime fit score,
- portfolio fit score,
- catalyst/fundamental score if available,
- risk/reward score.

Final score:

`buyScore = weighted sum of component scores`

Weights should depend on strategy family and regime.

### 23.2 Add relative strength

Every candidate should be compared against:
- SPY,
- its segment benchmark,
- its sector ETF if applicable.

Examples:
- defense stock vs ITA/XAR,
- energy stock vs XLE/XOP,
- gold miner vs GDX,
- agriculture proxy vs DBA,
- large tech vs QQQ.

### 23.3 Add trend maturity

Do not buy trends blindly.

Compute:
- number of days above 20d MA,
- number of days above 50d MA,
- distance from 20d MA in ATR units,
- distance from recent breakout,
- recent gap size,
- RSI trend not just RSI level.

Block if:
- too extended,
- recent move is parabolic,
- reward/risk to stop is poor.

### 23.4 Add pullback entries

For trend-following assets, prefer:
- trend is intact,
- asset pulls back toward 20d/50d average,
- volatility normalizes,
- reversal candle or short-term momentum turns up.

### 23.5 Add reward/risk estimate

Before buying, estimate:
- logical stop level,
- target level or trailing approach,
- expected upside,
- downside to stop,
- reward/risk ratio.

Block if reward/risk is below threshold, e.g. 1.5:1.

### 23.6 Candidate rejection reasons

Add precise rejection reasons:
- `TREND_TOO_MATURE`
- `PRICE_TOO_EXTENDED_ATR`
- `POOR_REWARD_RISK`
- `REGIME_MISMATCH`
- `SEGMENT_CAP_EXCEEDED`
- `CORRELATION_TOO_HIGH`
- `VOLATILITY_TOO_HIGH`
- `RELATIVE_STRENGTH_WEAK`
- `LOW_LIQUIDITY`
- `EARNINGS_RISK`
- `BAD_DATA`
- `SCHEDULER_NOT_DUE`
- `RUN_LOCK_ACTIVE`

---

## 24) Phase 8 — Improve Sell Logic

The current exit system may sell winners too early and hold weak positions too long.

### 24.1 Replace fixed take-profit with adaptive exits

Do not always sell at 15% profit.

For trend-following:
- let strong winners run,
- use ATR trailing stop,
- use trend break,
- use relative strength breakdown,
- optionally trim partial position at profit target.

For mean reversion:
- use profit target more directly,
- sell when price returns to mean,
- exit quickly if bounce fails.

For defensive assets:
- exit when risk-on regime returns or defensive trend breaks.

### 24.2 Add ATR-based stop logic

Compute ATR and set stops based on asset volatility.

Examples:
- initial stop = entry - 2.5 * ATR,
- trailing stop = highest close since entry - 3.0 * ATR,
- tighter or looser based on strategy family.

### 24.3 Add time stop

Some trades fail by doing nothing.

Add:
- max holding days by strategy family,
- if position has not reached minimum progress after N days, exit or reduce.

Examples:
- mean reversion: 5–10 trading days,
- trend following: longer,
- tactical commodity rotation: 10–30 trading days.

### 24.4 Add partial exits

Support:
- sell 50% at first target,
- trail remaining 50%,
- reduce risk instead of all-or-nothing.

This can improve winner management.

### 24.5 Add sell-score decomposition

Instead of one sell-risk score, compute:
- loss-control score,
- trend-break score,
- volatility-shock score,
- relative-strength breakdown score,
- regime-exit score,
- time-stop score,
- opportunity-cost score.

### 24.6 Exit attribution
Every exit should record:
- primary exit reason,
- secondary exit reasons,
- whether exit was profitable,
- whether price continued down after exit,
- whether exit was premature.

Add post-trade evaluation after 5, 10, and 20 trading days.

---

## 25) Phase 9 — Add Better Data

Do not add data randomly. Add data only if it can be tested.

### 25.1 Fundamental data for equities

Add optional fundamentals:
- revenue growth,
- earnings growth,
- free cash flow,
- gross margin,
- operating margin,
- debt/equity,
- valuation ratios,
- earnings date,
- analyst estimate revisions.

Use these initially as filters:
- avoid weak companies unless strategy is mean reversion,
- prefer quality in uncertain regimes,
- avoid buying right before earnings unless allowed.

### 25.2 Macro and cross-asset data

Add:
- rates trend,
- dollar trend,
- oil trend,
- gold trend,
- broad commodity trend,
- volatility index/proxy,
- sector ETF trends.

### 25.3 News/sentiment

Use news cautiously.

Allowed use:
- flag unusual risk,
- identify earnings, lawsuits, geopolitical shocks,
- summarize potential catalyst,
- produce a sentiment score only after it is logged and tested.

Do not let LLM news summaries directly trigger trades.

### 25.4 Data-provider abstraction

Current system uses Twelve Data. Keep it, but make providers swappable.

Add provider interface for:
- market data,
- fundamentals,
- news,
- corporate events,
- macro data.

Recommended future providers:
- Twelve Data for broad market data,
- Alpaca for future paper/live brokerage and market data,
- Financial Modeling Prep or Finnhub for fundamentals/news,
- FRED for macro data,
- Polygon for richer market data if budget allows.

---

## 26) Phase 10 — Add ML Carefully

InvestBest should not jump from rules to opaque AI trading.

### 26.1 First ML use case: meta-labeling

Instead of “predict price,” predict:

> “Given that the rules strategy generated a signal, should we take this trade?”

This is safer and more useful.

Features:
- current rule scores,
- regime,
- volatility,
- relative strength,
- segment,
- recent drawdown,
- liquidity,
- trend maturity,
- reward/risk,
- historical win rate for similar signals.

Target:
- whether trade achieved positive risk-adjusted outcome over next N days,
- or whether max adverse excursion was acceptable.

Output:
- trade approval probability,
- expected value estimate,
- uncertainty.

### 26.2 Second ML use case: exit quality

Predict:
- whether holding should be exited,
- whether trailing stop is likely to trigger,
- whether profit should be allowed to run.

### 26.3 Third ML use case: regime classifier

Train classifier to identify:
- risk-on,
- risk-off,
- choppy,
- high-vol stress,
- commodity-led.

### 26.4 Recommended models

Start with:
- logistic regression baseline,
- random forest,
- LightGBM/XGBoost if available.

Do not start with:
- LSTM,
- reinforcement learning,
- giant autonomous LLM trader.

### 26.5 ML validation rules

Use:
- time-series split,
- walk-forward validation,
- purged/embargoed validation where possible,
- no random train/test split,
- no future leakage,
- no optimizing on the same period used for final evaluation.

### 26.6 Model registry

Add:

`model_versions`

Fields:
- id
- modelType
- strategyFamily
- featureSetVersion
- trainingWindowStart
- trainingWindowEnd
- validationMetricsJson
- status
- artifactPath
- createdAt

---

## 27) Phase 11 — Strengthen the Karpathy Improvement Loop

The existing Karpathy Loop idea is still right, but it needs stronger constraints because the strategy has lost money.

### 27.1 Research loop should prioritize diagnosing losses

The research planner should first ask:
- Which rules lost money?
- Which segments lost money?
- Which regimes caused drawdown?
- Which exit rules were premature?
- Which entries had negative expectancy?
- Did the strategy trade too much?
- Did it size risk correctly?
- Did the run frequency contribute to overtrading or stale-signal reuse?

### 27.2 Allowed experiments

The AI research agent may propose:
- one threshold change,
- one strategy-family config change,
- one segment cap change,
- one entry filter addition,
- one exit rule change,
- one sizing change,
- one regime rule change,
- one schedule-frequency experiment.

### 27.3 Forbidden experiments

The research agent may not:
- lower all risk controls at once,
- increase position sizes to recover losses,
- optimize only for recent two-month performance,
- promote strategies without out-of-sample validation,
- add live trading,
- ignore drawdown.

### 27.4 Research loop priorities

Order:
1. reduce drawdown,
2. eliminate negative-expectancy trade types,
3. improve exits,
4. improve regime avoidance,
5. improve entries,
6. improve upside capture,
7. optimize run frequency only after strategy quality is understood.

### 27.5 New research prompts

Add a “Loss Review Agent” prompt.

The Loss Review Agent should output:
- top 5 loss drivers,
- likely root causes,
- experiments to test,
- expected risk reduction,
- whether to disable any segment/rule temporarily.

Add a “Rule Surgeon Agent” prompt.

The Rule Surgeon Agent should output:
- one specific rule change,
- why it should help,
- what metric should improve,
- what metric might worsen,
- how to test it.

Add a “Risk Officer Agent” prompt.

The Risk Officer should veto changes that:
- increase drawdown,
- increase concentration,
- overfit recent data,
- reduce sample size too much,
- rely on incomplete data.

---

## 28) Phase 12 — Better Universe Management

The broader universe is good, but the system must know when not to trade parts of it.

### 28.1 Segment health score

Compute for each segment:
- segment trend,
- segment breadth,
- segment volatility,
- segment relative strength,
- recent strategy P&L,
- recent win rate,
- drawdown contribution.

Segment states:
- `ACTIVE`
- `CAUTION`
- `AVOID`
- `DEFENSIVE_ONLY`

### 28.2 Segment allocation logic

Instead of fixed segment caps only, use dynamic segment weights.

Example:
- if energy trend strong and risk acceptable, allow energy cap up to configured max,
- if agriculture proxies are choppy and negative expectancy, reduce or block,
- if broad market risk-off, reduce equities and raise defensive/cash.

### 28.3 Add sector/industry map

For equities, map symbols to:
- sector,
- industry,
- segment,
- proxy benchmark.

This enables correlation and crowding checks.

### 28.4 Universe expansion policy

Do not expand blindly. New symbols should pass:
- liquidity threshold,
- data availability threshold,
- historical backtest availability,
- segment fit,
- low stale-data rate.

---

## 29) Phase 13 — Better Execution Simulation

Paper trading should be more realistic.

### 29.1 Slippage model

Current slippage is simple. Upgrade to:
- base slippage,
- volatility-based slippage,
- liquidity-based slippage,
- gap penalty,
- ETF-specific slippage.

### 29.2 Market timing

Daily bars may not match hourly runs well.

Options:
- if running hourly, use intraday bars where available,
- if only daily data is reliable, run once daily after market close or before market open,
- do not pretend hourly precision if data is daily.

### 29.3 Recommendation
For now, support both:

#### Option A — Daily strategy
Run after market close.
Use daily bars.
Generate next-day paper orders.

#### Option B — Intraday strategy
Use intraday bars.
Keep hourly runs.
Need stronger data quality.

Because the current technical strategy uses daily features, Cursor should default the strategy recommendation to **daily strategy mode**, but must still support the user's requested automatic **hourly scheduled Run Agent Now** behavior.

---

## 30) Phase 14 — Reconsider Run Frequency

The strategy currently runs hourly, but uses mostly daily indicators.

That is inconsistent.

### 30.1 Required change

Add strategy frequency modes:

- `DAILY_EOD`
- `DAILY_PREMARKET`
- `HOURLY_INTRADAY`
- `MANUAL_RESEARCH`

For the current daily OHLCV-based strategy, use:
- `DAILY_EOD` for analysis,
- paper fills at next open or configurable execution assumption.

Only use hourly as true intraday strategy if:
- intraday bars are used,
- intraday-specific features exist,
- intraday slippage assumptions exist.

### 30.2 Important distinction

There are two related but different settings:

1. **Scheduler frequency**
   - how often the scheduler wakes up and checks whether to run.

2. **Strategy data frequency**
   - whether the strategy uses daily or intraday signals.

Cursor must model both.

### 30.3 Dashboard warning
If hourly runs use daily data, show warning:

> “This strategy uses daily indicators. Hourly execution may create repeated decisions from stale daily signals.”

---

## 31) Phase 15 — Stop Trading Bad Conditions

Add a “No Trade Is A Position” framework.

### 31.1 No-trade conditions

Block or reduce trading when:
- regime is unknown,
- data quality is poor,
- portfolio drawdown threshold breached,
- recent strategy win rate collapses,
- volatility shock,
- benchmark below critical trend,
- too many signals are marginal,
- candidate universe is highly correlated,
- backtest confidence low,
- the agent already ran recently and signals have not materially changed.

### 31.2 Cash as an asset
Cash should be an explicit allowed outcome, not a failure.

If no trades pass high standards:
- hold cash,
- log why,
- do not force buys just to stay active.

---

## 32) Phase 16 — Decision Quality Scoring

Add a post-trade review system.

### 32.1 After each trade closes

Score:
- entry quality,
- exit quality,
- maximum favorable excursion,
- maximum adverse excursion,
- whether stop was too tight/wide,
- whether take profit was premature,
- whether trailing exit helped,
- whether alternative exit would have improved result.

### 32.2 Delayed labels

For each buy candidate, even skipped ones, look forward 5/10/20 days and record:
- future return,
- max drawdown,
- max runup,
- whether buying would have helped.

This creates training data for ML and research agents.

### 32.3 New table: `decision_outcome_labels`

Fields:
- id
- decisionRunItemId
- symbolId
- labelHorizonDays
- futureReturn
- maxFavorableExcursion
- maxAdverseExcursion
- wouldHaveHitStop
- wouldHaveHitTarget
- labelGeneratedAt

---

## 33) Phase 17 — New Composite Score for Strategy Promotion

Every strategy version should be scored with a better objective.

### 33.1 Composite score

Use:

- 25% total return,
- 25% Sortino,
- 20% max drawdown penalty,
- 10% profit factor,
- 10% turnover penalty,
- 10% regime stability.

Make weights configurable.

### 33.2 Hard rejection rules

Reject a strategy if:
- max drawdown worsens beyond threshold,
- Sortino is negative,
- profit factor below 1.05,
- too few trades,
- turnover too high,
- performance comes from one symbol only,
- performance only works in one regime,
- out-of-sample result fails,
- deflated/probabilistic Sharpe confidence is too weak.

### 33.3 Track all trials
Because repeated testing can overfit, store every experiment trial, not just winners.

---

## 34) Recommended Near-Term Default Strategy Variants

Cursor should implement these as candidate strategy variants, not blindly overwrite production defaults.

### Variant 1 — Safer Baseline
Goal:
Reduce losses and whipsaws.

Changes:
- raise buy threshold from 45 to 60,
- raise minimum confidence from 40 to 55,
- lower max position from 10% to 6%,
- reduce max new positions per run from 3 to 1 or 2,
- add portfolio drawdown circuit breakers,
- require relative strength above segment benchmark,
- block buys in choppy neutral unless mean-reversion strategy confirms.

### Variant 2 — Trend-Only Strong Regime
Goal:
Trade less, only in strong conditions.

Changes:
- only buy trend-following candidates in `RISK_ON_TREND`,
- require 20d and 50d trend alignment,
- require relative strength vs benchmark,
- use ATR trailing stop,
- remove fixed take-profit or make it partial only,
- use volatility-adjusted sizing.

### Variant 3 — Defensive Rotation
Goal:
Reduce equity exposure during poor regimes.

Changes:
- when regime is `RISK_OFF_BEAR` or `HIGH_VOL_STRESS`, allow only:
  - SHY,
  - IEF,
  - GLD,
  - UUP,
  - cash,
  - other explicitly defensive proxies.
- block new long equity buys,
- reduce weakest holdings.

### Variant 4 — Pullback in Uptrend
Goal:
Avoid buying overextended momentum.

Changes:
- require higher-timeframe uptrend,
- require pullback near 20d/50d moving average,
- require RSI recovering from 40–55 range,
- block price more than 2 ATR above 20d average,
- use tighter invalidation stop.

### Variant 5 — Commodity Rotation
Goal:
Treat commodities separately.

Changes:
- commodity segment uses trend and volatility filters more heavily,
- wider ATR stops,
- smaller position sizes,
- segment max exposure,
- no RSI-only entries.

### Variant 6 — Daily-vs-Hourly Schedule Test
Goal:
Determine whether hourly runs are helping or hurting the mostly daily strategy.

Compare:
- hourly scheduled runs,
- daily after close runs,
- daily before open runs,
- hourly with intraday data only.

Metrics:
- return,
- drawdown,
- turnover,
- stale signal count,
- duplicate/similar decision count,
- slippage impact,
- missed sell count.

---

## 35) Cursor Implementation Roadmap

Build in this order.

### Sprint 1 — Scheduler and run reliability
- shared `runInvestBestAgent`
- scheduled run settings
- hourly scheduler tick
- manual and scheduled run unification
- run locks
- idempotency
- last/next run display

### Sprint 2 — Stop guessing
- Strategy Diagnostics page
- attribution tables
- performance by segment/rule/regime
- decision outcome labels

### Sprint 3 — Backtest Lab
- deterministic backtester
- parameter sweep
- baseline comparison
- equity/drawdown charts
- result persistence
- run-frequency comparison

### Sprint 4 — Regime Engine
- multi-factor regime snapshots
- regime-specific exposure rules
- dashboard regime card

### Sprint 5 — Portfolio Risk Engine
- correlation matrix
- segment concentration
- risk-per-trade sizing
- drawdown circuit breakers

### Sprint 6 — Strategy Families
- trend-following
- mean-reversion
- defensive rotation
- commodity rotation
- strategy selector

### Sprint 7 — Better exits
- ATR stops
- adaptive trailing stops
- partial exits
- time stops
- exit attribution

### Sprint 8 — Karpathy Research Loop v2
- Loss Review Agent
- Rule Surgeon Agent
- Risk Officer Agent
- safer experiment policy
- shadow mode

### Sprint 9 — ML Meta-Labeling
- delayed labels
- trade approval model
- model registry
- walk-forward validation

---

## 36) Specific Files Cursor Should Create

### Scheduler
- `apps/web/src/lib/scheduler/types.ts`
- `apps/web/src/lib/scheduler/scheduleSettings.ts`
- `apps/web/src/lib/scheduler/calculateNextRun.ts`
- `apps/web/src/lib/scheduler/marketHours.ts`
- `apps/web/src/lib/scheduler/runLock.ts`
- `apps/web/src/lib/scheduler/triggerAgentRun.ts`
- `apps/web/src/lib/scheduler/provider.ts`
- `apps/web/src/lib/scheduler/providers/triggerDevScheduler.ts`
- `apps/web/src/lib/scheduler/providers/vercelCronScheduler.ts`
- `apps/web/src/lib/scheduler/providers/databaseScheduler.ts`
- `apps/web/src/lib/jobs/hourlyAgentScheduler.ts`
- `apps/web/src/app/api/internal/scheduler-tick/route.ts`
- `apps/web/src/app/api/internal/hourly-run/route.ts`
- `apps/web/src/app/api/settings/agent-schedule/route.ts`
- `apps/web/src/app/api/settings/agent-schedule/next-run/route.ts`

### Diagnostics
- `apps/web/src/lib/diagnostics/tradeAttribution.ts`
- `apps/web/src/lib/diagnostics/rulePerformance.ts`
- `apps/web/src/lib/diagnostics/segmentPerformance.ts`
- `apps/web/src/app/diagnostics/page.tsx`
- `apps/web/src/components/diagnostics/AttributionTable.tsx`
- `apps/web/src/components/diagnostics/DiagnosticWarnings.tsx`

### Backtesting
- `apps/web/src/lib/backtest/backtestEngine.ts`
- `apps/web/src/lib/backtest/parameterSweep.ts`
- `apps/web/src/lib/backtest/walkForward.ts`
- `apps/web/src/lib/backtest/backtestMetrics.ts`
- `apps/web/src/app/backtests/page.tsx`
- `apps/web/src/components/backtests/BacktestRunner.tsx`
- `apps/web/src/components/backtests/BacktestComparison.tsx`

### Regime
- `apps/web/src/lib/regime/regimeEngine.ts`
- `apps/web/src/lib/regime/regimeClassifier.ts`
- `apps/web/src/lib/regime/regimeActions.ts`
- `apps/web/src/components/regime/RegimeCard.tsx`

### Portfolio Risk
- `apps/web/src/lib/portfolio/riskEngine.ts`
- `apps/web/src/lib/portfolio/riskSizing.ts`
- `apps/web/src/lib/portfolio/drawdownCircuitBreaker.ts`
- `apps/web/src/components/portfolio/RiskDashboard.tsx`

### Strategy Families
- `apps/web/src/lib/strategy/families/trendFollowing.ts`
- `apps/web/src/lib/strategy/families/meanReversion.ts`
- `apps/web/src/lib/strategy/families/defensiveRotation.ts`
- `apps/web/src/lib/strategy/families/commodityRotation.ts`
- `apps/web/src/lib/strategy/selectStrategyFamily.ts`

### Exits
- `apps/web/src/lib/exits/atrStops.ts`
- `apps/web/src/lib/exits/trailingStops.ts`
- `apps/web/src/lib/exits/timeStops.ts`
- `apps/web/src/lib/exits/partialExits.ts`
- `apps/web/src/lib/exits/exitAttribution.ts`

### Research Agents
- `apps/web/src/lib/agents/lossReviewAgent.ts`
- `apps/web/src/lib/agents/ruleSurgeonAgent.ts`
- `apps/web/src/lib/agents/riskOfficerAgent.ts`

### ML
- `apps/ml-service/app/meta_labeling.py`
- `apps/ml-service/app/feature_sets.py`
- `apps/ml-service/app/model_registry.py`
- `apps/ml-service/training/train_trade_approval_model.py`

---

## 37) New API Routes

### Scheduler
- `POST /api/internal/scheduler-tick`
- `POST /api/internal/hourly-run`
- `GET /api/settings/agent-schedule`
- `PUT /api/settings/agent-schedule`
- `GET /api/settings/agent-schedule/next-run`
- `POST /api/runs/trigger`
- `GET /api/runs/latest`

### Diagnostics
- `GET /api/diagnostics/summary`
- `GET /api/diagnostics/attribution`
- `POST /api/diagnostics/rebuild`

### Backtests
- `GET /api/backtests`
- `POST /api/backtests/run`
- `POST /api/backtests/sweep`
- `POST /api/backtests/walk-forward`
- `GET /api/backtests/:id`

### Regime
- `GET /api/regime/current`
- `GET /api/regime/history`
- `POST /api/regime/recompute`

### Risk
- `GET /api/portfolio/risk`
- `GET /api/portfolio/exposures`
- `POST /api/portfolio/recompute-risk`

### Strategy Families
- `GET /api/strategy-families`
- `PUT /api/strategy-families/settings`

### Research
- `POST /api/research/loss-review`
- `POST /api/research/propose-rule-change`
- `POST /api/research/risk-review`

### ML
- `POST /api/ml/train-meta-labeler`
- `POST /api/ml/score-trade-approval`
- `GET /api/ml/models`

---

## 38) Updated Database Schema Additions

Add:

- `agent_schedule_settings`
- `agent_run_locks`
- `trade_attribution_snapshots`
- `backtest_runs`
- `backtest_trades`
- `backtest_daily_equity`
- `market_regime_snapshots`
- `decision_outcome_labels`
- `model_versions`
- `strategy_family_configs`
- `portfolio_risk_snapshots`
- `segment_health_snapshots`

Also update:
- `decision_runs` to include trigger source, schedule id, lock id, idempotency key, strategy version, and run mode,
- `decision_run_items` to include component scores,
- `paper_trades` to include strategy family and exit attribution,
- `paper_positions` to include high-water mark, ATR stop, trailing stop, and strategy family.

---

## 39) Updated Scoring Model

Replace:

`buyScore`
`sellRiskScore`
`confidenceScore`

With:

### Candidate scoring
- `trendScore`
- `momentumScore`
- `pullbackScore`
- `relativeStrengthScore`
- `volatilityScore`
- `liquidityScore`
- `regimeFitScore`
- `portfolioFitScore`
- `rewardRiskScore`
- `qualityScore`
- `finalBuyScore`

### Holding scoring
- `lossControlScore`
- `trendBreakScore`
- `relativeWeaknessScore`
- `volatilityShockScore`
- `regimeExitScore`
- `timeStopScore`
- `opportunityCostScore`
- `finalSellRiskScore`

### Decision scoring
- `tradeApprovalScore`
- `modelUncertainty`
- `dataQualityScore`

---

## 40) Better Dashboard

Upgrade the dashboard with:

### Current state
- portfolio value
- total return
- drawdown
- benchmark comparison
- cash %
- exposure %
- current regime
- circuit breaker state
- last agent run
- next scheduled run
- scheduled run status

### What is working
- profitable segments
- profitable rules
- best strategy family
- best holding period bucket

### What is failing
- losing segments
- losing rules
- worst exit reason
- worst entry score bucket

### Agent action summary
- sells today
- buys today
- skipped due to risk
- blocked due to regime
- blocked because schedule not due
- blocked due to poor reward/risk

### Research recommendations
- suggested changes,
- experiments in progress,
- latest rejected strategy,
- latest promoted strategy.

---

## 41) Acceptance Criteria

This upgrade is complete only when:

1. I can run the agent manually with **Run Agent Now**.
2. The agent automatically runs every hour by default.
3. I can change how frequently the agent runs.
4. I can disable automatic scheduled runs.
5. I can see last run, next run, run status, and scheduler warnings.
6. Scheduled and manual runs use the same agent logic.
7. Duplicate/overlapping runs are prevented.
8. I can see exactly why InvestBest has been losing money.
9. I can see P&L by segment, symbol, rule, strategy family, regime, and trigger source.
10. I can run backtests before changing defaults.
11. I can compare strategy variants.
12. I can see whether exits are helping or hurting.
13. The system has a real multi-factor regime engine.
14. The system sizes positions based on risk, not just portfolio percent.
15. The system can hold cash when conditions are bad.
16. The system supports different logic for trend, mean-reversion, defensive, and commodity trades.
17. The AI research loop proposes small testable changes, not uncontrolled rewrites.
18. Strategy promotion requires out-of-sample validation.
19. New trades include reward/risk, relative strength, regime fit, and portfolio fit.
20. Losses trigger risk reduction instead of revenge trading.
21. The app is still paper-trading unless explicitly changed later.

---

## 42) Final Cursor Instruction

Cursor should not treat this as a cosmetic improvement.

The current InvestBest strategy has lost money because it is too simple, too fixed-threshold-based, too backward-looking, not portfolio-aware enough, and not yet supported by a strong diagnostics/backtesting loop.

Cursor should implement a serious strategy upgrade focused on:

- reliable automatic scheduled agent runs,
- configurable run frequency,
- run locks and idempotency,
- diagnostics,
- attribution,
- robust backtesting,
- regime detection,
- portfolio risk,
- strategy families,
- adaptive exits,
- risk-aware sizing,
- delayed outcome labels,
- and a safer Karpathy-style research loop.

The goal is not to guarantee profits.
The goal is to build a system that learns which rules are actually working, rejects bad trades more often, sizes risk intelligently, avoids hostile regimes, runs reliably on schedule, and only promotes changes after evidence.

Build the system so bad strategies are discovered quickly, contained safely, and improved systematically.
