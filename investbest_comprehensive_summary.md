# InvestBest — Comprehensive Summary & Engineering Design

This document describes the **purpose**, **behavior**, and **technical architecture** of the InvestBest application in this repository. It is intended for engineers and stakeholders who need a single, detailed map of *what* the system is, *why* it is built the way it is, and *where* the important code lives.

---

## 1. Executive summary

**InvestBest** is a **paper-trading** web application: it simulates a U.S.-listed equity and ETF portfolio (default **$100,000** starting cash) using **rule-based** buy/sell logic, **market data** (Twelve Data or a deterministic mock), and **persistent audit trails** of every agent run, candidate symbol, and simulated trade. It is **not** a broker, does not move real money, and is built for **research, education, and strategy experimentation**.

The active product lives under **`apps/web`** (Next.js 15, App Router, Prisma, PostgreSQL). Supporting pieces include **`docker-compose.yml`** (local Postgres), **`packages/shared`** (small shared constants such as default tickers), **`apps/ml-service`** (FastAPI stub for future batch scoring), and **legacy** folders (`backend/`, `frontend/`, `research/`) kept for reference.

---

## 2. Purpose and product goals

### 2.1 What problem it serves

- **Transparent automation**: Run a recurring “agent” that evaluates a curated **universe** of symbols, scores them with explicit rules, applies **risk and liquidity guardrails**, and records **why** each action was taken or blocked.
- **Safe experimentation**: All execution is **paper-only**; settings (thresholds, position caps, shorts, regime filters) can be tuned without capital risk.
- **Auditability**: Each run produces structured artifacts (`DecisionRun`, `DecisionRunItem`, `DecisionRunCandidate`, `PaperTrade`, `PortfolioSnapshot`, etc.) suitable for diagnostics and post-hoc analysis.

### 2.2 Primary user journeys

| Journey | Description |
|--------|-------------|
| **Dashboard** | View portfolio value, performance vs a benchmark snapshot, equity/drawdown curves, latest agent status, optional **portfolio Q&A** (OpenAI) when `OPENAI_API_KEY` is set. |
| **Diagnostics** | Strategy diagnostics, attribution-style breakdowns, charts (rebuilt via API; cached in `TradeAttributionSnapshot`). |
| **Holdings / Trades** | Open positions and executed paper trades with reasons and scores. |
| **Universe** | Explore segments (equities, defense, energy, agriculture, metals, macro) and how symbols map into the tradable set. |
| **Decisions** | Inspect decision runs and drill into per-symbol explorer views. |
| **Settings** | Tune strategy thresholds, scheduler behavior, paper reset, search profiles, and **manual “run agent now”**. |

The root route **`/`** redirects to **`/dashboard`** (`src/app/page.tsx`).

---

## 3. What the system does (runtime behavior)

### 3.1 The “hourly market agent” pipeline

The core orchestrator is **`runHourlyMarketAgent`** in `apps/web/src/lib/jobs/hourlyMarketAgent.ts` (build spec §14). At a high level, each run:

1. **Loads** the demo user’s `AppSettings`, open `PaperPosition`s, and the **tradable symbol universe** (segments, search profile, free-tier symbol caps).
2. **Fetches** daily OHLCV and live quotes via **`src/lib/data-provider/twelveData.ts`** (or mock data when configured).
3. **Computes features** and **rules scores** (`src/lib/portfolio/features.ts` — `rulesScores`, `bearScores`, etc.).
4. **Evaluates sells** before buys (`src/lib/rules/sellRules.ts`, `shortRules.ts`), respecting stop-loss, take-profit, trailing give-back, stale-quote policy, cooldowns, and regime-related throttles.
5. **Evaluates buys** (`src/lib/rules/buyRules.ts`) with confidence, momentum, vol caps, dollar-volume liquidity, SPY-based **market regime** assessment (`src/lib/portfolio/marketRegime.ts`), and position sizing (`src/lib/portfolio/sizing.ts`, `math.ts`).
6. **Persists** bars, indicators, features, model scores, quote snapshots, decision rows, paper trades, portfolio snapshots, holding value logs, and optional **LLM summary** via the decision explainer (`src/lib/decision/explainer.ts`).
7. **Records progress** in run notes for UI polling (`src/lib/jobs/runProgress.ts`).

Runs are **idempotent** per time bucket where applicable (e.g. hour bucket keys) to avoid duplicate trades when cron or manual triggers overlap.

### 3.2 Scheduling and concurrency

