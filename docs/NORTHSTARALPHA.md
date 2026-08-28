# NorthstarAlpha

**The master vision, strategy, and architecture document.**

| Field | Value |
|---|---|
| **Product name** | NorthstarAlpha |
| **Repository name today** | InvestBest (`craiglutz801/investbest`) |
| **Status** | Canonical synthesis of all NorthstarAlpha ideas as of 2026-08-28 |
| **Audience** | Craig, reviewers, and any agent continuing the build |
| **Authority** | This file is the single end-to-end explanation of *what we are building and why*. Per-stage scientific details still live in the Chan roadmap and the Stage 1–6 package docs. Historical InvestBest docs are not vNext authority. |

This document gathers **everything** that has been decided, designed, and built around NorthstarAlpha: the product thesis, the architecture we want, the current InvestBest reality we must not get locked into, the investing strategies (today and next), the Chan systematic-trading principles, the academic methods added in the last 48 hours, the six-stage Chan research stack, the bounded research loop, paper-only safety, and the explicit things we refuse.

Nothing in this document is a performance claim. Simulated results are not evidence of alpha, not a live track record, and not financial advice. Live trading is out of scope until an explicit later program.

---

## 1. What we are trying to build

NorthstarAlpha is a **research-first systematic investing platform**.

The durable product is not a single hourly stock picker. The durable product is a **machine that can propose, test, falsify, and (only after evidence and a human) promote** systematic edges — then express those edges in a paper book under a RiskGovernor, with every decision reconstructable.

In one sentence:

> Never trade a pattern merely because it backtested well. Require a defensible mechanism, measurable evidence that the required market behavior exists, enough expected edge to survive friction and uncertainty, and a predefined way to detect when the thesis has broken.

That sentence is the Chan-inspired core of the system. Everything else — diagnostics, eligibility, trend/carry, health, anti-overfit gates, conservative sizing, the research loop, paper-safety, and the operator UI — exists to make that rule executable.

### What success looks like

A person sitting at the console should be able to answer, for any sleeve and any timestamp T:

1. **What did we know at T?** (point-in-time data, not wall-clock ingest time)
2. **Why was this eligible?** (mechanism + statistical property + costs)
3. **Why did risk clip, allow, or block it?** (RiskGovernor, not a heuristic `if`)
4. **What did we pay in friction, and was that inside the Edge-to-Friction budget?**
5. **Which experiments failed last month, and why did we keep those failures?**

If we cannot answer those questions, we do not have NorthstarAlpha yet. We have a paper-trading toy.

### What this is not

- Not a brokerage.
- Not a live-trading bot.
- Not an LLM that reads news and buys stock.
- Not a score-to-trade hourly cron that we keep growing until it “has Chan in it.”
- Not a beauty contest of backtests.
- Not a claim that any current rule set has alpha.

Paper execution is a **downstream consumer** of promoted strategies. It is never the research engine and never the proof of edge.

---

## 2. The one architectural move

Move from this (what InvestBest actually does today):

```text
DATA -> FEATURES -> HEURISTIC SCORES -> SELLS -> BUYS -> PAPER FILL -> DASHBOARD
```

Toward this (NorthstarAlpha):

```text
DATA
  -> POINT-IN-TIME VALIDATION
  -> FEATURES (as-of)
  -> EDGE MECHANISM          (versioned Edge Contract)
  -> STATISTICAL DIAGNOSTICS (Stage 1)
  -> STRATEGY ELIGIBILITY    (Stages 2–3)
  -> SIGNAL                  (shadow until promoted)
  -> EXPECTED EDGE AFTER COST + UNCERTAINTY HAIRCUT
  -> EDGE HEALTH / REGIME COMPATIBILITY (Stage 4)
  -> PORTFOLIO CONSTRUCTION
  -> FRACTIONAL-KELLY CEILING (Stage 5; ceiling only)
  -> RISK GOVERNOR           (authoritative)
  -> EXECUTION SIMULATION    (paper only)
  -> ATTRIBUTION
  -> HEALTH / DECAY MONITORING
  -> RESEARCH LOOP           (Stage 6; bounded)
```

**Diagnostics never place an order.** Unpromoted signals never reach the execution simulator. LLMs never appear in the call stack of scoring, sizing, or promotion verdicts.

The atomic research object is:

```text
strategy × instrument × horizon
```

Not `ticker`. Not `AppSettings.strategyMode`. Not “whatever the hourly agent happened to scan this hour.”

---

## 3. Non-negotiable rules

These are product invariants, not style preferences.

1. **Paper only until an explicit later program.** `EXECUTION_MODE=paper`. Missing or any other value fails closed. No broker SDK in the active runtime.
2. **Research is isolated from execution.** A module that can compute ADF cannot submit an order. A module that can size cannot fetch a broker clock. A module that can narrate cannot change risk limits.
3. **Point-in-time by default.** Every feature, diagnostic, and signal carries `as_of`. Storage that cannot answer “what was known at T?” is not a research store.
4. **Fail closed.** Missing, stale, partial, non-finite, misaligned, rank-deficient, or future-dated inputs produce skip / ineligible / paused — never a fill and never a silent healthy default.
5. **No LLM in money-critical arithmetic.** LLMs may propose hypotheses, critique configs, and explain artifacts. They do not score, size, promote, or discover a universe of tickers.
6. **No direct strategy-to-broker access.** Strategies emit *desired risk intents*. Execution simulation (and any future broker adapter) is a separate process.
7. **RiskGovernor is authoritative.** Diagnostics, health, and research agents may recommend throttle / pause / retire. Only RiskGovernor, plus a human merge gate for promotion, can change risk that reaches the simulator.
8. **Promotion is falsification, not a beauty contest.** The only non-reject verdict is `eligible_for_human_review`. There is no `promote_to_live`. Failed experiments are first-class records.
9. **Kelly, if used at all, is a ceiling.** Uncertainty-shrunk fractional Kelly, never full Kelly, always subordinate to vol, concentration, drawdown, exposure, liquidity, and the governor.
10. **Craig’s merge gate.** Draft PRs. Do not merge, do not deploy, do not enable live trading without explicit approval.

---

## 4. Current reality versus the destination

The git remote is still named InvestBest. NorthstarAlpha is the product we are building. Existing application code is **evidence, not authority**. Craig’s explicit concern on 2026-08-26: do not get locked into InvestBest code that previously underperformed.

### 4.1 What exists in the repo today

Four overlapping generations plus a fifth research plane:

```text
                    docs / NorthstarAlpha intent
                    (RiskGovernor, Edge Contracts, Chan Stages)
                                      │
        ┌─────────────────────────────┼──────────────────────────────┐
        ▼                             ▼                              ▼
  apps/web (V1 MVP)            InvestBest_V2                  backend + frontend
  Next.js + Prisma             Next.js + JSONB state          FastAPI + Jinja
  Twelve Data                  Yahoo + Alpha Vantage          Polygon stubs
  hourlyMarketAgent ~2300 LOC  simulator.ts ~750 LOC          Celery tasks = pass
  CURRENT PAPER PATH           PARALLEL CLEAN-ROOM            LEGACY REFERENCE
                                      │
                                      ▼
                         research/*  (Chan Stages 1–6)
                         diagnostics, mean_reversion, trend_carry,
                         edge_health, promotion, research_loop
                         ISOLATED — must stay unwired to the hourly agent
```

| Stack | What it actually is | Role going forward |
|---|---|---|
| `apps/web` | Spec-aligned paper-trading MVP. Hourly ingest / score / trade. Full Prisma schema. Real operator UI. | Most complete **product**. Weakest **research architecture**. Keep as the operator console and the temporary paper sandbox. Do not grow it into the brain. |
| `InvestBest_V2` | Isolated simulator + mock research UI. Correct *principles* in `DESIGN.md`; coded app still runs a heuristic ranker. | Keep the lifecycle vocabulary (`candidate → incubating → active → decayed`). Do not cut over to V2. |
| `backend/` + `frontend/` | Original FastAPI / Jinja experiment. Momentum backtest, notification stubs, Alpaca env flags. | Archive. Do not revive broker keys on a dead stack. |
| `apps/ml-service` | FastAPI `/score/batch` returning neutral 50/40 scores; train/backtest 501. | Freeze. Reject “call LightGBM from the hourly agent.” |
| `research/` | On `main`: Stage 1 diagnostics only. On draft PRs: Stages 2–6. | **This is the vNext research home.** |

NorthstarAlpha does not yet appear as an identifier in executable code on `main`. It exists in the Chan roadmap, the paper-validation runbook, the overnight research package names, and this document.

### 4.2 What the live paper path actually does

The current operator loop (`runHourlyMarketAgent`) is a long-only, rules-based, curated-universe paper trader:

1. Load a capped equity/ETF universe (default 28 names for Twelve Data free-tier).
2. Fetch daily OHLCV (or deterministic mock bars).
3. Compute a small feature vector: 1d/5d/20d returns, distance from SMA20/SMA50, RSI14, 20-day vol, volume spike, average dollar volume.
4. Score with one of three heuristic modes (`rules_v1`, `alpha_v1`, `regression_v1` with seeded coefficients).
5. Sell existing holdings first (stop, take-profit, trailing give-back, sell-risk, momentum break).
6. Optionally throttle new buys from SPY vs SMA50/SMA200.
7. Rank remaining buy candidates and size conservatively (cash reserve, 10% max position, whole shares, 0.05% slippage).
8. Persist `DecisionRun` / trades / positions. Optionally call OpenAI for a narrative.

