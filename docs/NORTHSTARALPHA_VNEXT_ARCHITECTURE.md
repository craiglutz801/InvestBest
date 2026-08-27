# NorthstarAlpha vNext Architecture

**Status:** Draft architecture audit — no production behavior changes  
**Date:** 2026-08-27  
**Product name:** NorthstarAlpha  
**Repository name today:** InvestBest (`craiglutz801/InvestBest`)  
**Scope:** Design the architecture we would choose *today* for a research-driven systematic trading platform. Existing InvestBest code is **evidence, not authority**.

This document does not merge, deploy, enable live trading, or wire Chan Stage 1–6 modules into the current hourly agent.

---

## 0. Executive recommendation

NorthstarAlpha should be a **research-first, contract-driven, Python-core systematic platform** with a TypeScript operator UI. Paper execution is a **downstream consumer** of promoted strategies, never the research engine and never the proof of edge.

The current repo contains three overlapping generations plus overnight Chan research packages landing in parallel. The correct long-term move is **not** to grow `hourlyMarketAgent.ts` until it can host Chan diagnostics. The correct move is to **strangle the hourly equity loop** behind typed contracts and let research, eligibility, portfolio construction, risk, and execution simulation become independent services.

### Top 5 legacy constraints that must **not** carry forward

1. **Monolithic hourly orchestrator as the system.** `apps/web/src/lib/jobs/hourlyMarketAgent.ts` (~2,300 lines) ingests data, computes features, scores, sells, buys, shorts, sizes, snapshots, and explains in one transaction. That shape cannot host mean-reversion pairs, futures carry, or a RiskGovernor without becoming unmaintainable.
2. **Heuristic score → paper trade as the alpha architecture.** Live scoring is three hand-authored modes (`rules_v1`, `alpha_v1`, `regression_v1`) with hardcoded weights and a seeded coefficient vector. Scores create trades. Diagnostics do not exist in the live path. This is the opposite of Chan’s eligibility-before-signal rule.
3. **Equity-only free-tier hourly loop as the universe model.** `INVESTBEST_MAX_UNIVERSE_SYMBOLS=28`, Twelve Data 7.5s pacing, a 71-ticker curated list, and SPY SMA regime logic are operational accidents, not a market model. They cannot express `strategy × instrument × horizon`.
4. **LLM / sensitivity loop as a promotion engine.** `runKarpathyTrialLoop` mutates a disconnected `StrategySpec`, scores variants with linear perturbation (not replay), and is not wired to any API. It must not become the research loop. LLMs may propose hypotheses; they must never compute money-critical arithmetic or self-promote.
5. **Point-in-time contamination in the feature store.** `FeatureSnapshot` and `ModelScore` are timestamped with `new Date()` at ingest, not bar time. The same symbol is re-fetched mid-run. Universe capping rotates names out of scan. Research built on this store will leak the future.

### Top 5 pieces worth **preserving**