- **`triggerAgentRun`** (`src/lib/scheduler/triggerAgentRun.ts`) is the **single entry** for triggered runs. It:
  - Acquires a per-user **`AgentRunLock`** (Postgres-backed; expires stale locks).
  - Pre-creates or attaches to a **`DecisionRun`** with `triggerSource`, `runMode`, idempotency key, and lock linkage.
  - Invokes `runHourlyMarketAgent` and updates **`AgentScheduleSettings`** bookkeeping (`lastRunAt`, `lastRunStatus`, `nextRunAt`, errors).
- **`/api/internal/scheduler-tick`** (`src/app/api/internal/scheduler-tick/route.ts`) calls **`runSchedulerTick`** (`src/lib/jobs/hourlyAgentScheduler.ts`), which decides which users are due and kicks off runs (often in the background via Next.js **`after()`** for fast HTTP responses).
- **`SCHEDULER_PROVIDER`** (`src/lib/scheduler/provider.ts`) abstracts **database**, **Trigger.dev**, and **Vercel Cron**-style heartbeats; the default path is **external cron → scheduler tick**.

### 3.3 Internal API authentication

Internal routes (`scheduler-tick`, `hourly-run`, rebuild hooks, etc.) use **`internalAuthorized`** (`src/lib/server/internalAuth.ts`):

- In **production**, a shared secret must match via `Authorization: Bearer`, `x-investbest-secret`, or `x-internal-cron-secret`.
- Secret resolution order: `INVESTBEST_INTERNAL_SECRET` → `INTERNAL_CRON_SECRET` → `CRON_SECRET` → `TRIGGER_SECRET_KEY`.
- In **non-production**, if no secret is configured, requests are allowed (local dev friction reduced).

### 3.4 LLM-assisted features (optional)

| Feature | Location | Requirement |
|--------|----------|-------------|
| **Portfolio Q&A** | `src/app/api/dashboard/ask/route.ts` | `OPENAI_API_KEY`; builds context from `buildDashboardPayload` + strategy snapshot (`src/lib/server/portfolioQaContext.ts`). |
| **Run explainer** | `src/lib/decision/explainer.ts` | Summarizes run outcome when key present. |
| **Karpathy-style trial loop** | `src/lib/karpathy/runTrialLoop.ts` + `src/lib/agents/*` | Proposes strategy variants (deterministic + optional LLM in `researchPlanner.ts`), scores via **composite metrics**, runs **critic** and **narrator** agents; **does not auto-promote** to live settings without gates (`src/lib/promotion/trialPromotionGate.ts`). |

These paths degrade gracefully when keys are missing (Q&A disabled; planners fall back to non-LLM variants).

---

## 4. Why it should work (design rationale)

### 4.1 Deterministic core, optional intelligence

- **Scoring and execution** rely on **explicit TypeScript rules** and numeric thresholds stored in `AppSettings`, not on opaque model output alone. That yields **reproducible** behavior for a given seed, settings, and data snapshot.
- **Mock market data** (`USE_MOCK_MARKET_DATA` / missing Twelve Data key) allows CI and local dev without network flakiness.

### 4.2 Strong persistence model

- Prisma models cover the full lifecycle: **universe → snapshots → scores → decisions → trades → portfolio snapshots → diagnostics cache**. The schema is annotated for “Strategy Upgrade” concepts (trigger sources, run modes, scheduler settings, locks, attribution snapshots).
- **Constraints** (e.g. unique `(userId, symbolId)` on `PaperPosition`, idempotency keys on `DecisionRun`) reduce double-counting and orphan states.

### 4.3 Operational safety

- **Run locks** prevent overlapping agent executions per user.
- **Stale quote** handling can block sells (`staleQuoteAllowSells`) to avoid selling on bad prices.
- **Market-hours** and **schedule preset** logic (`src/lib/scheduler/marketHours.ts`, `calculateNextRun.ts`) align automated runs with intended sessions.

### 4.4 Known limitations (honest scope)

- **Single demo user** (`requireDefaultUser` in `src/lib/server/defaultUser.ts`, email from `INVESTBEST_DEMO_EMAIL`) — multi-tenant auth is a future swap-in.
- **Rules + heuristics ≠ guaranteed alpha**; the app proves **process** and **measurement**, not profitability.
- **ML service** is largely stubbed; batch scoring integration is a forward path, not the current core loop.

---

## 5. Repository layout

```
InvestBest/
├── apps/
│   ├── web/                 # Primary Next.js application
│   └── ml-service/          # FastAPI stub (future /score/batch, etc.)
├── packages/
│   └── shared/              # Shared TS constants (e.g. default tickers)
├── docs/                    # Build spec, architecture notes
├── docker-compose.yml       # Postgres (host port 5433)
├── README.md
└── investbest_comprehensive_summary.md   # This file
```

Legacy: `backend/`, `frontend/`, `research/` — not the spec-aligned primary path (see root `README.md`).

---

## 6. `apps/web` engineering structure