There is **no** Edge Contract, **no** statistical eligibility, **no** walk-forward, **no** RiskGovernor module, **no** broker adapter, and `runMode: "dry_run"` is persisted but the pipeline still writes trades.

That loop is a **heuristic baseline / operator sandbox**. It is useful for proving paper-ops reliability. It is not the alpha architecture.

### 4.3 Top five legacy constraints that must not carry forward

1. **Monolithic hourly orchestrator as the system.** `hourlyMarketAgent.ts` (~2,300 lines) ingests, features, scores, sells, buys, shorts, sizes, snapshots, and explains in one transaction. That shape cannot host pairs, futures carry, or a RiskGovernor.
2. **Heuristic score → paper trade as the alpha architecture.** Hand-authored points and a seeded regression vector create trades. Diagnostics do not exist in the live path. This is the opposite of Chan’s eligibility-before-signal rule.
3. **Equity-only free-tier hourly loop as the universe model.** A 28-symbol cap, Twelve Data pacing, a curated 71-ticker list, and SPY SMA regime logic are operational accidents. They cannot express `strategy × instrument × horizon`.
4. **Karpathy / LLM sensitivity loop as a promotion engine.** `runKarpathyTrialLoop` mutates a disconnected `StrategySpec` and scores variants with linear perturbation, not replay. It must not become the research loop and must not self-promote `AppSettings`.
5. **Point-in-time contamination.** `FeatureSnapshot` and `ModelScore` are stamped with wall-clock ingest time, not bar time. Research built on that store will leak the future.

### 4.4 Top five pieces worth preserving

1. **Paper-only fail-closed boundary** (merged from the last 48 hours): `EXECUTION_MODE=paper`, operator pause/kill, market-data quality gate, broker-SDK isolation, reconstructable audit.
2. **Deterministic, unit-tested portfolio math and rule reason codes.** Keep as reference implementations and test oracles while replacing the orchestrator that calls them.
3. **Audit-oriented persistence nouns.** `DecisionRun`, locks, idempotency keys, trade reason codes, progress notes. Rebuild as versioned events, not a 30-column `AppSettings` blob.
4. **Chan Stages 1–6 as isolated Python libraries under `research/`.** Typed schemas, fail-closed promotion (`eligible_for_human_review` only), explicit “no broker / no position mutation” tests. Do not relocate them into `apps/web`.
5. **Operator UI surfaces** in `apps/web` (dashboard, explorer, diagnostics, settings). These are the right *surfaces*. Stop using the Next.js app as the research runtime.

---

## 5. Target architecture

If no InvestBest code existed, this is the system we would build.

### 5.1 Design principles

1. **Research is the product.** Paper trading is a consumer of promoted sleeves.
2. **Separation of concerns is a safety property**, not just a cleanliness preference.
3. **Typed, versioned, JSON-serializable contracts** at every boundary. Fail closed on unknown versions.
4. **Point-in-time by default.**
5. **Python for statistical / research workloads.** statsmodels, numpy, scipy, pandas, later PyArrow. TypeScript for the operator UI, BFF, and paper-ops API.
6. **No LLM in money-critical arithmetic.**
7. **No direct strategy-to-broker access.**
8. **Replaceable data providers.** Canonical store is vendor-neutral. Twelve Data, Polygon, Yahoo, and mock are adapters.
9. **`strategy × instrument × horizon` is the atomic object.**
10. **RiskGovernor is authoritative.**
11. **Fast isolated tests.** Pure functions, synthetic series, no Docker required for research unit tests.
12. **Optimize for the best long-term system**, not minimal diffs to `hourlyMarketAgent.ts`.

### 5.2 Two planes

```text
                         ┌─────────────────────────────────────────┐
                         │         Operator UI  (TypeScript)        │
                         │  Research · Portfolio · Risk · Execution │
                         │  Data health · Audit · Settings          │
                         └──────────────────┬──────────────────────┘
                                            │ typed HTTP / JSON contracts
┌───────────────────────────────────────────┼───────────────────────────────────────────┐
│                                           ▼                                           │
│  Research plane (Python)                          Ops plane (TypeScript + Postgres)   │
│  ──────────────────────                           ────────────────────────────────    │
│  Data catalog / PIT panels                        Paper book (cash, positions, fills) │
│  Feature as-of library                            Decision / command log              │
│  Stage 1 diagnostics                              Scheduler + locks                   │
│  Stage 2–3 eligibility / signals (shadow)         ExecutionSimulator                  │
│  Stage 4 health snapshots                         RiskGovernor (policy + limits)      │
│  Stage 5 promotion (human review only)            Market-data adapters (live quotes)  │
│  Stage 6 bounded research loop                    Notification / operator pause       │
│  Model + Edge Contract registry                                                   │
└───────────────────────────────────────────┬───────────────────────────────────────────┘
                                            │
                         DesiredPortfolioIntent (versioned)
                                            │
                         RiskGovernor.authorize()
                                            │
                         ExecutionSimulator  ──X──  Broker adapter
                                                    (does not exist;
                                                     forbidden until
                                                     an explicit program)
```

Communication rule:

```text
CLI / research job runner
    → loads PIT panels (files or research DB, not live Twelve Data inside a library)
    → calls Stage 1–5 pure functions
    → writes DiagnosticResult / Eligibility / Health / Promotion JSON artifacts
    → Stage 6 proposes bounded config diffs against Edge Contracts
    → human review

apps/web UI
    → MAY read serialized artifacts (display only)
    → MUST NOT call Python diagnostics in-process from hourlyMarketAgent
    → MUST NOT change paper positions because a p-value moved
```

### 5.3 Target repository layout (proposed; not moved in this PR)

```text
northstaralpha/                         # product name; git remote may stay InvestBest
  packages/
    contracts/                          # JSON Schema + generated TS/Py types
    ui/                                 # today’s apps/web, slimmed to operator console
  services/
    marketdata/                         # ingest, vendor adapters, PIT writer
    research/                           # job runner for Stages 1–6, walk-forward
    portfolio/                          # construction from eligible sleeves
    risk/                               # RiskGovernor
    execution-sim/                      # paper fills, costs, delay, borrow, rolls
    ops-api/                            # BFF for UI
  research/                             # KEEP the overnight packages here
    statistical_diagnostics/
    mean_reversion_eligibility/
    trend_carry/
    edge_health/
    anti_overfit_promotion/
    research_loop/
    strategy_families/                  # thin wrappers that *use* the above
  archive/                              # backend/, frontend/, InvestBest_V2, stale docs
```

| Workload | Language | Why |
|---|---|---|
| Diagnostics, eligibility, health, DSR/PBO, Kelly ceiling, walk-forward, futures term structure | Python 3.11+ | Ecosystem quality; overnight packages already here |
| Operator UI, paper book API, scheduler | TypeScript | Existing UI quality |
| Shared contracts | JSON Schema, codegen to both | Avoid a second schema war |
| Money-critical arithmetic | Never LLM | Golden tests across languages for PnL math |

### 5.4 Core contracts

#### Edge Contract (research authority)

Every strategy family eventually carries a versioned Edge Contract:

- economic / behavioral mechanism
- statistical property required for the edge
- eligible instruments and horizons
- expected holding period
- expected implementation costs (commission, spread, slippage, impact, borrow, dividend substitute, financing, futures roll)
- regimes where it should work and fail
- formation tests
- live health tests
- structural-break conditions
- retirement / throttle rules
- answers to the 19-question Chan Test (Section 8)

Identity:

```text
identity_key = strategy_family | instruments | horizon
```

#### DiagnosticResult (evidence only)

`as_of`, sample window, method, parameters, statistics, p-value, quality flags, `is_usable`. Fail flags make the result unusable for eligibility. Interpretation is never a trade.

#### EligibilityDecision / HealthSnapshot / PromotionDecision

| Object | Legal values | What it is not |
|---|---|---|
| Eligibility | `eligible` / `ineligible` / `insufficient_data` | Not an entry. Residual z-score is a later shadow step. |
| Health | `healthy` / `degraded` / `paused` / `research_retire_candidate` | Advisory. Hysteresis. Never an order. |
| Promotion | `reject` / `eligible_for_human_review` | No self-promotion. Failures are first-class. |

#### DesiredPortfolioIntent (ops)

Emitted by portfolio construction after eligibility + health + sizing ceiling:

```text
{
  schema_version,
  as_of,
  sleeve_id,                 # Edge Contract identity
  instrument_id,
  horizon,
  target_weight,             # or target_notional
  urgency,                   # next bar / next session / next roll
  constraints_applied[],     # what RiskGovernor already clipped
  signal_artifact_id         # pointer to immutable research artifact
}
```

A strategy library **cannot** emit a broker order. It can only emit this intent.

#### RiskDecision

