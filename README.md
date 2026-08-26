# InvestBest

Paper-trading web app: hourly agent, curated equity/ETF universe, auditable decisions, $100k simulated portfolio. Built to **InvestBest Cursor Build Spec** (`docs/InvestBest_Cursor_Build_Spec.md`).

**Research / paper trading only.** Results are simulated, are **not** evidence of alpha, are **not** a live track record, and are **not** financial advice. The active runtime has no live-broker or real-money order path. Required capability boundary: `EXECUTION_MODE=paper` (missing or any other value fails closed). Operator pause/kill and the validation soak are documented in [`docs/PAPER_VALIDATION_RUNBOOK.md`](docs/PAPER_VALIDATION_RUNBOOK.md).

## New stack (spec-aligned)

| Area | Choice |
|------|--------|
| App | `apps/web` — Next.js 15, Prisma, Tailwind, Recharts |
| DB | PostgreSQL (e.g. local Docker or Neon) |
| Data | Twelve Data (+ mock mode) |
| Jobs | Render Cron recommended for production execution; Vercel remains the UI / reporting layer |
| ML | `apps/ml-service` — FastAPI stub for `/score/batch` |

Architecture overview: **`docs/ARCHITECTURE.md`**.

### Quick start (web + DB)

```bash
cp .env.example apps/web/.env
# Edit DATABASE_URL and optional API keys

docker compose up -d
# Postgres is on host port 5433 (see docker-compose.yml).

cd apps/web
npm install
npx prisma generate
npx prisma db push
npm run db:seed
npm run dev
```

Open **http://localhost:3000** → Dashboard. Use **Settings → Run hourly agent now** or wait for cron.

### Scripts (`apps/web`)

- `npm run dev` — dev server
- **Keep dev server alive across crashes / reboot** — see [`docs/Local_Dev_Server_Persist.md`](docs/Local_Dev_Server_Persist.md) (PM2 + honest note about sleep vs cloud).
- `npm run build` / `npm start` — production
- `npm run agent:tick` — run one scheduler tick in-process (best for Render Cron)
- `npm run db:push` / `npm run db:migrate` — schema
- `npm run db:seed` — demo user + universe symbols
- `npm test` — Vitest (portfolio math + rules)

### Production recommendation

Use **Vercel** for the web UI and **Render Cron** for actual agent execution.

- Blueprint file: [`render.yaml`](render.yaml)
- Render cron runtime command: `npm run agent:tick`
- Replace the old `curl https://.../api/internal/scheduler-tick` cron job with this direct command-based cron
- Keep `USE_MOCK_MARKET_DATA=false`
- Start with `INVESTBEST_MAX_UNIVERSE_SYMBOLS=28` so runs finish reliably

## Legacy layout

Older FastAPI/Jinja pieces remain under `backend/`, `frontend/`, `research/` for reference; active development for this spec is under `apps/`.

## License

Private / personal use.