### 6.1 Stack

| Layer | Technology |
|-------|------------|
| Framework | Next.js 15 (App Router), React 19 |
| Language | TypeScript |
| Styling | Tailwind CSS, `tailwindcss-animate`, class-variance-authority |
| UI | Radix primitives, local `src/components/ui/*`, Lucide icons |
| Charts | Recharts |
| ORM | Prisma 6 → PostgreSQL |
| Validation | Zod (e.g. settings, API bodies) |
| Tests | Vitest (`npm test`) — math, rules, features, metrics |

### 6.2 App Router layout (`src/app`)

| Path | Role |
|------|------|
| `layout.tsx` | Root layout, metadata |
| `(main)/layout.tsx` | **Force-dynamic** shell with `AppNav` |
| `(main)/dashboard`, `diagnostics`, `holdings`, `universe`, `trades`, `decisions`, `settings` | Feature pages (mostly server components + client widgets) |
| `api/**/route.ts` | REST-style route handlers |

**Navigation** is centralized in `src/components/AppNav.tsx` (Dashboard, Diagnostics, Holdings, Universe, Trades, Decisions, Settings).

### 6.3 Library code (`src/lib`) — conceptual map

| Area | Path(s) | Responsibility |
|------|---------|----------------|
| **DB** | `db.ts` | Singleton `PrismaClient`; merges `.env` files in dev for `DATABASE_URL` / `INVESTBEST_DATABASE_URL` |
| **Market data** | `data-provider/twelveData.ts`, `marketDataProvider.ts` | Twelve Data HTTP client; swappable `MarketDataProvider` interface |
| **Features & regime** | `portfolio/features.ts`, `marketRegime.ts`, `sizing.ts`, `math.ts` | Indicators, rule scores, regime, position math, slippage |
| **Rules** | `rules/buyRules.ts`, `sellRules.ts`, `shortRules.ts` | Blocking logic; paired `*.test.ts` |
| **Jobs** | `jobs/hourlyMarketAgent.ts`, `jobs/hourlyAgentScheduler.ts`, `jobs/freeTierUniverse.ts`, `jobs/runProgress.ts` | Orchestration, universe prep for API limits, progress JSON |
| **Scheduler** | `scheduler/*.ts` | Locks, trigger wrapper, providers, next-run calculation |
| **Server helpers** | `server/dashboardPayload.ts`, `holdingsPayload.ts`, `prices.ts`, `tradableSymbols.ts`, `positionValueHistory.ts`, `internalAuth.ts`, `defaultUser.ts` | Read models for UI and APIs |
| **Diagnostics** | `diagnostics/*.ts` | Payload builders, warnings, regime helpers, risk ratios |
| **Performance** | `performance/metrics.ts` | Equity curve, drawdown, returns |
| **Evaluation / research** | `evaluation/*`, `research/types.ts`, `karpathy/runTrialLoop.ts`, `agents/*`, `strategy/*` | Trial metrics, strategy JSON schema, variant generation |
| **API helpers** | `api/http.ts`, `api/settingsSchema.ts` | JSON responses, settings validation |
| **Constants** | `constants/universe.ts` | `UNIVERSE_SEGMENTS`, ticker metadata (seed aligns with this) |

### 6.4 Components (`src/components`)

- **Dashboard**: agent status, portfolio ask panel, charts (`components/charts/*`, `components/dashboard/*`).
- **Diagnostics**: summary strip, charts panel, warnings (`components/diagnostics/*`).
- **Settings**: forms for automation (`components/settings/AgentAutomationForm.tsx`, etc.).
- **Agent run**: monitoring UI (`components/agent-run/AgentRunMonitor.tsx`).

### 6.5 Database (`prisma/`)

- **`schema.prisma`**: Single source of truth for tables (see §7).
- **`seed.ts`**: Creates demo user, `UniverseSegment` / `SegmentSymbol` / `Symbol` rows from `constants/universe.ts`, default `SearchProfile`, `AppSettings`, and scheduler-related defaults.

### 6.6 Configuration & tooling

- **`next.config.ts`**: Minimal (e.g. `reactStrictMode`).
- **`package.json`**: Scripts for `dev`, `build`, Prisma, Vitest, optional PM2 (`ecosystem.config.cjs`).
- **`vitest.config.ts`**: Unit test entry.

---

## 7. Data model (summary)

The schema is documented inline in `apps/web/prisma/schema.prisma`. Conceptual clusters:

| Cluster | Models (examples) |
|---------|-------------------|
| **Identity & settings** | `User`, `AppSettings`, `SearchProfile`, `AgentScheduleSettings` |
| **Universe** | `Symbol`, `UniverseSegment`, `SegmentSymbol` |
| **Market & features** | `MarketSnapshot`, `IndicatorSnapshot`, `FeatureSnapshot`, `ModelScore` |
| **Runs & decisions** | `DecisionRun`, `DecisionRunItem`, `DecisionSearchSnapshot`, `DecisionRunCandidate` |
| **Execution** | `PaperPosition`, `PaperTrade`, `QuoteSnapshot`, `PositionValuation`, `HoldingValueLog` |
| **Portfolio history** | `PortfolioSnapshot` |
| **Scheduler & locks** | `AgentRunLock` |
| **Diagnostics cache** | `TradeAttributionSnapshot` |

Important defaults on `AppSettings` include starting cash, max position %, buy/sell thresholds, stop/take-profit, cooldown, regime filter mode, optional vol targeting, and shorting parameters.

---

## 8. HTTP API surface (`apps/web/src/app/api`)

Public-ish (same-origin UI) JSON routes include:

| Route | Purpose |
|-------|---------|
| `GET/POST .../dashboard` | Dashboard JSON |
| `POST .../dashboard/ask` | Portfolio Q&A |
| `GET .../holdings`, `GET .../trades`, `GET .../decisions` | Lists for pages |
| `GET .../runs/latest`, `GET .../runs/[id]`, `GET .../runs/[id]/candidates` | Run detail |
| `POST .../runs/trigger` | Manual agent trigger (uses scheduler/trigger path) |
| `GET/POST .../settings`, agent-schedule, `next-run` | User settings & schedule |
| `POST .../settings/reset-paper` | Reset paper portfolio |
| `GET .../symbols`, `GET .../universe/segments` | Universe helpers |
| `GET .../performance/equity-curve`, `benchmark` | Charts data |
| `GET/POST .../diagnostics/*`, `POST .../diagnostics/rebuild` | Diagnostics |
| `GET .../search-profiles` | Search profiles |

Internal:

| Route | Purpose |
|-------|---------|
| `GET/POST .../internal/scheduler-tick` | Cron heartbeat → scheduler |
| `GET/POST .../internal/hourly-run` | Legacy/simple hourly kick (see docs) |
| `POST .../internal/backtest`, `rebuild-features` | Internal batch jobs |

All routes should be considered **implementation details**; prefer UI + `README` for operational entry points.

---

## 9. External integrations

| System | Role |
|--------|------|
| **PostgreSQL** | Primary datastore (`DATABASE_URL`; Docker maps **5433** → 5432). |
| **Twelve Data** | OHLCV + quotes when `TWELVE_DATA_API_KEY` set; rate limiting helpers in client code. |
| **OpenAI** | Chat Completions for Q&A, explainer, optional research variants (`OPENAI_API_KEY`, model env overrides). |
| **Trigger.dev / Vercel Cron** | Optional schedulers; **database** provider only needs something to call `scheduler-tick` with the secret. |

Environment variables are illustrated in `apps/web/.env.example` (NextAuth placeholders, demo email, internal secrets, mock data flags, optional `ML_SERVICE_URL`).

---

## 10. Testing and quality

- **Vitest** covers numerical stability and rule behavior (`portfolio/math.test.ts`, `features.test.ts`, `buyRules.test.ts`, `sellRules.test.ts`, `metrics.test.ts`, etc.).
- **Lint**: `next lint` script.
- Prisma **`db push`** / **`migrate`** keeps schema in sync; seed establishes a known-good universe and demo user.

---

## 11. Deployment & operations (conceptual)

1. Provision **PostgreSQL** and set **`DATABASE_URL`**.
2. Run **`npx prisma migrate deploy`** (or `db push` in controlled environments) and **`npm run db:seed`** for demo data.
3. Build **`npm run build`** and **`npm start`**, or use a platform runner (Vercel, etc.).
4. Configure **secrets** for internal routes in production.
5. Attach a **cron** job to **`/api/internal/scheduler-tick`** (or legacy hourly route per `docs/ARCHITECTURE.md`) with the bearer secret.
6. Optional: PM2 (`ecosystem.config.cjs`) for long-lived dev processes on a workstation — not a substitute for cloud scheduling.

---

## 12. Related documentation

- **`README.md`** — Quick start, scripts, stack table.
- **`docs/ARCHITECTURE.md`** — Concise architecture overview.
- **`docs/InvestBest_Cursor_Build_Spec.md`** — Original build requirements (referenced throughout code comments as §sections).

---

## 13. Document maintenance

When adding major features, update this file if:

- New **domains** appear (e.g. real auth, multi-user).
- The **agent pipeline** gains new stages or replaces rules-first scoring.
- **API routes** or **env vars** change in ways operators must know.

---

*Generated for the InvestBest repository to capture product intent and engineering structure as of the documented codebase layout.*