```text
{
  intent_id,
  verdict: allow | clip | block | pause_sleeve | pause_book,
  clipped_weight?,
  reason_codes[],
  policy_version,
  governor_version
}
```

#### ExecutionReport (paper)

Fills, slippage vs arrival, unfilled remainder, cost breakdown matching Stage 1 `FrictionInputs` names so research EFR and realized ops friction are comparable.

### 5.5 RiskGovernor

A dedicated policy engine, not extra `if`s in an hourly agent.

**Inputs:** DesiredPortfolioIntent(s), current book, liquidity, borrow/roll calendars, Edge Contract throttle rules, Stage 4 health, operator pause, `EXECUTION_MODE`.

**Hard authority:**

- Gross / net exposure caps, single-name and sleeve concentration
- Volatility / drawdown throttles
- Liquidity and shortability
- Horizon conflict (do not express 12-month trend and 2-day mean reversion as one hourly slot)
- Kill switch / pause
- Fail closed on missing / stale / non-finite data
- Fractional-Kelly **ceiling** from Stage 5 — never a target, always subordinate to the limits above

**Non-authority:** inventing signals, relaxing promotion gates, calling brokers, hiding failed experiments.

Until a Python RiskGovernor service exists, the paper-safety admission gate in `apps/web` is the **temporary** governor for the legacy loop only. New Chan modules must not call it, and it must not call them.

Health may recommend `1.0` / `0.5` / `0.0`. The authorized multiplier is `min(health recommendation, governor authorization)`, clamped to `[0, 1]`. Health cannot loosen hard controls. A governor can only tighten. Missing `risk_governor_cap` fails closed at 0; nothing invents a 20% cap.

### 5.6 Execution boundary

```text
research package  ─X─►  broker SDK
strategy module   ─X─►  ExecutionSimulator
UI click          ─X─►  live order

research package  ──►  artifacts (diagnostics, eligibility, intents)
portfolio service ──►  DesiredPortfolioIntent
RiskGovernor      ──►  RiskDecision
ExecutionSimulator──►  PaperTrade / Fill  (paper only)
future BrokerPort ──►  (does not exist; requires a separate approved program)
```

---

## 6. Investing strategies

NorthstarAlpha is not “one strategy with more settings.” It is a **family of sleeves**, each with an Edge Contract, each researched at `strategy × instrument × horizon`.

### 6.1 What the current paper engine trades (baseline, not alpha)

The shipped `apps/web` engine is a long-only, explainable momentum-and-risk-control heuristic. Treat it as `baseline_heuristic_v1` — a frozen reference, not an evolving alpha.

**Universe (curated, not discovered by an LLM):**

- Large / liquid equities (AAPL, MSFT, NVDA, …)
- Defense / aerospace
- Energy
- Agriculture and soft-commodity ETF proxies
- Metals and miners
- Macro / rates / dollar / commodity proxies

**Information used:** daily OHLCV only. No fundamentals, no news in the math, no options, no shorts in the MVP path (the Shorting setting is saved and unused), no leverage.

**Buy score (`rules-v1`):** start at 50.

- +15 if 5-day and 20-day returns are both positive
- +10 if price is above SMA20 and SMA50
- +10 if RSI is between 35 and 70
- −25 if RSI ≥ 75
- −15 if volume > 2× 20-day average
- −10 if 20-day annualized vol > 35%

**Sell-risk score:** start at 30; add for 5-day return < −3%, RSI > 80, price > 5% below SMA20, volume spike on a down day.

**Buy blocks:** cash reserve, min confidence, buy-score threshold, already held (no pyramiding), vol > 60%, price > 15% above SMA20, post-sell cooldown, optional dollar-volume floor.

**Sells (first matching rule):** 8% stop, 15% take-profit, trailing give-back after halfway to target, sell-risk threshold, momentum break (5-day < −4% and RSI < 45).

**Regime:** SPY vs SMA50/SMA200 throttles new buys only. Soft mode (default) halves new buys in a bearish regime; strict mode blocks them. After paper-safety hardening, a SPY series shorter than 200 bars cannot authorize the full buy count.

**Sizing:** max 10% of portfolio, also `min(8% of port, 33% of cash)`, optional vol targeting, whole shares, 0.05% slippage, 10% cash reserve, max 3 new positions per run, target 12 holdings.

**Honest strengths:** explainable, cash-aware, not concentrated, auditable.

**Honest weaknesses:** backward-looking technicals, whipsaw in chop, no learning, no factor/correlation crowding, no real regime-conditional strategy, cannot profit from falling prices, universe is an operational accident.

This sleeve may continue to run as a **decaying-risk baseline** while real families are researched in shadow. It must not receive Chan diagnostics as new `if` statements inside the hourly agent.

### 6.2 Strategy families NorthstarAlpha is built to host

A new family adds: an Edge Contract template, the Stage 1 diagnostics it needs, an eligibility module, health rules, a cost model, and a sleeve in portfolio construction. It does **not** add another `strategyMode` string to `hourlyMarketAgent`.

| Family | Instrument | Typical horizon | Required property | Must not reuse |
|---|---|---|---|---|
| **Statistical mean reversion / stat-arb** | Economically related pairs and baskets | Half-life days | Residual stationarity, stable hedge, EFR, no structural break | RSI oversold, `bearScores`, “it fell so buy it” |
| **Multi-speed time-series trend** | Equities, futures, FX | ~1m / 3m / 6m / 12m | Persistence after vol-normalization, horizon agreement, plateau robustness | A single optimized lookback; SPY SMA50/200 as the only regime |
| **Futures carry** | Listed futures | Contract / roll cycle | Contango vs backwardation from aligned curve quotes; roll *transaction* costs separate from curve gap | Equity close-to-close features; treating `|F_next − F_front|` as friction |
| **Event** (later) | Equities | Days around earnings | Event calendar as-of | Hardcoded earnings penalties inside a simulator |
| **Legacy heuristic** | Current curated equities/ETFs | Daily / hourly ops cadence | None claimed — grandfathered baseline | New Chan families |

Trend should be a **diversified primary return engine**, not one indicator. Carry should inform **confidence** without double-counting the same exposure as trend. Mean reversion is **formation first, entry timing second**. A collapsing security that is statistically distant from a historical mean is still ineligible.

### 6.3 How a family earns the right to take risk

```text
declared mechanism
  → Stage 1: is the required statistical property present, as-of T?
  → Stage 2 or 3: is this instrument/horizon eligible?
  → EFR: does expected gross edge cover realistic round-trip friction?
  → Stage 5: does it survive cost/delay/neighborhood/walk-forward/holdout/DSR/PBO?
  → Stage 4: is it healthy now, and what would a break look like?
  → human review
  → shadow book at zero or tiny risk
  → RiskGovernor
  → paper ExecutionSimulator
  → attribution + ongoing health
  → Stage 6 may propose the *next* bounded experiment
```

If any required box is missing, the candidate is rejected or paused. Silence is not consent.

### 6.4 How we reason about “making it better”

The most valuable improvements are not “more aggressive settings.” They are better evidence, better risk control, and better research:

1. Backtests and parameter *neighborhoods*, not single-point optima.
2. Walk-forward and a sealed holdout.
3. Attribution by symbol, segment, rule, cohort, regime.
4. Portfolio risk: concentration, correlation, vol contribution, drawdown, beta, horizon mix.
5. Richer data only after it can be tested point-in-time (fundamentals, events, macro).
6. Separate sleeves instead of one generic ruleset.
7. Shorting only if borrow, locates, margin, and loss controls are real — a checkbox is not enough.

That list was already true of InvestBest. NorthstarAlpha makes it *enforceable*.

---

## 7. The Chan paper and the Chan doctrine

“The Chan paper” in this project means the durable systematic-trading doctrine associated with **Ernest P. Chan** — the body of work behind *Quantitative Trading*, *Algorithmic Trading*, and *Machine Trading* — converted into an agent-executable build sequence.

We are not implementing a single journal article titled “Chan.” We are implementing the parts of that doctrine that survive contact with costs, competition, and regime change.

### 7.1 What Chan actually contributes here

Chan’s useful residue is not a magic indicator. It is a research posture:

- **Mechanism before backtest.** Mean reversion needs a reason two (or N) series should stay related. Trend needs a reason shocks should persist. Carry needs a reason a curve should pay you for holding it. “It looked good in sample” is not a mechanism.
- **Measure the property the mechanism requires.** If you claim mean reversion, test residual stationarity, half-life, hedge stability. If you claim trend, test persistence across horizons, not one optimized SMA. If you claim carry, measure the curve, not a back-adjusted continuous series’s P&L.
- **Costs are part of the signal.** An edge that does not survive commission, spread, slippage, impact, borrow, financing, and rolls is not an edge. This is why Edge-to-Friction Ratio is a first-class Stage 1 object.
- **Half-life and holding period must match.** A two-day half-life is not a six-month trade. A twelve-month trend is not an hourly RSI scalp.
- **Hedges and parameters drift.** Rolling stability and structural-break tests exist because cointegration and trend persistence die.
- **Do not confuse a research series with executable economics.** Especially in futures: a back-adjusted continuous price is for studying trend. Listed-contract selection, rolls, and curve gaps are for studying carry and friction.
- **Do not pick the lookback that won the sweep.** Neighboring-parameter plateaus; refuse performance-sweep selection.
- **Kelly is dangerous when the mean is uncertain.** Use a shrunk fractional ceiling, then let risk limits win.
- **Keep the losers.** Multiple testing is the default state of a research loop. Count every trial.

