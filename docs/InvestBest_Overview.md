# InvestBest — What It Is

**InvestBest** is a **paper-trading** web application: it simulates buying and selling U.S. equities and ETFs with a notional portfolio (for example, $100k starting cash) using **rules-based** signals—not live broker execution and not guaranteed investment returns. The purpose is to **research, observe, and audit** how a systematic strategy behaves over time: what it would buy or sell, why, and how the simulated portfolio and benchmark compare.

---

## Purpose

- **Learning & experimentation** — Try position sizing, risk settings, and universe constraints without capital at risk.
- **Transparency** — Each agent run produces **decision records**, per-symbol scores, and optional run logs so you can trace *why* a symbol was skipped, bought, or sold.
- **Operational realism (within limits)** — The app models **slippage**, **cash reserves**, **cooldowns after sells**, and **data staleness** so results reflect frictions you would care about in production—still a simulation, not a substitute for professional advice.

---

## Architecture at a Glance

| Layer | Technology |
|--------|------------|
| **App** | Next.js 15 (App Router), React, Tailwind, shadcn-style UI |
| **Data access** | Prisma ORM → **PostgreSQL** |
| **Market data** | **Twelve Data** API (with **mock/synthetic** mode when no key or `USE_MOCK_MARKET_DATA=true`) |
| **Scheduled runs** | HTTP trigger (e.g. cron → `/api/internal/hourly-run`) with secret protection |

A separate **ML scoring service** (`apps/ml-service`, FastAPI stub) exists for future batch scoring; the active “brain” in the web app today is **deterministic rules** (technical features + thresholds), not a black-box model.

---

## Backend: How a Run Works

1. **Universe** — The agent loads a curated set of tradable symbols (segments, caps, free-tier friendly ordering for API limits).
2. **Ingest & features** — For each symbol it pulls daily OHLCV (or mock bars), computes **features** (returns, volatility, RSI-style measures, etc.), and derives **model scores**: buy score, sell-risk score, confidence.
3. **Sells first** — Open positions are evaluated against **sell rules** (stop loss, take profit, trailing give-back, momentum/confidence breakdowns, stale-quote policy). Executed sells update **cash** and **paper trades**.
4. **Regime & liquidity (optional)** — Benchmark (e.g. SPY) may **throttle** how many new buys are allowed in rough market regimes. Symbols below a minimum **average dollar volume** can be blocked when that setting is enabled.
5. **Buys** — Remaining symbols are filtered by **buy rules** (score thresholds, cash reserve, volatility stretch, cooldown, liquidity). Candidates are ranked; the agent sizes positions using caps and optional **volatility-targeted** scaling, then records **buys** and new/updated **positions**.
6. **Persistence** — Results land in PostgreSQL: `DecisionRun`, `DecisionRunItem`, `PaperTrade`, `PaperPosition`, `PortfolioSnapshot`, and (when enabled) **candidate explorer** rows and progress notes for the UI.

The UI (**Dashboard**, **Decisions**, **Explorer**, **Settings**) reads this data to show equity vs benchmark, drawdown, allocation, holdings, and run history.

---

## Important Caveat

InvestBest is a **tool for simulation and education**. Past or simulated performance does not predict future results. It is **not** financial, tax, or legal advice.
