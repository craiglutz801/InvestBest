# InvestBest architecture (2026 MVP)

This repo implements the **InvestBest Cursor Build Spec**: a paper-trading web app with hourly decision runs, Postgres persistence, and a path to ML scoring and LLM explanations only.

**Research / paper trading only — not evidence of alpha, not financial advice, not a live broker.** The active Next.js runtime (`apps/web`) is fail-closed to `EXECUTION_MODE=paper`. Legacy Alpaca fields under `config/` and `backend/` are isolated from this app and must not be wired. See [`docs/PAPER_VALIDATION_RUNBOOK.md`](PAPER_VALIDATION_RUNBOOK.md).

## Primary application (`apps/web`)

- **Framework**: Next.js App Router, TypeScript, Tailwind, shadcn-style UI primitives, Recharts.
- **Data**: PostgreSQL + Prisma (`prisma/schema.prisma`). Market snapshots, feature snapshots, model scores, decision runs/items, paper positions/trades, portfolio snapshots.
- **Market data**: Twelve Data client (`src/lib/data-provider/twelveData.ts`). Use `USE_MOCK_MARKET_DATA=true` or omit `TWELVE_DATA_API_KEY` for deterministic mock series.
- **Scoring (Milestone 1)**: Rules-based signals in `src/lib/portfolio/features.ts` (`rulesScores`) plus explicit buy/sell rule modules.
- **Orchestration**: `src/lib/jobs/hourlyMarketAgent.ts` implements the §14 pipeline (sells before buys, idempotent hourly key, portfolio snapshot, optional explainer).
- **Scheduler (fallback)**: `apps/web/vercel.json` cron → `GET /api/internal/hourly-run` with `Authorization: Bearer` matching `CRON_SECRET` / `INVESTBEST_INTERNAL_SECRET`. Trigger.dev is the preferred long-term option per spec.
- **Auth**: Single demo user from seed (`INVESTBEST_DEMO_EMAIL`). Multi-user auth can replace `requireDefaultUser` later.

## ML service (`apps/ml-service`)

- FastAPI stub: `POST /score/batch`, `GET /health`, training/backtest routes return 501 until Milestones 2–4.

## Legacy stack

- `backend/`, `frontend/`, `research/` remain as earlier experiments; the spec-aligned product path is `apps/web` + `apps/ml-service`.

## Local database

```bash
docker compose up -d
# DATABASE_URL=postgresql://investbest:investbest@localhost:5433/investbest
cd apps/web && npm run db:push && npm run db:seed
```

## Key docs

- **NorthstarAlpha master vision and architecture:** [`docs/NORTHSTARALPHA.md`](NORTHSTARALPHA.md)
- Build requirements: `docs/InvestBest_Cursor_Build_Spec.md`