The central sentence, again:

> Never trade a pattern merely because it backtested well. Require a defensible mechanism, measurable evidence that the required market behavior exists, enough expected edge to survive friction and uncertainty, and a predefined way to detect when the thesis has broken.

Nothing in this doctrine guarantees profits. The objective is to improve the probability of retaining genuine risk-adjusted edge while reducing false positives, overfitting, cost leakage, regime mismatch, and sizing mistakes.

### 7.2 The Chan Test (mandatory before paper promotion)

Before a strategy reaches paper promotion, it must answer these nineteen questions with evidence. If it cannot, it is not ready.

1. Why should this edge exist?
2. Who or what creates the inefficiency?
3. Why should it persist after costs and competition?
4. What measurable property must be true?
5. Is that property present out of sample?
6. Is it stable through time?
7. What is expected edge after realistic friction?
8. What happens if costs are materially higher?
9. What happens with delayed execution?
10. Does it work around neighboring parameters?
11. Does it work across multiple windows and regimes?
12. How many variants were tested before this one won?
13. Does multiple-testing-aware evaluation still support it?
14. What does a structural break look like?
15. What live metric stops new risk?
16. What regime should hurt the strategy?
17. What portfolio risk does it add?
18. What existing risk does it diversify?
19. How much capital survives uncertainty haircuts and hard risk limits?

These questions are not a blog post. They are fields on the Edge Contract and gates in Stages 1–5.

---

## 8. Papers and methods added in the last 48 hours

Between 2026-08-26 and 2026-08-27 the project absorbed a specific scientific stack. This section is the literature and method map — what was added, what it is for, and what it must not be used for.

None of these methods place an order.

### 8.1 Stationarity and unit roots

**Augmented Dickey–Fuller (Dickey & Fuller; MacKinnon p-values via statsmodels).**

- **Can:** Reject (or fail to reject) a unit-root null on a specified window and deterministic specification (`n` / `c` / `ct` / `ctt`).
- **Cannot:** Prove the series is economically mean-reverting, tradable, or cointegrated; choose a holding period; survive lag/trend misspecification.

### 8.2 Cointegration

**Engle–Granger / CADF (Engle & Granger 1987), used the way Chan uses pair residuals.**

- **Can:** Test residual stationarity of an OLS hedge of `y` on `x`; report the in-sample hedge ratio.
- **Cannot:** Guarantee the hedge is stable out of sample; identify which leg is independent; rule out spurious residual stationarity around breaks; imply a pairs trade after costs.
- **Fail-closed additions from the last 48 hours:** unequal lengths and mismatched timestamps are never truncated; they become `MISALIGNED_INPUTS`. Rank-deficient, constant, duplicate, or near-collinear panels fail closed.

**Johansen (Johansen 1991) multivariate cointegration.**

- **Can:** Report trace / max-eigen statistics, a sequential 5% trace suggested rank, and a scaled cointegrating vector.
- **Cannot:** Produce unique trading weights (vectors are identified up to scaling); supply p-values (statsmodels does not); remain reliable in short samples; authorize basket trades.

### 8.3 Mean-reversion time scale

**AR(1) / Ornstein–Uhlenbeck half-life**, the Chan-style estimator:

```text
Δy_t = μ + θ y_{t-1} + ε
half_life = ln(2) / |θ|     when θ < 0
```

- **Can:** Estimate a time scale compatible (or not) with a requested holding horizon.
- **Cannot:** Be a holding-period recommendation if the DGP is not AR(1); remain defined when `θ ≥ 0`.

### 8.4 Persistence diagnostics

**Hurst exponent** (lagged-difference variance scaling, plus a Chan-style lagged-std slope as a secondary statistic).

- H ≈ 0.5 random-walk-like; H < 0.5 anti-persistent; H > 0.5 persistent.
- **Cannot:** Provide a well-sized p-value in this implementation; overcome short-sample bias; establish a tradable edge.

**Lo–MacKinlay overlapping variance ratio (Lo & MacKinlay 1988).**

- **Can:** Estimate VR(q) on first differences with homo- and heteroskedastic z-statistics.
- **Cannot:** Translate VR ≠ 1 into a strategy; choose q uniquely; incorporate costs.

### 8.5 Stability and breaks

**Rolling ADF, half-life, OLS hedge ratio, residual volatility** on point-in-time windows that never peek past the window end.

- **Cannot:** Treat overlapping windows as independent tests; prove future stability; emit orders when a window “looks stationary.”

**Structural-break contract.**

- `chow_ols` — Chow F at a pre-specified split, or a max-F scan flagged `break_date_estimated` (p-value then anti-conservative).
- `cusum_ols_resid` — Ploberger–Kramer CUSUM of OLS residuals.
- **Can:** Evidence of coefficient / mean instability.
- **Cannot:** Name the economic cause; act as a stop; replace Stage 4 health.

### 8.6 Implementation realism

**Edge-to-Friction Ratio (project-defined, Chan-inspired):**

```text
EFR = expected_gross_edge / expected_round_trip_friction
```

Friction components: commission, spread, slippage, market impact, borrow fees, dividend substitutes, financing, futures *execution* roll, other.

Research default: label EFR < ~2.5 as fragile (configurable). EFR does not create trades and does not prove the numerator is a real edge. Zero, negative, NaN, or Inf friction fails closed.

**Last-48-hour correction that matters:** in futures, the front/deferred **curve gap is carry, not friction**. Treating `|F_next − F_front| / |F_front|` as `futures_roll` would double-count the same economic effect (once as carry, again as a cost). Execution roll friction is bid/ask half-spreads on the two roll legs when both books exist; otherwise it is unknown.

### 8.7 Multiple-testing-aware promotion

**Deflated Sharpe Ratio — Bailey & López de Prado (2014).**

Two different variance quantities, corrected on 2026-08-27 after review:

1. `V[{SR_n}]` — **cross-sectional** variance of Sharpe ratios across tried trials. This scales the False Strategy expected-max threshold `SR0`.
2. The selected strategy’s skew/kurtosis sampling-error term — PSR/DSR **denominator only**. Never used as `V[{SR_n}]`.

```text
SR_hat = mean(r) / std(r, ddof=1)          # per-period, not annualized

denom  = sqrt(1 - γ3·SR_hat + ((γ4-1)/4)·SR_hat²)
V[{SR_n}] = Var(trial Sharpes, ddof=1)
SR0    = sqrt(V[{SR_n}]) · [(1-γ) Φ⁻¹(1-1/N) + γ Φ⁻¹(1-1/(N e))]
DSR    = Φ[(SR_hat - SR0) · sqrt(n_obs-1) / denom]
```

- N = 1 → SR0 = 0, DSR = PSR(0).
- N > 1 → must pass `trial_sharpes` (length N, all finite) or `sharpe_trials_variance`. `returns + n_trials` alone is not enough.
- More trials **or** wider trial-Sharpe dispersion raise SR0 and reduce DSR.
- Assumption: given `V[{SR_n}]`, trials are treated as independent. Positive correlation among nearby parameterizations **understates** SR0.

**Probability of Backtest Overfitting / CSCV — Bailey, Borwein, López de Prado, Zhu (2014).**

1. Split T bars into S even contiguous slices (S ≥ 4 even).
2. Every combination of S/2 slices is IS; the complement is OOS.
3. Pick the IS-best strategy.
4. Relative OOS rank λ; PBO = Pr(λ < 0.5).

Universe is **fixed before CSCV**. Columns whose full-sample Sharpe is undefined are excluded once. Combinations do not drop strategies mid-flight — that fails closed.

### 8.8 Conservative sizing

**Uncertainty-shrunk fractional Kelly (ceiling, not target):**

```text
f_full   = μ / σ²
t        = μ / se(μ)
s        = t² / (t² + ν)                 # default ν = 1
μ_shrunk = s · μ
f_frac   = α · (μ_shrunk / σ²)           # default α = 0.25; α ≥ 1 rejected

f_ceiling = min(f_frac, f_vol, f_conc, f_exp, f_liq, f_RG, f_hard) · τ_DD
```

Role is always `ceiling_not_target`. Missing `risk_governor_cap` is not unlimited capacity.

Informational trial-count haircut: `h = 1 / sqrt(N_trials)`.

### 8.9 Cost, delay, concentration, holdout

- Cost stress: `net = gross − m · cost` with m ∈ {1.0, 1.5, 2.0} (baseline, +50%, +100%). One failed scenario vetoes.
- Delay stress: positions shifted forward by d bars (later fill, no lookahead).
- Concentration: Herfindahl–Hirschman and top-k shares on positive P&L mass.
- Holdout: sealed research window, optional embargo, untouched holdout. Any trial that touches holdout is contamination and fail-closed.

### 8.10 Paper citations (compact)