1. **Paper-only execution boundary and fail-closed admission (PR #2, in flight).** `EXECUTION_MODE=paper`, operator pause/kill switch, market-data quality gate, broker-SDK isolation. These are product invariants, not InvestBest lock-in.
2. **Deterministic, unit-tested rule functions and portfolio math.** `buyRules`, `sellRules`, `shortRules`, `rotationRules`, `universePolicy`, `math.ts`, `sizing.ts`, `marketRegime.ts`, `performance/metrics.ts`. Keep as *reference implementations* and test oracles while replacing the orchestrator that calls them.
3. **Audit-oriented persistence ideas in Prisma.** `DecisionRun` + items + candidates, `PaperTrade` reason codes, run locks, idempotency keys, progress notes, diagnostics payload. Rebuild as versioned event/contracts, not as a 30-column `AppSettings` blob.
4. **Overnight Chan packages as isolated Python libraries.** Draft PRs #4/#10/#11/#13/#14/#12 already put Stages 1–6 under `research/*` with typed schemas, fail-closed promotion (`eligible_for_human_review` only), and explicit “no broker / no position mutation” tests. **That placement is the correct vNext research home.** Do not relocate them into `apps/web`.
5. **Operator UI patterns in `apps/web`.** Dashboard, holdings, trades, decision explorer, logs, diagnostics charts (Recharts), settings. These are the right *surfaces* for a research/paper platform. Keep the Next.js app as the operator console; stop using it as the research runtime.

---

## 1. Audit method and current-state evidence

### 1.1 How this audit treats the repo

- **Inspected:** `apps/web`, `apps/ml-service`, `InvestBest_V2`, `backend/`, `frontend/`, `research/`, `packages/shared`, `config/`, root docs, Prisma schema, scheduler, scoring, Karpathy loop, regression baseline, paper simulator.
- **Also inspected (draft, unmerged):** paper-safety PR #2; Chan Stage 1–6 PRs #4, #11, #10, #13, #14, #12.
- **Not treated as authority:** `docs/ARCHITECTURE.md`, `docs/DESIGN_SPECIFICATION.md`, `ARCHITECTURE.md`, `TODO.md` Milestone 2 “wire LightGBM into hourlyMarketAgent”, or any “minimal code change” path that preserves the hourly loop as the brain.

### 1.2 Three application stacks plus a fourth research plane

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
  PRODUCTION PATH per README   PARALLEL CLEAN-ROOM            LEGACY REFERENCE
                                      │
                                      ▼
                         research/*  (overnight drafts)
                         northstar_diagnostics, mean_reversion,
                         trend_carry, edge_health, promotion, research_loop
                         ISOLATED — must stay unwired to hourly agent
```

| Stack | What it actually is | Maturity |
|---|---|---|
| `apps/web` | Spec-aligned paper-trading MVP. Hourly ingest/score/trade. Full Prisma schema. UI. | Most complete **product**, weakest **research architecture** |
| `InvestBest_V2` | Isolated simulator + mock research UI. Domain types for model lifecycle. | Real rebalance engine; validation battery is copy, not code |
| `backend/` + `frontend/` | Original FastAPI/Jinja experiment. Momentum backtest, notification stubs, Alpaca env flags. | Scaffold. Celery jobs are `pass`. |
| `research/` on `main` | Placeholder README promising `strategy_library/` and `experiments/` | Empty on `main`; overnight PRs add real packages |
| `apps/ml-service` | FastAPI `/score/batch` returning neutral 50/40 scores; train/backtest 501 | Stub |
| `packages/shared` | One unused ticker list | Dead |

NorthstarAlpha does **not** appear as an identifier in executable code on `main`. It exists in `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` and in overnight research package names.

### 1.3 What the live paper path actually does

1. Load a capped equity/ETF universe (default 28 names for Twelve Data free-tier).
2. Fetch daily bars (or deterministic `mockBars()`).
3. Compute a small feature vector (`ret1d/5d/20d`, SMA distances, RSI14, vol20, volSpike).
4. Score with one of three heuristic modes.
5. Mark holdings, sell/cover, apply SPY SMA regime, buy, optionally short, snapshot.
6. Persist `DecisionRun` / trades / positions. Optionally call OpenAI for a narrative.

There is **no** Edge Contract, **no** statistical eligibility, **no** walk-forward, **no** RiskGovernor module, **no** broker adapter, **no** dry-run enforcement (`runMode: "dry_run"` is persisted but the pipeline still writes trades).

### 1.4 V2 design vs V2 code

`InvestBest_V2/DESIGN.md` states the right principles: research before trading; holdout/walk-forward; paper downstream of validation; LLM not in money-critical arithmetic. The coded app **inverts** that: `simulator.ts` runs a heuristic ranker (`ACTIVE_MODEL = "regression_v1_manual"`) with no validation engine. Research/experiments/candidates/chat pages render `mockData`. Preserve the *intent* and the isolated simulator; do not preserve the inversion.

---

## 2. KEEP / ADAPT / REPLACE / ARCHIVE matrix

Legend:

- **KEEP** — reuse with little change; valuable as-is.
- **ADAPT** — reuse the idea/interface/tests; rewrite the surrounding wiring.
- **REPLACE** — do not use as the long-term design; extract tests/oracles if useful.
- **ARCHIVE** — stop developing; move out of the active tree when hygiene work is approved. This task does **not** delete anything.

| Module / path | Decision | Why | vNext destination |
|---|---|---|---|
| **Market-data adapters** | | | |
| `apps/web/src/lib/data-provider/marketDataProvider.ts` | **ADAPT** | Right idea (swappable vendor). Too thin: daily-only, Twelve Data types leak, agent bypasses it and imports `twelveData.ts` directly. | `packages/marketdata` (TS) + `research/data` (Python) behind a versioned `MarketDataPort` |
| `apps/web/src/lib/data-provider/twelveData.ts` | **ADAPT** | Working vendor client with Zod validation and retry. Keep as one adapter. | Adapter under the port; strip 7.5s sleep into a rate-limiter, not the agent |
| Inline `mockBars()` in `hourlyMarketAgent.ts` | **REPLACE** | Mock lives inside the orchestrator. | First-class `MockMarketDataProvider` with bar-time timestamps |
| `InvestBest_V2/src/lib/marketData.ts` (Yahoo + Alpha Vantage) | **ADAPT** | Useful second vendor + earnings calendar. Unofficial Yahoo is not a production PIT store. | Earnings as an `EventDataPort`; Yahoo as research-only fallback, never canonical store |
| `backend/data/polygon_client.py` | **ADAPT** | Polygon is a better institutional vendor than Twelve Data for a serious store. Client is unused (Celery `pass`). | New Python market-data service adapter |
| Finnhub env var / unused | **ARCHIVE** | Listed, never implemented. | Revisit only if a news/event port needs it |
| **Point-in-time data / storage contracts** | | | |
| `MarketSnapshot` (bar time) | **ADAPT** | Correct grain if unique on `(symbol, timestamp, source)` and immutable. Today: append-only, no dedup, no run FK. | Canonical PIT bar store: `(instrument_id, ts, vendor, as_of)` unique, append-only, adjustments versioned |
| `FeatureSnapshot` / `ModelScore` (`new Date()` ingest time) | **REPLACE** | Timestamps are wall-clock, not decision-time. Research joins will leak. | Feature as-of bar timestamp; model scores versioned artifacts, not live rows mixed into ingest |
| `IndicatorSnapshot` (never written) | **ARCHIVE** | Dead schema. | Drop from vNext model |
| `buildRegressionDataset.ts` | **ADAPT** | Intent (lookahead join) is right; alignment is weak because feature timestamps are wrong. | Move to Python research store with explicit as-of |
| **Postgres / Prisma persistence** | | | |
| PostgreSQL as system of record | **KEEP** | Correct choice for operator state, audit, paper books. | Keep Postgres; add a research artifact store (Parquet/Arrow + object storage) for PIT panels |
| Prisma `DecisionRun`, `PaperTrade`, `PaperPosition`, locks | **ADAPT** | Good audit nouns. Overloaded with explorer JSON blobs and 30+ `AppSettings` tunables. | Split: `ops` schema (runs, fills, positions) vs `research` schema (experiments, contracts, diagnostics) |
| Single demo `User` / `requireDefaultUser()` | **REPLACE** | Fine for a personal MVP; not a platform identity model. | Operator identity later; do not design multi-tenant around this |
| `InvestBest_V2` `investbest_v2_state` JSONB blob | **REPLACE** | Convenient for a prototype; not an auditable book. | Do not promote JSONB portfolio blobs |
| **UI / dashboard** | | | |
| `apps/web` App Router UI (dashboard, holdings, trades, decisions, explorer, logs, diagnostics, settings) | **KEEP** (as operator console) | Real operator workflow. | Evolve into Research / Portfolio / Execution / Data / System IA; stop embedding strategy math in React |
| V2 pages (`/research`, `/experiments`, `/candidates`, `/system`, `/chat`) | **ADAPT** | Correct information architecture; currently mock. | Rebuild against real research contracts |
| `frontend/` Jinja templates | **ARCHIVE** | Superseded. | Freeze; do not extend |
| **Paper portfolio simulator** | | | |
| Portfolio math in `apps/web/src/lib/portfolio/math.ts` | **KEEP** | Pure, tested, long/short PnL, slippage. | Shared simulator kernel (port to Python for research replay; keep TS for UI paper book or generate both from one spec) |
| Sizing helpers `sizing.ts` | **ADAPT** | Vol targeting is real; live sizing still hardcodes `portVal×0.08`, `cash×0.33` inside the agent. | Sizing is a RiskGovernor input, not an agent local |
| Paper fills inside `hourlyMarketAgent.ts` | **REPLACE** | Simulator is not a module. `dry_run` does not dry-run. Fees are always 0. Immediate fill at last quote. | `ExecutionSimulator` service: delay, spread, impact, borrow, roll; never called by a strategy module |
| `InvestBest_V2/src/lib/simulator.ts` | **ADAPT** | Cleaner isolated rebalance loop than V1. Still heuristic, equity-only, hardcoded constants. | Extract structure (exits → candidates → size → persist); drop constants into Edge Contracts / risk policy |
| **Scheduler / job execution** | | | |
| Run lock, trigger sources, market-hours skip (`scheduler/*`) | **KEEP** | Serious operational primitives. | Keep as the **ops** scheduler; add a separate research job runner |
| `TriggerSource` / `RunMode` union (`paper_trade` \| `dry_run` \| `shadow` \| `backtest`) | **ADAPT** | Right vocabulary; `dry_run`/`shadow`/`backtest` are placeholders. | Enforce modes in the execution service, not comments |
| Render cron → `npm run agent:tick` | **ADAPT** | Fine heartbeat for paper ops. | Must not be the only way research jobs run |
| Vercel Hobby daily cron on V2 | **ARCHIVE** (as architecture) | Cadence is a hosting accident. | Do not design strategy horizons around Vercel Hobby |
| **Audit trail / idempotency** | | | |
| `DecisionRun.idempotencyKey`, `AgentRunLock` | **KEEP** | Necessary for scheduled paper runs. | Generalize to `CommandId` on every mutating ops action |
| `notesJson.progress[]` (cap 250) | **ADAPT** | Useful UX; not an immutable log. | Append-only `AuditEvent` table; UI tails it |
| Paper-safety `auditTrail.ts` (PR #2) | **KEEP** | Explicit admission/block reasons. | Feed RiskGovernor + UI |
| **Current feature / scoring code** | | | |
| `computeFeatures` | **ADAPT** | Small, tested, understandable. Insufficient as a feature platform (no PIT, no corporate actions, no cross-sectional rank, no futures). | Python feature library with as-of semantics; this file becomes a fixture for golden tests |
| `rulesScores` / `alphaFoundationScores` / `bearScores` | **REPLACE** (as alpha) | Hand-authored points. Useful as a **shadow baseline** to compare against real strategies. | Freeze as `baseline_heuristic_v1` experiment; do not extend weights |
| `apps/ml-service` stub | **REPLACE** | Neutral scores and 501s. Spec wants LightGBM *inside* the hourly loop — **reject that spec**. | If ML is used, it is a research artifact scored offline, promoted through Stage 5, never a live HTTP oracle the agent must call to trade |
| **Current buy / sell / short rules** | | | |
| `evaluateBuyBlock`, `shouldSell`, `evaluateShortBlock`, `shouldCoverShort`, `pickRotationTarget` | **ADAPT** | Deterministic gates with reason codes. They are *portfolio policy*, not edge. | Fold into RiskGovernor + sleeve policy. Reason codes stay. Thresholds come from versioned policy, not 30 AppSettings columns mixed with strategy |
| `applyLongUniversePolicy` (segment score shifts, block defensive ETFs in bull) | **REPLACE** | Hidden alpha in a “policy” file. Regime opinion masquerading as risk. | If the thesis is real, it becomes an Edge Contract with diagnostics. If not, it is a frozen baseline heuristic |
| Hardcoded agent constants (`maxDistFromMean: 0.15`, short SMA floors, rotation edges) | **REPLACE** | Invisible policy. | Versioned `RiskPolicy` |
| **Karpathy / LLM variant loop** | | | |
| Bounded `StrategySpec` + Zod schema (`strategy/types.ts`, `schema.ts`) | **ADAPT** | Right idea: agents mutate a bounded surface, not arbitrary code. Surface is the *wrong object* (hourly-rule knobs). | Replace with bounded **experiment proposals** over Edge Contract fields (Stage 6 `ALLOWED_MUTATION_TARGETS`) |
| `runKarpathyTrialLoop` + `applyTrialSensitivity` | **REPLACE** | Sensitivity is not a backtest. Unwired. Disclaimer admits it does not change the agent — and must not. | Stage 6 research loop + Stage 5 anti-overfit. LLM narrator/critic may remain as *explanation*, not scoring |
| `trialPromotionGate` (composite margin 0.015) | **REPLACE** | Toy gate vs Stage 5 DSR/PBO/holdout/walk-forward. | Do not merge the two promotion concepts |
| Planner/critic/narrator agents | **ADAPT** | Useful for hypothesis text and UI summaries. | Read-only over research artifacts; cannot place trades or edit risk code |
| **Current regression model** | | | |
| `DEFAULT_REGRESSION_V1_MODEL` seeded coefficients | **REPLACE** (as a model) | Honest about being seeded. Must not be treated as trained alpha. | Keep as a documented dummy for UI demos; research models live in the model registry with training metadata |
| Regression dataset export API | **ADAPT** | Useful once PIT is fixed. | Python research export |
| **InvestBest_V2 modules** | | | |
| `types.ts` `ModelStage` (`candidate → … → decayed`) | **KEEP** | Correct lifecycle vocabulary. | Canonical lifecycle; persist for real, not mock |
| Validation battery page copy | **ADAPT** | Spec text, no engine. | Engine is Stage 5 + research store |
| V2 chat page | **ARCHIVE** until grounded | Static bullets. | Only revive against validated artifacts (Stage 6 narrator rules) |
| **Root legacy FastAPI / Celery** | | | |
| `backend/strategies/momentum.py` + `BacktestService` | **ADAPT** | Only working Python strategy/backtest. Cross-sectional momentum is a legitimate family. | Port ideas into `research/strategy_families/trend`; do not revive SQLAlchemy app |
| `backend/tasks/*` (`pass`) | **ARCHIVE** | Empty. | Do not build Celery around this |
| `config/settings.py` Alpaca/Polygon/FRED/OpenAI | **ARCHIVE** (as active config) | Broker keys on a dead stack. Paper-safety PR correctly isolates them. | Secrets belong to future execution adapters, never to research packages |
| `frontend/` | **ARCHIVE** | Jinja MVP. | — |
| **Chan Stage 1–6 research modules** | | | |
| Stage 1 `research/statistical_diagnostics` (`DiagnosticResult`) | **KEEP** (as drafted) | Isolated, typed, PIT-aware, no broker. **This is the vNext diagnostics kernel.** | Remain a pure Python library. UI/ops consume serialized results only |
| Stage 2 `research/mean_reversion_eligibility` | **KEEP** (as drafted) | Eligibility ≠ entry. Correct Chan split. | Shadow-only until Stage 5 + human review |
| Stage 3 `research/trend_carry` | **KEEP** (as drafted) | Multi-horizon + futures continuous vs executable series. Prevents equity-hourly lock-in. | Same isolation |
| Stage 4 `research/edge_health` | **KEEP** (as drafted) | Advisory health states; hysteresis; no orders. | RiskGovernor may *read* health to throttle within pre-approved bounds; health never places orders |
| Stage 5 `research/anti_overfit_promotion` | **KEEP** (as drafted) | Fail-closed; max verdict `eligible_for_human_review`; Kelly is a ceiling. | **This** is promotion. Not `trialPromotionGate`. Not AppSettings.strategyMode |
| Stage 6 `research/research_loop` + `EdgeContract` | **KEEP** (as drafted) | Bounded proposals, forbidden actions, strategy × instrument × horizon identity. | Research control plane. Must not import `hourlyMarketAgent` |
| `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` | **KEEP** | Binding research sequence. | This vNext doc *places* those stages; it does not rewrite Chan’s scientific content |

---

## 3. Greenfield target architecture

If no InvestBest code existed, this is the system we would build.

### 3.1 Design principles

1. **Research is the product.** Paper trading is a consumer of promoted sleeves, not the source of truth for whether a strategy works.
2. **Separation of concerns is a safety property.** A module that can compute ADF cannot submit an order. A module that can size cannot fetch a broker clock. A module that can narrate cannot change risk limits.
3. **Typed, versioned contracts at every boundary.** JSON-serializable, schema-versioned, fail-closed on unknown versions.
4. **Point-in-time by default.** Every feature, diagnostic, and signal carries `as_of`. Storage that cannot answer “what was known at T?” is not a research store.
5. **Python for statistical/research workloads.** statsmodels/numpy/scipy/pandas (and later PyArrow) are the correct ecosystem for Stages 1–5, walk-forward, and futures term structure. TypeScript is for the operator UI, BFF, and paper-ops API.
6. **No LLM in money-critical arithmetic.** LLMs propose, critique, and explain. They do not score, size, or promote.
7. **No direct strategy-to-broker access.** Strategies emit *desired risk intents*. Execution simulation (and any future broker adapter) is a separate process with its own auth and an allow-list of order types. Live trading is out of scope until an explicit later decision.
8. **Replaceable data providers.** Canonical store is vendor-neutral. Twelve Data, Polygon, Yahoo, and mock are adapters.
9. **`strategy × instrument × horizon` is the atomic research object**, not `ticker` and not `strategyMode` on a user.
10. **RiskGovernor is authoritative.** Diagnostics, health, and research agents may recommend throttle/pause/retire. Only RiskGovernor (plus a human merge gate for promotion) can change risk that reaches the simulator.
11. **Fast isolated tests.** Pure functions, synthetic series, no Docker required for research unit tests. Ops tests may use Postgres.
12. **Optimize for the best long-term system**, not minimal diffs to `hourlyMarketAgent.ts`.

### 3.2 Logical architecture

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
                         ExecutionSimulator  ──X──  Broker adapter (does not exist;
                                                    forbidden until explicit program)
```

Pipeline (Chan-aligned, not hourly-agent-aligned):

```text
DATA
  → POINT-IN-TIME VALIDATION
  → FEATURES (as-of)
  → EDGE MECHANISM (Edge Contract)
  → STATISTICAL DIAGNOSTICS (Stage 1)
  → STRATEGY ELIGIBILITY (Stage 2–3)
  → SIGNAL (shadow until promoted)
  → EXPECTED EDGE AFTER COST + UNCERTAINTY HAIRCUT
  → EDGE HEALTH / REGIME COMPATIBILITY (Stage 4)
  → PORTFOLIO CONSTRUCTION
  → FRACTIONAL-KELLY CEILING (Stage 5; ceiling only)
  → RISK GOVERNOR
  → EXECUTION SIMULATION
  → ATTRIBUTION
  → HEALTH / DECAY MONITORING
  → RESEARCH LOOP (Stage 6; bounded)
```

**Diagnostics never place an order.** Unpromoted signals never reach ExecutionSimulator.

### 3.3 Target repository layout (greenfield)

Proposed once hygiene work is approved. **Do not move files in this PR.**

```text
northstaralpha/                         # product name; git remote may stay InvestBest until a rename
  packages/
    contracts/                          # JSON Schema + generated TS/Py types (single source)
    ui/                                 # today’s apps/web, slimmed to operator console
  services/
    marketdata/                         # ingest, vendor adapters, PIT writer
    research/                           # job runner for Stages 1–6, walk-forward
    portfolio/                          # construction from eligible sleeves
    risk/                               # RiskGovernor
    execution-sim/                      # paper fills, costs, delay, borrow, rolls
    ops-api/                            # BFF for UI
  research/                             # KEEP overnight packages here
    statistical_diagnostics/
    mean_reversion_eligibility/
    trend_carry/
    edge_health/
    anti_overfit_promotion/
    research_loop/
    strategy_families/                  # thin wrappers that *use* the above; no orchestration
  archive/                              # backend/, frontend/, InvestBest_V2, root FastAPI docs
```

Language rule:

| Workload | Language | Reason |
|---|---|---|
| Diagnostics, eligibility, health, DSR/PBO, Kelly ceiling, walk-forward, futures term structure | Python 3.11+ | Ecosystem quality, numeric isolation, overnight packages already here |
| Operator UI, paper book API, scheduler | TypeScript | Existing UI quality; no need to rewrite React |
| Shared contracts | JSON Schema (codegen to both) | Avoid a second accidental schema war |
| Money-critical arithmetic | Never LLM; prefer Python research + deterministic TS ops twins only where the paper book must match | Golden tests across languages for PnL math |

### 3.4 Core contracts (vNext)

These are the objects the overnight Chan work should speak. Names align with draft PRs where they already exist.

#### Edge Contract (research authority)

Already drafted in Stage 6 (`EdgeContract`): `strategy_family`, mechanism, required statistical property, instruments, horizon, holding period, expected costs (commission/spread/slippage/impact/borrow/dividend/financing/futures_roll), good/bad regimes, formation tests, live health tests, break/retirement/throttle rules, Chan review answers.

Identity:

```text
identity_key = strategy_family | instruments | horizon
```

Not `AppSettings.strategyMode`. Not `ticker` alone.

#### DiagnosticResult (evidence only)

Already drafted in Stage 1: `as_of`, sample window, method, parameters, statistics, p-value, quality flags, `is_usable`. Fail flags make the result unusable for eligibility.

#### EligibilityDecision / HealthSnapshot / PromotionDecision

- Eligibility: candidate vs ineligible, reason codes, **never** an entry. Residual z-score is a later shadow step.
- Health: `healthy | degraded | paused | retire_research`, advisory; hysteresis in Stage 4.
- Promotion: `reject | eligible_for_human_review` only. No self-promotion. Failed experiments are first-class registry rows.

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

Fills, slippage vs arrival, unfilled remainder, cost breakdown matching Stage 1 `FrictionInputs` names so EFR in research and realized friction in ops are comparable.

### 3.5 RiskGovernor

A dedicated policy engine, not extra `if`s in an hourly agent.

**Inputs:** DesiredPortfolioIntent(s), current book, liquidity, borrow/roll calendars, Edge Contract throttle rules, Stage 4 health, operator pause, `EXECUTION_MODE`.

**Hard authority:**

- Gross/net exposure caps, single-name and sleeve concentration
- Volatility / drawdown throttles
- Liquidity and shortability
- Horizon conflict (do not express 12-month trend and 2-day MR as one hourly slot)
- Kill switch / pause (from paper-safety PR)
- Fail closed on missing/stale/non-finite data
- Fractional-Kelly **ceiling** from Stage 5 — never a target, always subordinate to the limits above

**Non-authority:** inventing signals, relaxing promotion gates, calling brokers, hiding failed experiments.

Until a Python RiskGovernor service exists, the paper-safety admission gate in `apps/web` is the **temporary** governor for the legacy loop only. New Chan modules must not call it, and it must not call them.

### 3.6 Execution boundary

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

Paper-safety `ACTIVE_APP_BROKER_POLICY` and Stage 6 `ForbiddenAction` are **KEEP** and should be encoded as CI grep tests on `apps/web` and `research/*` respectively.

### 3.7 Strategy × instrument × horizon — adding futures/carry/stat-arb

The hourly equity loop fails this test. vNext passes it by making **horizon a first-class dimension**:

| Family | Instrument | Typical horizon | Data needs | Must not reuse |
|---|---|---|---|---|
| Time-series trend | Equity, futures, FX | 1m / 3m / 6m / 12m | Continuous research series + executable contract | SPY SMA50/200 as the only regime |
| Futures carry | Listed futures | contract / roll cycle | Curve, roll calendar, financing | Equity close-to-close features |
| Stat-arb / MR | Pairs, baskets | half-life days | Cointegration, hedge ratio, borrow | `bearScores` / RSI oversold as “mean reversion” |
| Event | Equities | days around earnings | Event calendar as-of | V2 earnings penalty hardcoded in simulator |

A new family adds: an Edge Contract template, Stage 1 diagnostics it needs, an eligibility module, health rules, cost model, and a sleeve in portfolio construction. It does **not** add another `strategyMode` string to `hourlyMarketAgent`.

### 3.8 Testing strategy

| Layer | What | Speed |
|---|---|---|
| Research unit tests | Synthetic stationary / RW / cointegrated series; degenerate NaN/Inf; PIT as-of masks | milliseconds, no IO |
| Contract tests | JSON Schema round-trip TS ↔ Py | seconds |
| Simulator golden tests | Known fills, costs, delay; PnL twins | seconds |
| Ops integration | Idempotent paper run against test Postgres | seconds–low minutes |
| Forbidden-import tests | Research packages cannot import `apps/web`, Prisma, broker SDKs | milliseconds |

Reject: “integration test = run the hourly agent against Twelve Data.”

---

## 4. Migration / strangler plan

Goal: reach vNext **without** a big-bang rewrite and **without** teaching Chan modules to speak hourly-agent. Strangle by **contract**, not by wrapping the 2,300-line function.

### Phase A — Freeze the legacy loop as a baseline sleeve (now)

- Leave `apps/web` paper trading running as **heuristic baseline / operator sandbox**.
- Do **not** add Chan imports, LightGBM, or Karpathy promotion into `hourlyMarketAgent.ts`.
- Merge paper-safety PR #2 (when Craig approves) so the sandbox is fail-closed paper-only.
- Keep Chan Stages 1–6 in `research/*` as isolated libraries (already the overnight plan).
- Snapshot current heuristic as experiment `baseline_heuristic_v1` in the Stage 5 registry **once that registry exists** — a frozen reference, not an evolving alpha.

### Phase B — Contracts and PIT store (first structural work)

- Introduce `packages/contracts` (Edge Contract, DiagnosticResult, Intent, RiskDecision) generated from the overnight Python dataclasses / JSON.
- Build a PIT bar writer: unique `(instrument, timestamp, vendor)`, as-of, no wall-clock feature stamps.
- Adapter-wrap Twelve Data and Polygon behind `MarketDataPort`. Stop importing vendors from the orchestrator.
- Extract `ExecutionSimulator` from the agent: same math tests, new caller.

**Reuse unchanged:** Prisma paper book tables (temporarily), UI pages, scheduler locks, `math.ts` tests, paper-safety gates.

**Wrap:** Twelve Data client, buy/sell reason codes as a `LegacyHeuristicSleeve` adapter that emits `DesiredPortfolioIntent` instead of writing trades.

**Rewrite:** feature timestamps, scoring-as-alpha, orchestrator control flow.

**Retire from active design:** `strategyMode`, Karpathy sensitivity promotion, ml-service-as-live-oracle, V2 JSONB blob, Jinja app.

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
- Rename product strings to NorthstarAlpha; repository rename is a later ops decision.

### Explicit reuse classification

| Reuse unchanged | Wrap behind adapters | Rewrite | Retire |
|---|---|---|---|
| Paper-only policy, kill switch | Twelve Data / Yahoo / Polygon clients | `hourlyMarketAgent` control flow | Seeded regression as alpha |
| Unit tests for math + rule reason codes | Scheduler heartbeat | Feature store timestamps | Karpathy sensitivity gate |
| Decision/trade/position **nouns** | Heuristic scores as `LegacyHeuristicSleeve` | AppSettings as strategy | Celery stubs, Jinja UI |
| Chan research packages (as libraries) | V2 simulator loop shape | Portfolio construction / risk | `packages/shared` unused tickers |
| Next.js operator chrome | Prisma paper book during Phase B–C | Promotion (use Stage 5) | Checked-in `.venv`, `investbest.db` (hygiene) |

---

## 5. Repo hygiene plan

**This section proposes cleanup only. Do not delete or move files as part of this audit PR.**

| Issue | Evidence | Proposed action (later PR) |
|---|---|---|
| Checked-in `.venv/` | ~8,669 tracked files, ~139 MB | `git rm -r --cached .venv`; add root `.gitignore`; never recommit. Recreate locally via `scripts/run.sh` or a documented `uv`/`venv` path |
| Checked-in `investbest.db` | 64 KB SQLite at repo root | Untrack; treat as local artifact of legacy backend |
| Checked-in `.DS_Store` | Root | Untrack; gitignore |
| No root `.gitignore` | Only `apps/web/.gitignore` and `InvestBest_V2/.gitignore` | Add root ignore: `.venv/`, `*.db`, `.env`, `.DS_Store`, `node_modules`, `.next` |
| Duplicate apps | `apps/web` vs `InvestBest_V2` vs `backend/`+`frontend/` | Declare `apps/web` = operator UI; `research/` = science; `InvestBest_V2` freeze then `archive/investbest_v2/` after extracting simulator tests; legacy FastAPI → `archive/fastapi_mvp/` |
| Duplicate architecture docs | Root `ARCHITECTURE.md` (FastAPI), `docs/ARCHITECTURE.md` (2026 MVP), `docs/DESIGN_SPECIFICATION.md` (2025 Jinja), V2 `DESIGN.md`, this doc | Make **this file** the NorthstarAlpha authority. Stamp others `Status: historical / InvestBest-era`. Chan roadmap remains the scientific sequence |
| Naming | Package `investbest-web`, demo `demo@investbest.local`, product NorthstarAlpha | Gradual rename: UI chrome first, env prefixes `NORTHSTAR_*` with aliases for `INVESTBEST_*`, repo rename last |
| Stale broker-facing config | `ALPACA_*` in `config/settings.py`, services checklist, health flags; **no order code** | Keep isolated (paper-safety). Do not add SDKs. Later: move to `archive` with the FastAPI app |
| Stale research README | Promises AI Strategy Generator Phase 3 folders that do not exist | Replace with index of Stage 1–6 packages after those PRs land |
| `apps/ml-service` stub | Neutral scores | Freeze; do not deploy as a live dependency of paper trading |
| `packages/shared` | Unused tickers | Fold into contracts/universe later or archive |
| Render seed-on-cron | `render.yaml` `db:seed` every hourly build | Stop seeding production on cron (ops bug, separate PR) |
| Prisma raw-SQL fallbacks | ~15 paths when client is stale | Delete the pattern when the schema is stable; it hides drift |

---

## 6. Integration boundary for overnight Chan work

### 6.1 Where Stages 1–6 live

**Home: `research/<package>/` as importable Python libraries.** This is already what draft PRs #4, #11, #10, #13, #14, #12 do. vNext **ratifies** that layout.

| Stage | Package (draft) | Import name | May import | Must not import |
|---|---|---|---|---|
| 1 | `research/statistical_diagnostics` | `northstar_diagnostics` | numpy/scipy/statsmodels | `apps/web`, Prisma, broker, `hourlyMarketAgent` |
| 2 | `research/mean_reversion_eligibility` | `northstar_mean_reversion` | Stage 1 | same + must not write positions |
| 3 | `research/trend_carry` | `northstar_trend_carry` | Stage 1 (optional) | same |
| 4 | `research/edge_health` | `northstar_edge_health` | Stage 1 | same; health is advisory |
| 5 | `research/anti_overfit_promotion` | `northstar_promotion` | numeric stack | same; verdict ≠ activate |
| 6 | `research/research_loop` | `northstar_research_loop` | Stages 1–5 via adapters | same; plus no self-merge/deploy |

Communication pattern:

```text
CLI / research job runner
    → loads PIT panels (files or research DB, not live Twelve Data inside the library)
    → calls Stage 1–4 pure functions
    → writes DiagnosticResult / Eligibility / Health / Promotion JSON artifacts
    → Stage 6 loop proposes bounded config diffs against Edge Contracts
    → human review

apps/web UI
    → MAY read serialized artifacts via ops-api (display only)
    → MUST NOT call Python diagnostics in-process from hourlyMarketAgent
    → MUST NOT change paper positions because a diagnostic p-value moved
```

### 6.2 Forbidden integrations (explicit)

Do **not**:

- `import` Chan packages from `hourlyMarketAgent.ts` (or add a sidecar HTTP call from that file that can unblock a buy).
- Gate `evaluateBuyBlock` on ADF/CADF/Hurst.
- Put Johansen inside `features.ts`.
- Use Stage 5 Kelly ceiling as the hourly position sizer without RiskGovernor.
- Let Stage 6 narrator text change `AppSettings`.
- Train LightGBM in `apps/ml-service` and call it from the hourly loop “because TODO.md said so.”
- Collapse `strategy × instrument × horizon` into `strategyMode: rules_v1 | alpha_v1 | regression_v1`.

### 6.3 Allowed integrations (when a later approved PR says so)

- UI pages that **display** diagnostic JSON and health states.
- A research job that **reads** exported PIT bars originally ingested by the paper app (copy, not live coupling).
- Shadow mode: persist hypothetical intents next to the paper book with `runMode=shadow` and **zero** fills.
- After Stage 5 `eligible_for_human_review` **and** Craig’s merge/promotion approval: a new sleeve runner that emits `DesiredPortfolioIntent` into RiskGovernor — still not into the old orchestrator guts.

### 6.4 File ownership vs parallel overnight PRs

Do not fight the stacking map in `docs/CHAN_INTEGRATION_STACK.md` (draft on Stage 6):

| Area | Owner until merge |
|---|---|
| `apps/web/src/lib/safety/**`, admission, execution mode | Paper-safety PR #2 |
| `research/statistical_diagnostics/**` | Stage 1 PR #4 |
| `research/mean_reversion_eligibility/**` | Stage 2 PR #11 |
| `research/trend_carry/**` | Stage 3 PR #10 |
| `research/edge_health/**` | Stage 4 PR #13 |
| `research/anti_overfit_promotion/**` | Stage 5 PR #14 |
| `research/research_loop/**` | Stage 6 PR #12 |
| **`docs/NORTHSTARALPHA_VNEXT_ARCHITECTURE.md` (this file)** | This audit |

This audit does not modify those packages. It tells later work **where they plug in** (research plane) and **where they must not** (hourly agent, Prisma paper mutations).

### 6.5 Paper-safety vs Chan

Paper-safety hardens the **legacy sandbox**. Chan builds the **future research kernel**. They meet only at:

1. Shared forbidden-broker rule.
2. Shared “diagnostics are not orders” rule.
3. Eventually, RiskGovernor reading health + intents.

They should not share files this week. If they touch the same file, paper-safety wins for `apps/web`, Chan wins for `research/`.

---

## 7. Operator / research information architecture (UI)

When the console is retargeted (not in this PR), navigate by workflow:

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

## 8. Decisions this architecture refuses

| Tempting shortcut | Why we refuse |
|---|---|
| “Just call Stage 1 from the hourly agent so Chan is integrated” | Couples science to a free-tier equity cron and makes diagnostics into trade switches |
| “Wire ml-service LightGBM next; it’s Milestone 2” | Trains on a contaminated feature store and keeps score→trade |
| “V2 is the rewrite, cut over” | V2 simulator is still heuristic; research UI is mock |
| “Revive FastAPI + Alpaca from config/settings.py” | Broker keys on a dead stack; violates paper-only |
| “Karpathy loop promotes AppSettings” | Sensitivity ≠ validation; LLM adjacent to money |
| “One strategyMode enum to rule them all” | Cannot represent horizon or instrument class |
| “JSON blob for the whole book” (V2) | Not auditable, not reconcilable |
| “Minimal diffs to hourlyMarketAgent” | Explicitly rejected by this audit’s charter |

---

## 9. Success criteria for vNext (architecture-level)

We are on the NorthstarAlpha path when all of the following are true:

1. A new strategy family can be added without editing an hourly orchestrator.
2. Every live sleeve has a versioned Edge Contract and a Stage 5 human-review record (legacy heuristic marked `grandfathered_baseline` with a decay plan).
3. Research tests run without Node, Prisma, or network.
4. Paper fills cannot occur unless RiskGovernor (or the temporary paper-safety admission gate) allowed them.
5. Futures carry and a cointegrated pair can be researched in the same repo without pretending they are hourly equity RSI scores.
6. LLMs never appear in the call stack of scoring, sizing, or promotion verdicts.
7. The operator can answer: *what did we know at T, why was this eligible, why did risk clip it, what did we pay in friction, and which experiment failed last month?*

---

## 10. Document control

| Doc | Role after this audit |
|---|---|
| **This file** | NorthstarAlpha **system** architecture (placement, strangler, hygiene, anti-lock-in) |
| `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` | Scientific stage sequence and Chan test questions |
| Overnight `docs/statistical_diagnostics.md` etc. | Per-package developer docs (when those PRs land) |
| `docs/ARCHITECTURE.md` + root `ARCHITECTURE.md` + `DESIGN_SPECIFICATION.md` | Historical InvestBest-era; not vNext authority |
| `InvestBest_V2/DESIGN.md` | Correct *principles*; implementation is not the target runtime |
| `TODO.md` Milestone 2–5 | Treat as InvestBest backlog. vNext supersedes “call ML from hourly agent” and “Alpaca placeholder inside the MVP agent” |

**No production behavior is changed by adding this document.**

---

## Appendix A — Evidence index (main-branch paths)

| Path | Role in the audit |
|---|---|
| `apps/web/src/lib/jobs/hourlyMarketAgent.ts` | Monolithic orchestrator (~2298 lines), mock bars, raw-SQL fallbacks |
| `apps/web/src/lib/portfolio/features.ts` | Heuristic score modes |
| `apps/web/src/lib/research/regressionV1.ts` | Seeded coefficients `regression-v1-seeded` |
| `apps/web/src/lib/karpathy/runTrialLoop.ts` | Unwired sensitivity “promotion” |
| `apps/web/src/lib/data-provider/marketDataProvider.ts` | Thin port, unused by agent |
| `apps/web/prisma/schema.prisma` | Paper book + AppSettings policy blob |
| `apps/web/src/lib/scheduler/types.ts` | RunMode placeholders |
| `InvestBest_V2/src/lib/simulator.ts` | Isolated but heuristic rebalance |
| `InvestBest_V2/src/lib/types.ts` | ModelStage lifecycle (keep vocabulary) |
| `apps/ml-service/app/main.py` | Neutral stub |
| `backend/` | Legacy FastAPI; Celery `pass`; Alpaca flags |
| `research/README.md` | Empty placeholder on `main` |
| `render.yaml` | Hourly cron, universe cap 28 |
| `.venv/`, `investbest.db` | Checked-in artifacts |

## Appendix B — Overnight draft PRs this architecture assumes as *research* (unmerged)

| PR | Stage | Boundary ratified here |
|---|---|---|
| #2 | Paper-only safety | KEEP for legacy sandbox; temporary governor |
| #4 | Diagnostics foundation | KEEP; research kernel |
| #11 | Mean-reversion eligibility | KEEP; shadow |
| #10 | Trend + futures carry | KEEP; prevents equity-only lock-in |
| #13 | Edge health | KEEP; advisory |
| #14 | Anti-overfit promotion | KEEP; only promotion authority |
| #12 | Research loop + EdgeContract | KEEP; control plane |

None of those PRs should be merged solely because this audit exists. Craig’s merge gate remains. This document exists so that, if they merge, they merge **into a research plane**, not into InvestBest’s hourly agent.
