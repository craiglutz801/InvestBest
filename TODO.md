# InvestBest — TODO (build & operations)

Aligned with **`docs/InvestBest_Cursor_Build_Spec.md`**. Primary code lives under **`apps/web`** and **`apps/ml-service`**. Legacy Python/Jinja pieces (`backend/`, `frontend/`) are out of scope unless you explicitly revive them.

---

## Milestones still to complete

### Milestone 2 — ML ranking (replace rules-only scoring)

- [ ] Train **buy** and **sell-risk** models (LightGBM / XGBoost per spec) on historical features with **no future leakage**.
- [ ] Wire **`apps/ml-service`** `POST /score/batch` to real models; add feature parity with `apps/web` feature snapshots.
- [ ] Call ML service from **`hourlyMarketAgent`** (with fallback or feature flag when service unavailable).
- [ ] Implement **confidence** from calibration / margins / data completeness (spec §9), not LLM-invented.

### Milestone 3 — LLM explainer (polish)

- [ ] Harden prompts and structured inputs for **`writeDecisionExplainerSummary`** (per-symbol “top reasons” optional).
- [ ] Store explainer **prompt + raw response** in `notesJson` or a dedicated table if audits require it.

### Milestone 4 — Backtesting

- [ ] Offline **walk-forward** pipeline (Python: `ml-service/backtests/` or repo `research/`) — export metrics per spec §11.
- [ ] **`POST /api/internal/backtest`** (and/or UI page) — currently **501** stub.
- [ ] Trade log / performance **CSV or JSON export**.

### Milestone 5 — Real brokerage (structure only)

- [ ] Broker adapter interface + **Alpaca** paper/live placeholder (env vars in `.env.example` only; no live execution in MVP).

---

## `apps/web` — engineering backlog

### Scheduler & jobs

- [ ] **Trigger.dev** — hourly task with retries, overlap guard, observability (spec prefers this over cron-only).
- [ ] Align **Vercel Cron** with **`CRON_SECRET`** / **`INVESTBEST_INTERNAL_SECRET`** in project settings; document rotation.
- [ ] **Failure alerts** — email/Slack/PagerDuty when `DecisionRun.status === "failed"` (spec §14).

### Data & resilience

- [ ] **Finnhub** optional client (`lib/data-provider/finnhub.ts`) behind `newsEnabled` / Phase 2 features.
- [ ] Retries/backoff for Twelve Data; **degraded** runs when too many symbols fail (partial success already partially there via skip items).
- [ ] **Indicator snapshots** — persist computed RSI/SMA/ATR etc. into `IndicatorSnapshot` (currently only market + feature JSON paths are heavy users).

### Product / rules

- [ ] **`lib/decision/agent.ts`** — extract orchestration from monolithic `hourlyMarketAgent` if it grows further.
- [ ] **`lib/portfolio/simulator.ts`** — isolate buy/sell/pnl math for reuse in backtests.
- [ ] Enforce **paper window** (`paperStartDate` / `paperEndDate`) in agent (skip or no-op outside window).
- [ ] **`PUT /api/symbols`** — richer “allowed universe” UX (bulk activate/deactivate + name/exchange edits).

### Auth & users

- [ ] **Clerk or NextAuth** — replace `requireDefaultUser` / demo email with real sessions; keep schema `User`-centric.

### Testing

- [ ] **Integration tests** — hourly pipeline against test DB (idempotency, no double trades, sell-before-buy).
- [ ] Tests for **cooldown** and **max new positions** in agent (not only rule unit tests).

### Docs (repo)

- [ ] **`docs/TRADING_RULES.md`**, **`docs/DATA_MODEL.md`** (spec §24) — expand from `ARCHITECTURE.md` if you want operator-facing detail.

---

## `apps/ml-service`

- [ ] **`training/train_buy_model.py`**, **`training/train_sell_model.py`** — data pull, labels (e.g. 5d forward return / downside), export `model_version`.
- [ ] **`app/features.py`** — shared normalization with web feature store if scores must match.
- [ ] Container / **Railway / Render** deploy notes next to FastAPI app.
- [ ] Optional **`pyproject.toml`** to lock versions (spec §24).

---

## Accounts, keys & env (spec stack)

### Required for production-like runs

- [ ] **PostgreSQL** — e.g. **Neon** + `DATABASE_URL` in `apps/web/.env` (see root **`docker-compose.yml`** for local).
- [ ] **Twelve Data** — `TWELVE_DATA_API_KEY` (or keep `USE_MOCK_MARKET_DATA=true` for dev).
- [ ] **Vercel** (or host of choice) — deploy `apps/web`; set env vars; connect cron to internal hourly route with secret.

### Optional / Phase 2

- [ ] **OpenAI** — `OPENAI_API_KEY` for richer run summaries (`OPENAI_MODEL` optional).
- [ ] **Finnhub** — `FINNHUB_API_KEY` for news/fundamentals enrichment.
- [ ] **Trigger.dev** — `TRIGGER_SECRET_KEY`, `TRIGGER_PROJECT_ID` when adopted.

### Quick env setup

- [ ] Copy **`.env.example`** → **`apps/web/.env`** and fill values.
- [ ] Run **`npm run db:push`** (or migrate) and **`npm run db:seed`** after DB is up.

---

## Legacy stack (`backend/`, `frontend/`, `config/`)

If you still use the old FastAPI app, see historical **`config/.env.example`** and **`config/SERVICES_CHECKLIST.md`** for Polygon/Alpaca/FRED/etc. **Not required** for the new Next.js MVP path above.

---

**Quick reference:** Build spec — `docs/InvestBest_Cursor_Build_Spec.md` · Architecture — `docs/ARCHITECTURE.md` · Runbook — root `README.md`.