| Method | Canonical source | Where NorthstarAlpha uses it |
|---|---|---|
| Chan systematic-trading doctrine | Ernest P. Chan, *Quantitative Trading* / *Algorithmic Trading* / *Machine Trading* | Entire roadmap, Edge Contract, Chan Test |
| ADF | Dickey & Fuller; MacKinnon critical values | Stage 1, Stage 2, Stage 4 |
| Engle–Granger / CADF | Engle & Granger (1987) | Stage 1, Stage 2, Stage 4 |
| Johansen | Johansen (1991) | Stage 1, Stage 2 baskets |
| OU / AR(1) half-life | Standard; Chan’s applied form | Stage 1, Stage 2, Stage 4 |
| Hurst | Hurst (1951); applied as a diagnostic | Stage 1 |
| Variance ratio | Lo & MacKinlay (1988) | Stage 1 |
| Chow | Chow (1960) | Stage 1 break contract |
| CUSUM of OLS residuals | Ploberger & Kramer | Stage 1 break contract |
| Time-series momentum ensemble | Moskowitz, Ooi, Pedersen (2012) and related TSMOM literature, implemented as multi-speed 1m/3m/6m/12m | Stage 3 |
| Deflated Sharpe | Bailey & López de Prado (2014) | Stage 5, Stage 6 harness |
| PBO / CSCV | Bailey, Borwein, López de Prado, Zhu (2014) | Stage 5 |
| Kelly criterion (fractional, shrunk) | Kelly (1956); applied conservatively | Stage 5, Stage 6 sizing adapter |

This is the literature that landed as **code and contracts** in the last 48 hours. It is not a reading list for later. It is already in `research/*` on the Chan branches.

---

## 9. The six Chan stages

Each stage is an isolated Python library under `research/`. Each has isolation tests that forbid broker/order APIs and imports from `hourlyMarketAgent`. Each is draft-PR only unless Craig approves a merge. Diagnostics remain evidence.

Build order is 1 → 2 → 3 → 4 → 5 → 6. Paper-safety was developed in parallel because it lives in `apps/web` and must not share files with Chan packages.

### Stage 1 — Statistical diagnostics foundation

**Package:** `research/statistical_diagnostics` (`northstar_diagnostics`)
**On `main`:** yes (merged). **Tests:** 65 passed at head `d2b3218`.

The kernel. Pure functions, common `DiagnosticResult` schema (timestamps, formation window, method, parameters, library versions, statistics, p-value, critical values, hypotheses, assumptions, quality flags, interpretation that is explicitly not a trade).

Public API: `adf_stationarity`, `cadf_cointegration`, `johansen_cointegration`, `mean_reversion_half_life`, `hurst_diagnostic`, `variance_ratio_diagnostic`, `rolling_stationarity`, `rolling_parameter_stability`, `detect_structural_break`, `edge_to_friction_ratio`.

Dependencies: numpy, scipy, statsmodels. No broker SDK.

Why Python, not TypeScript: ADF / Engle–Granger / Johansen are mature in statsmodels. Reimplementing them in JS would add correctness risk. Why not `apps/ml-service`: that stub may later be called from the hourly agent; putting diagnostics there would make accidental trade-path coupling easy.

### Stage 2 — Mean-reversion eligibility engine

**Package:** `research/mean_reversion_eligibility` (`northstar_mean_reversion`)
**PR:** #11 (draft). **Tests:** 39 passed at head `55e2af7`.

Do not treat generic oversold / overbought as mean reversion.

Two questions that must not be collapsed:

1. **Formation / eligibility** — is this economically related pair or basket a statistically defensible mean-reversion *candidate* on a point-in-time window?
2. **Entry timing** — is the residual currently extended (z-score)? Applied only in `evaluate_shadow_entry`, and only if (1) already passed.

The engine does **not** discover a universe and does **not** accept LLM ticker lists. Callers must supply `EconomicCandidate` groups with a declared `RelationshipKind` and a non-empty economic rationale.

Gates (all fail closed): economic universe declaration, PIT market data (equal-length, date-aligned), event / fundamental veto flags, liquidity / shortability snapshots, CADF (pairs) or Johansen (baskets), residual ADF, hedge-ratio stability, spread-vol stability, half-life vs requested horizon, structural-break veto, EFR / cost cushion.

Broken cointegration is flagged when CADF passes in the first half of the window and fails in the second (`BROKEN_COINTEGRATION`). Stage 1 fail-closed CADF alignment is inherited.

`evaluate_shadow_entry` may report `SHADOW_ENTRY_OBSERVED` with `long_spread` / `short_spread`. That payload is `is_production_signal=False`.

Deviation worth knowing: structural-break veto defaults to CUSUM at **1%** (Stage 1 detector default is 5%) to reduce false vetoes on genuine cointegrated baskets.

### Stage 3 — Multi-speed trend + futures carry

**Package:** `research/trend_carry` (`northstar_trend_carry`)
**PR:** #10 (draft). **Tests:** 67 passed at head `40a41e4`.

Trend is a diversified primary return engine. Carry is complementary context. The module will not select a single optimized lookback.

Ensemble (defaults ≈ 21 / 63 / 126 / 252 trading days):

```text
raw_return = P[t] / P[t-L] - 1
daily_vol  = stdev(log-returns over vol_lookback, ddof=1)
strength   = raw_return / (daily_vol * sqrt(L))
capped     = clip(strength, -signal_cap, +signal_cap)
ensemble   = mean(usable capped strengths)
```

`ensemble_method` is always `equal_weight_capped_horizons`. `selected_lookback` is always `None`. `refuse_performance_sweep_selection` exists so a later agent cannot “just take the winner.”

`allow_short` only controls **research expression**. It is not broker permission.

Two futures objects that must stay separate:

| Object | Use | Must not be used as |
|---|---|---|
| `ResearchContinuousSeries` | Trend research on a back-adjusted path (`not_executable_pnl=True`) | Trade P&L, margin, or an order |
| `ExecutableContractEconomics` | Front contract, DTE, roll direction, **curve/roll gap** (carry), execution roll friction if bid/ask exist | A continuous price series or a broker instruction |

Carry snapshots fail closed when roots mismatch, quotes are older than `max_quote_age` (default 3 days), or front/deferred timestamps differ by more than `max_front_next_skew` (default 1 day).

Health ingredients (horizon agreement, persistence, whipsaw, vol shock, breadth) are **research tags**. Stage 4 owns formal throttle / pause / retire.

### Stage 4 — Edge health + structural-break monitoring

**Package:** `research/edge_health` (`northstar_edge_health`)
**PR:** #13 (draft). **Tests:** 69 passed at head `75146a5`. Schema `4.0.0`.

Creates explicit health states per strategy family. Health metrics may later throttle sleeve risk within pre-approved bounds. They do not authorize unrestricted AI discretion.

| State | Default advisory multiplier | Meaning |
|---|---|---|
| `healthy` | 1.0 | Required live properties are inside research bands |
| `degraded` | 0.5 | Edge is weakening |
| `paused` | 0.0 | Stop **new** risk from this sleeve in research logic |
| `research_retire_candidate` | 0.0 | Thesis looks broken; candidate for retirement review |

**Hysteresis:** soft degraded / paused need consecutive confirmations so one noisy bar does not flap. Hard pause (structural break, fail-closed missing evidence, trend vol shock) enters immediately. Recovery requires cooldown then consecutive healthy observations. A pause that persists becomes a retire candidate. Reason codes record why emitted state lagged instantaneous state.

Mean-reversion evidence: rolling ADF/CADF, half-life drift, hedge-ratio drift, residual-vol change, convergence rate, Stage 1 break flag, realized vs expected friction. Thesis-broken = break **and** half-life undefined/extreme **and** extreme friction or residual vol.

Trend evidence: horizon sign agreement, persistence, whipsaw, vol shock, realized implementation cost, cross-market breadth. Thesis-broken = vol shock **and** extreme whipsaw **and** extreme breadth.

`apply_advisory` never mutates positions, never raises a governor bound, always keeps `subordinate_to_risk_governor=True`. `HealthSnapshot.may_create_order` and `may_mutate_positions` are always false.

Unusable Stage 1 results are omitted rather than treated as healthy, and recorded under `evidence.extra["unusable_stage1"]`.

There is still no production `RiskGovernor` on `main`. Stage 4 defines a `RiskGovernorPort`. It does not implement or weaken one.

### Stage 5 — Anti-overfit promotion + conservative sizing

**Package:** `research/anti_overfit_promotion` (`northstar_promotion`)
**PR:** #14 (draft). **Tests:** 60 passed at head `4ac1fa0`.

Make backtesting a falsification process.

Every serious candidate is attacked with:

- point-in-time formation windows
- realistic costs and cost stress (+50%, +100%)
- execution-delay stress
- parameter-neighborhood / plateau tests (isolated optimum fails)
- multiple formation windows
- walk-forward evaluation
- untouched final holdout
- regime slices
- trade / P&L concentration
- explicit experiment / trial counting (failures retained)
- DSR and PBO / CSCV
- shadow-forward contract flag

Default verdict is `reject`. The only other verdict is `eligible_for_human_review`. There is no `promote_to_paper` or `promote_to_live`.

Public API: `ExperimentRegistry`, `formation_windows`, `walk_forward_splits`, `seal_holdout` / `audit_holdout`, `evaluate_plateau`, `cost_stress` / `execution_delay_stress`, `trade_pnl_concentration`, `evaluate_regime_slices`, `deflated_sharpe_ratio`, `probability_of_backtest_overfitting`, `kelly_ceiling`, `evaluate_promotion`.

This — not the Karpathy `trialPromotionGate` (composite margin 0.015), not `AppSettings.strategyMode` — is promotion authority.

### Stage 6 — Bounded research loop

**Package:** `research/research_loop` (`northstar_research_loop`)
**PR:** #12 (draft, **temporary integration checkout — not the merge path to `main`**). **Tests:** 49 passed; combined native harness **349 passed** and `CHAN_HARNESS_OK`.

This is the Chan research loop. It is the control plane that sits on top of Stages 1–5. It is **not** the Karpathy sensitivity loop, and it is **not** allowed to become one.

#### What the loop may do

- Propose hypotheses as **bounded** experiment proposals
- Compare diagnostics
- Identify broken assumptions
- Create controlled experiments
- Summarize attribution
- Propose bounded config changes on an allow-list: `strategy_config`, `thresholds`, `feature_set`, `formation_window`, `health_settings`

#### What the loop must not do

- Free-form trades from news
- Bypass risk rules
- Self-approve live deployment, merge, or paper activation
- Optimize only recent P&L
- Hide failed experiments
- Change broker / execution safety code as part of a strategy experiment
- Invent missing governor caps
- Call Stage 1–5 through `getattr` name-guessing or a silent synthetic fallback

#### Pipeline

```text
proposal + Edge Contract
  -> Stage 1 diagnostics
  -> Stage 2 eligibility
  -> after-friction (EFR + cost stress)
  -> Stage 5 robustness / anti-overfit
  -> Stage 4 health
  -> Stage 5 conservative sizing ceiling (advisory)
  -> state machine
  -> append-only registry (winners and failures)
```

Legal candidate statuses: `proposed`, `rejected`, `research-qualified`, `shadow-ready`, `paused`, `retired`. **There is no `live` status.**

Native APIs the harness is required to call:

| Stage | Function |
|---|---|
| 1 | `cadf_cointegration`, `edge_to_friction_ratio` |
| 2 | `evaluate_candidate(candidate, *, config=)` |
| 3 | `evaluate_asset_trend`, `refuse_performance_sweep_selection` |
| 4 | `HealthMonitor.evaluate(evidence, *, identity=)` |
| 5 | `evaluate_promotion`, `kelly_ceiling`; DSR via registry `trial_sharpes` |

`require_native_stages()` fails the harness if any required package is missing.

Sizing: health multiplier applied **once** after `kelly_ceiling` (not also injected as `drawdown_throttle`). Missing `risk_governor_cap` returns a 0 ceiling.

#### Morning harness scenarios (synthetic, no secrets)

| Scenario | Expected status | Why |
|---|---|---|
| `good_candidate` | `shadow-ready` | Mechanism + stats + EFR + robustness + health |
| `overfit_candidate` | `rejected` | `ISOLATED_OPTIMUM`, `HOLDOUT_CONTAMINATION` |
| `high_friction_candidate` | `rejected` | `insufficient_efr` |
| `structurally_broken_candidate` | `paused` | `mr.structural_break` |
| `statistically_invalid_candidate` | `rejected` | Stage 2 formation gates |

Observed on the integration checkout: `places_trade: false`, `promotes_to_live: false`, 1 retained winner, 4 retained failures, all five adapters `adapter_mode: native`.

One command:

```bash
bash research/run_chan_research_tests.sh
python3 -m northstar_research_loop
```

Do **not** run all six pytest directories in one invocation; several packages ship `tests/test_isolation.py`.

After morning review, keep Stage 2–5 ownership on PRs #11 / #10 / #13 / #14. Do **not** merge the Stage 6 integration checkout to `main`.

---

## 10. The Chan research loop versus the older Karpathy loop

The repo already contains a Karpathy-style improvement-loop design (`docs/InvestBest_Karpathy_Loop_Addendum.md` and an unwired `runKarpathyTrialLoop`). That design was the right *instinct* and the wrong *object*.

### 10.1 What the Karpathy addendum got right

- Split the system into **Loop A (operator / paper trader)** and **Loop B (researcher)**.
- Agents propose small, testable changes; they do not freely control money.
- Promotion is gated. The improvement loop improves the operator loop; it does not replace it.
- LLMs are for hypothesis generation and explanation, not unaudited trading decisions.
- Bounded mutation surface (a `StrategySpec` + Zod schema) rather than arbitrary code rewrite.

### 10.2 Why it must not become NorthstarAlpha’s research loop

| Karpathy loop (InvestBest) | Chan research loop (NorthstarAlpha) |
|---|---|
| Mutates hourly-rule knobs (`StrategySpec` thresholds, segments, search profiles) | Mutates Edge Contract fields on an allow-list |
| Scores variants with linear perturbation / sensitivity, not replay | Scores through Stages 1–5: diagnostics, eligibility, EFR, DSR/PBO, holdout, health |
| `trialPromotionGate` composite margin 0.015 | Fail-closed `evaluate_promotion`; max verdict `eligible_for_human_review` |
| Not a backtest; not wired to any API | Deterministic pipeline + append-only registry + synthetic harness |
| Risk of self-promoting `AppSettings` | Agent capability bitmap cannot place a trade, bypass risk, self-merge, self-deploy, or self-promote |
| One `strategyMode` | `strategy × instrument × horizon` |

Keep the planner / critic / narrator **as explanation** over research artifacts. Replace the scoring and promotion path with Stage 6 + Stage 5. Do not merge the two promotion concepts.

The world-class review’s Research Lab / Portfolio & Risk Studio / Execution Center / Portfolio Review information architecture is still the right *feel* for the UI. The engine behind Research is now Chan Stages 1–6, not a FastAPI momentum backtest.

---

## 11. Paper-only safety and validation (last 48 hours)

Paper-safety and Chan research meet only at three shared rules:

1. Forbidden broker.
2. Diagnostics are not orders.
3. Eventually, RiskGovernor reading health + intents.

They should not share files. If they touch the same file, paper-safety wins for `apps/web`, Chan wins for `research/`.

### 11.1 What landed on `main`

Merged PR #2, with a temporal-integrity correction (`4bb2210`):

- Fail-closed `EXECUTION_MODE=paper`. Missing, empty, `live`, or any other value cannot start a run or mutate simulated positions.
- Operator pause (`AppSettings.agentPaused`) and emergency kill (`AGENT_PAUSE` / `AGENT_KILL_SWITCH`). History is kept. Un-pausing does not backfill skipped hours.
- Market-data quality gate. Invalid data produces auditable skip / no-trade, never a fill.
- Reconstructable audit on `DecisionRun.notesJson.audit`.
- Run lock + hourly idempotency; duplicate or concurrent triggers cannot create a second trade set.
- Legacy Alpaca / IB config under `config/` and `backend/` documented as unused isolation leftover. Do not wire it.
- Long-only curated-universe strategy and shipped risk defaults unchanged.

Fail-closed data classes:

| Code | Meaning |
|---|---|
| `MISSING_BARS` | No usable series |
| `STALE_BARS` | Last bar too old (only after chronological check) |
| `NON_FINITE` | NaN / Inf prices |
| `INCONSISTENT_OHLC` | High/low/open/close relationships broken |
| `PARTIAL_SERIES` | Including missing or nonpositive volume (volume is not coerced to 0) |
| `DUPLICATE_BARS` | Duplicate timestamps |
| `OUT_OF_ORDER_BARS` | Not strictly chronological |
| `FUTURE_BARS` | Materially in the future (36h slack for daily session labeling) |
| `MISSING_QUOTE_TIMESTAMP` | Quote without provider timestamp cannot mark a holding fresh |
| `FUTURE_QUOTE` | Materially future quote (2h slack for clock skew) |

SPY SMA200: new buys require 200 bars *and* a real `sma200`. A 50–199 bar series can still classify as soft-mode “neutral”; that no longer authorizes the full buy count.

### 11.2 Operator validation path

Documented in `docs/PAPER_VALIDATION_RUNBOOK.md`.

**Shipped risk defaults (frozen for the soak):** $100k starting cash, 10% max position, 10% cash reserve, 3 new positions/run, 8% stop, 15% take-profit, 24h cooldown, 0.05% slippage.

**Ten-trading-day reliability soak.** Goal: prove the paper engine stays fail-closed, auditable, and single-flight under real scheduler load. Pass criteria include zero non-paper runs, zero broker-order attempts, invalid data never fills, SMA200 and quote-timestamp rules hold, duplicate triggers produce at most one trade set, and at least one sampled fill reconstructs from persisted audit fields.

**Later 90-day shadow cohort.** Same long-only engine, risk defaults frozen, no strategy optimization, no LLM trade decisions. Output is operational reliability + reproducibility. Equity curve is **not** a performance claim.

Stop-the-line: any live-mode config, any broker SDK import, duplicate fills, or a trade from invalid data.

---

## 12. KEEP / ADAPT / REPLACE / ARCHIVE

Legend: **KEEP** reuse as-is. **ADAPT** reuse the idea/tests; rewrite the wiring. **REPLACE** do not use as the long-term design. **ARCHIVE** stop developing; move later. Nothing is deleted by this document.

| Module | Decision | vNext destination |
|---|---|---|
| Twelve Data client | ADAPT | One adapter under `MarketDataPort`; strip 7.5s sleep into a rate limiter |
| Inline `mockBars()` in the hourly agent | REPLACE | First-class `MockMarketDataProvider` with bar-time timestamps |
| V2 Yahoo + Alpha Vantage | ADAPT | Earnings as `EventDataPort`; Yahoo research-only, never canonical |
| Backend Polygon client | ADAPT | New Python market-data adapter |
| Finnhub env var | ARCHIVE | Revisit only for a news/event port |
| `MarketSnapshot` (bar time) | ADAPT | Canonical PIT bar store `(instrument, ts, vendor, as_of)` |
| `FeatureSnapshot` / `ModelScore` (`new Date()`) | REPLACE | Feature as-of bar timestamp; scores as versioned artifacts |
| `IndicatorSnapshot` (never written) | ARCHIVE | Drop |
| PostgreSQL | KEEP | Operator state, audit, paper books |
| Prisma `DecisionRun` / trades / locks | ADAPT | Split ops schema vs research schema |
| Demo `requireDefaultUser()` | REPLACE | Fine for a personal MVP; not a platform identity model |
| V2 JSONB portfolio blob | REPLACE | Not an auditable book |
| `apps/web` UI chrome | KEEP | Operator console |
| V2 Research / Experiments / Candidates / System pages | ADAPT | Rebuild against real contracts |
| Jinja `frontend/` | ARCHIVE | Freeze |
| `math.ts` portfolio math | KEEP | Shared simulator kernel; golden tests |
| `sizing.ts` | ADAPT | Sizing is a RiskGovernor input |
| Paper fills inside the hourly agent | REPLACE | `ExecutionSimulator` service |
| V2 `simulator.ts` | ADAPT | Keep exits → candidates → size → persist; drop hardcoded constants |
| Scheduler locks / market-hours | KEEP | Ops scheduler; add a separate research job runner |
| `RunMode` union | ADAPT | Enforce `dry_run` / `shadow` / `backtest` for real |
| Vercel Hobby daily cron as architecture | ARCHIVE | Do not design horizons around hosting accidents |
| Paper-safety `auditTrail.ts` | KEEP | Feed RiskGovernor + UI |
| `rulesScores` / `alphaFoundationScores` / `bearScores` | REPLACE (as alpha) | Freeze as `baseline_heuristic_v1` |
| `apps/ml-service` as live oracle | REPLACE | Offline research artifact, promoted through Stage 5 |
| Buy / sell / short reason codes | ADAPT | Fold into RiskGovernor + sleeve policy |
| `applyLongUniversePolicy` hidden alpha | REPLACE | If real, it becomes an Edge Contract; else frozen heuristic |
| Hardcoded agent constants | REPLACE | Versioned `RiskPolicy` |
| Bounded `StrategySpec` | ADAPT | Replace object with Edge Contract mutation targets |
| `runKarpathyTrialLoop` / `applyTrialSensitivity` | REPLACE | Stage 6 + Stage 5 |
| `trialPromotionGate` | REPLACE | Do not merge with Stage 5 |
| Planner / critic / narrator | ADAPT | Read-only over artifacts |
| Seeded `regression_v1` coefficients | REPLACE (as a model) | Dummy for UI demos only |
| V2 `ModelStage` vocabulary | KEEP | Canonical lifecycle |
| Backend momentum + `BacktestService` | ADAPT | Port ideas into `research/strategy_families/trend` |
| Celery `pass` tasks, Alpaca flags on dead stack | ARCHIVE | Secrets belong to future execution adapters |
| **Chan Stages 1–6** | **KEEP** | Remain pure Python libraries |
| Chan integration roadmap | KEEP | Scientific sequence; this file places it |

---

## 13. Migration / strangler plan

Goal: reach vNext **without** a big-bang rewrite and **without** teaching Chan modules to speak hourly-agent. Strangle by **contract**, not by wrapping the 2,300-line function.

### Phase A — Freeze the legacy loop as a baseline sleeve (now)

- Leave `apps/web` paper trading running as heuristic baseline / operator sandbox.
- Do **not** add Chan imports, LightGBM, or Karpathy promotion into `hourlyMarketAgent.ts`.
- Keep paper-safety fail-closed.
- Keep Chan Stages 1–6 in `research/*` as isolated libraries.
- Snapshot the heuristic as experiment `baseline_heuristic_v1` once the Stage 5 registry exists.

### Phase B — Contracts and PIT store (first structural work)

- `packages/contracts` generated from the overnight Python dataclasses / JSON.
- PIT bar writer: unique `(instrument, timestamp, vendor)`, as-of, no wall-clock feature stamps.
- Adapter-wrap Twelve Data and Polygon. Stop importing vendors from the orchestrator.
- Extract `ExecutionSimulator` from the agent: same math tests, new caller.
- Wrap heuristic scores as a `LegacyHeuristicSleeve` that emits `DesiredPortfolioIntent` instead of writing trades.

### Phase C — Research plane becomes authoritative for *new* sleeves

- Stage 2–3 shadow signals write artifacts only.
- Stage 4 health visible in UI (read-only).
- Stage 5 human-review queue is the only promotion path for new families.
- Portfolio construction can combine: `legacy_heuristic` sleeve (capped, decaying risk budget) + shadow sleeves at **zero** live risk.

### Phase D — RiskGovernor owns the book

- All intents, including the legacy sleeve, pass RiskGovernor.
- Hourly agent becomes a thin “legacy sleeve runner” or is deleted.
- UI reads research + ops contracts, not Prisma JSON blobs for scores.

### Phase E — Archive and rename

- Move `backend/`, `frontend/`, `InvestBest_V2`, root `ARCHITECTURE.md` / `DESIGN_SPECIFICATION.md` to `archive/` (separate hygiene PR).
- Rename product strings to NorthstarAlpha. Repository rename is a later ops decision.

### Explicit reuse classification

| Reuse unchanged | Wrap behind adapters | Rewrite | Retire |
|---|---|---|---|
| Paper-only policy, kill switch | Twelve Data / Yahoo / Polygon clients | `hourlyMarketAgent` control flow | Seeded regression as alpha |
| Unit tests for math + rule reason codes | Scheduler heartbeat | Feature store timestamps | Karpathy sensitivity gate |
| Decision / trade / position **nouns** | Heuristic scores as `LegacyHeuristicSleeve` | AppSettings as strategy | Celery stubs, Jinja UI |
| Chan research packages (as libraries) | V2 simulator loop shape | Portfolio construction / risk | Unused `packages/shared` tickers |
| Next.js operator chrome | Prisma paper book during B–C | Promotion (use Stage 5) | Checked-in `.venv`, `investbest.db` |

---

## 14. Operator / research information architecture

When the console is retargeted, navigate by workflow, not by leftover page names:

| Area | Job |
|---|---|
| **Home** | Book snapshot, governor state, last paper run, data freshness, paused sleeves |
| **Research** | Edge Contracts, experiments, diagnostics, walk-forward tear-sheets, failed trials |
| **Eligibility** | Stage 2–3 candidate sets; why ineligible |
| **Health** | Stage 4 states; structural breaks; decay |
| **Promotion** | Human-review queue (Stage 5); never a green “deploy live” button |
| **Portfolio** | Sleeve weights, concentration, horizon mix |
| **Execution (paper)** | Intents, risk decisions, fills, costs vs expected friction |
| **Data** | Vendor health, PIT coverage, corporate actions, roll calendars |
| **System** | `EXECUTION_MODE`, kill switch, scheduler locks, audit log |

V1 already has pieces of Home / Execution / System. V2 mock pages sketch Research. Neither has Eligibility, Health, or a real Promotion queue.

---

## 15. Decisions this architecture refuses

| Tempting shortcut | Why we refuse |
|---|---|
| “Just call Stage 1 from the hourly agent so Chan is integrated” | Couples science to a free-tier equity cron and makes diagnostics into trade switches |
| “Wire ml-service LightGBM next; it’s Milestone 2” | Trains on a contaminated feature store and keeps score → trade |
| “V2 is the rewrite, cut over” | V2 simulator is still heuristic; research UI is mock |
| “Revive FastAPI + Alpaca from `config/settings.py`” | Broker keys on a dead stack; violates paper-only |
| “Karpathy loop promotes AppSettings” | Sensitivity ≠ validation; LLM adjacent to money |
| “One `strategyMode` enum to rule them all” | Cannot represent horizon or instrument class |
| “JSON blob for the whole book” (V2) | Not auditable, not reconcilable |
| “Minimal diffs to `hourlyMarketAgent`” | Explicitly rejected |
| “Treat the futures curve gap as roll friction” | Double-counts carry as a cost |
| “DSR from `returns + n_trials` when N > 1” | `SR0` needs cross-trial Sharpe variance |
| “Invent a 20% governor cap when none was supplied” | Missing authority must fail closed at 0 |
| “Merge the Stage 6 integration checkout to `main`” | It is a temporary assembly of other people’s packages |

---

## 16. Repo hygiene (proposed only; nothing deleted here)

| Issue | Proposed later action |
|---|---|
| Checked-in `.venv/` (~139 MB) | `git rm -r --cached .venv`; root `.gitignore` |
| Checked-in `investbest.db` | Untrack; local artifact |
| Checked-in `.DS_Store` | Untrack |
| No root `.gitignore` | Add `.venv/`, `*.db`, `.env`, `.DS_Store`, `node_modules`, `.next` |
| Duplicate apps | `apps/web` = operator UI; `research/` = science; V2 and FastAPI → `archive/` after extracting useful tests |
| Duplicate architecture docs | **This file** is the NorthstarAlpha end-to-end authority. Stamp `docs/ARCHITECTURE.md`, root `ARCHITECTURE.md`, and `DESIGN_SPECIFICATION.md` as historical. Chan roadmap remains the scientific sequence. `docs/NORTHSTARALPHA_VNEXT_ARCHITECTURE.md` (PR #16) remains the placement/strangler audit. |
| Naming | Gradual rename: UI chrome first, env prefixes `NORTHSTAR_*` with aliases for `INVESTBEST_*`, repo rename last |
| `render.yaml` `db:seed` on hourly cron | Stop seeding production on cron |
| Prisma raw-SQL fallbacks | Delete the pattern when the schema is stable |

---

## 17. Current build status (as of 2026-08-28)

Overnight 2026-08-26 → morning 2026-08-27 was an approved bounded push. Morning testing was the target. Merge remains Craig’s gate.

```text
main
 ├── PR #2   paper-only safety           MERGED
 │     EXECUTION_MODE, pause/kill, data-quality, audit, locks
 │
 ├── PR #4   Stage 1 diagnostics         MERGED
 │     research/statistical_diagnostics  (northstar_diagnostics)  65 tests
 │     ├── PR #11 Stage 2 eligibility    DRAFT
 │     │     northstar_mean_reversion    39 tests
 │     └── PR #13 Stage 4 edge health    DRAFT
 │           northstar_edge_health       69 tests
 │
 ├── PR #10  Stage 3 trend/carry         DRAFT
 │     northstar_trend_carry             67 tests
 │     curve gap = carry; futures_roll = execution friction only
 │
 ├── PR #14  Stage 5 anti-overfit        DRAFT
 │     northstar_promotion               60 tests
 │     DSR N>1 requires trial_sharpes or sharpe_trials_variance
 │
 ├── PR #12  Stage 6 research loop       DRAFT, NOT the merge path
 │     copies Stages 1–5 for a native morning harness
 │     49 Stage 6 tests; 349 combined; CHAN_HARNESS_OK
 │
 └── PR #16  vNext architecture          DRAFT, docs only
       docs/NORTHSTARALPHA_VNEXT_ARCHITECTURE.md
```

| Stage | Issue | PR | Branch | On `main`? |
|---|---|---|---|---|
| Paper safety | #1 | #2 | `cursor/paper-only-safety-hardening-072f` | Yes |
| Diagnostics | #3 | #4 | `cursor/chan-stage1-statistical-diagnostics-fd6c` | Yes |
| Mean reversion | #5 | #11 | `cursor/chan-stage2-mean-reversion-eligibility-7dee` | No |
| Trend + carry | #6 | #10 | `cursor/chan-stage3-trend-carry-1042` | No |
| Edge health | #7 | #13 | `cursor/chan-stage4-edge-health-136d` | No |
| Anti-overfit | #8 | #14 | `cursor/chan-stage5-anti-overfit-promotion-add0` | No |
| Research loop | #9 | #12 | `cursor/chan-stage6-research-loop-6fec` | No (and should not be the merge vehicle) |
| vNext architecture | #15 | #16 | `cursor/northstaralpha-vnext-architecture-3dfb` | No |

File ownership until merge:

| Area | Owner |
|---|---|
| `apps/web` safety / `hourlyMarketAgent.ts` | PR #2 (done) |
| `research/statistical_diagnostics/**` | PR #4 (done) |
| `research/mean_reversion_eligibility/**` | PR #11 |
| `research/trend_carry/**` | PR #10 |
| `research/edge_health/**` | PR #13 |
| `research/anti_overfit_promotion/**` | PR #14 |
| `research/research_loop/**`, `docs/CHAN_*.md` | PR #12 |
| `docs/NORTHSTARALPHA_VNEXT_ARCHITECTURE.md` | PR #16 |
| **`docs/NORTHSTARALPHA.md` (this file)** | Comprehensive synthesis |

Allowed later integrations (only when an approved PR says so):

- UI pages that **display** diagnostic JSON and health states.
- A research job that **reads** exported PIT bars originally ingested by the paper app (copy, not live coupling).
- Shadow mode: persist hypothetical intents next to the paper book with `runMode=shadow` and **zero** fills.
- After Stage 5 `eligible_for_human_review` **and** Craig’s approval: a new sleeve runner that emits `DesiredPortfolioIntent` into RiskGovernor — still not into the old orchestrator guts.

Forbidden integrations (explicit):

- Import Chan packages from `hourlyMarketAgent.ts`, or add a sidecar HTTP call from that file that can unblock a buy.
- Gate `evaluateBuyBlock` on ADF / CADF / Hurst.
- Put Johansen inside `features.ts`.
- Use Stage 5 Kelly ceiling as the hourly position sizer without RiskGovernor.
- Let Stage 6 narrator text change `AppSettings`.
- Train LightGBM in `apps/ml-service` and call it from the hourly loop because `TODO.md` said so.
- Collapse `strategy × instrument × horizon` into `strategyMode: rules_v1 | alpha_v1 | regression_v1`.

---

## 18. Success criteria

We are on the NorthstarAlpha path when all of the following are true:

1. A new strategy family can be added without editing an hourly orchestrator.
2. Every live sleeve has a versioned Edge Contract and a Stage 5 human-review record (legacy heuristic marked `grandfathered_baseline` with a decay plan).
3. Research tests run without Node, Prisma, or network.
4. Paper fills cannot occur unless RiskGovernor (or the temporary paper-safety admission gate) allowed them.
5. Futures carry and a cointegrated pair can be researched in the same repo without pretending they are hourly equity RSI scores.
6. LLMs never appear in the call stack of scoring, sizing, or promotion verdicts.
7. The operator can answer: *what did we know at T, why was this eligible, why did risk clip it, what did we pay in friction, and which experiment failed last month?*
8. Failed experiments are as visible as winners.
9. The Chan Test can be answered with artifacts, not narrative.
10. Live trading still does not exist, and that is still correct.

---

## 19. How to read the rest of the repo

| Document | Role |
|---|---|
| **This file** | End-to-end vision + architecture + strategy + literature + loop |
| `docs/NORTHSTARALPHA_VNEXT_ARCHITECTURE.md` (PR #16) | Placement audit, KEEP/ADAPT matrix, strangler detail, repo hygiene |
| `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` | Binding scientific stage sequence and Chan Test |
| `docs/statistical_diagnostics.md` | What Stage 1 can and cannot establish |
| `docs/mean_reversion_eligibility.md` | Stage 2 gates (on PR #11) |
| `docs/trend_carry.md` | Stage 3 futures/continuous split (on PR #10) |
| `docs/edge_health.md` | Stage 4 state tables (on PR #13) |
| `docs/anti_overfit_promotion.md` | DSR / PBO / Kelly formulas (on PR #14) |
| `docs/CHAN_INTEGRATION_STACK.md` / `docs/CHAN_MORNING_TEST_PLAN.md` | How to run the overnight stack (on PR #12) |
| `docs/PAPER_VALIDATION_RUNBOOK.md` | 10-day soak and 90-day shadow cohort |
| `InvestBest_Strategy.md` | Accurate description of the *current* heuristic sleeve |
| `InvestBest_V2/DESIGN.md` | Correct principles; implementation is not the target runtime |
| `docs/InvestBest_Karpathy_Loop_Addendum.md` | Historical Loop A / Loop B instinct; superseded as promotion engine |
| `docs/ARCHITECTURE.md`, root `ARCHITECTURE.md`, `DESIGN_SPECIFICATION.md` | Historical InvestBest-era; not vNext authority |
| `TODO.md` Milestones 2–5 | InvestBest backlog. vNext supersedes “call ML from hourly agent” and “Alpaca placeholder inside the MVP agent” |

---

## 20. Document control

| Field | Value |
|---|---|
| Written | 2026-08-28 |
| Synthesizes | Chan roadmap (2026-08-26); paper-safety merge; Stage 1 merge; Stage 2–6 draft PRs; vNext architecture audit; current heuristic strategy; Karpathy addendum; world-class review IA; paper-validation runbook |
| Does not change | Production or paper-trading behavior |
| Does not authorize | Merge, deploy, live trading, or wiring Chan modules into `hourlyMarketAgent` |

When a later PR lands a stage onto `main`, update Section 17. When a scientific contract changes (for example another DSR or carry correction), update Sections 8–9 and leave a dated note. Do not fork a second “master” architecture file; edit this one.
