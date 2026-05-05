# InvestBest — Architecture

## Layers

```
┌─────────────────────────────────────────────────────────────────┐
│  Dashboard (HTMX-ready templates + JS)                           │
│  /dashboard | /strategies | /signals | /notifications | /system   │
└─────────────────────────────────────────────────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI — REST API                                              │
│  /api/strategies | /api/signals | /api/notifications | /api/system│
└─────────────────────────────────────────────────────────────────┘
                                    │
┌──────────────┬──────────────┬──────────────┬────────────────────┐
│  Services    │  Strategies  │  Data        │  Tasks (Celery)    │
│  Backtest    │  Momentum    │  Polygon     │  ingest_daily_prices│
│  Notifications│  (plug-ins) │  FRED (TODO) │  generate_signals   │
└──────────────┴──────────────┴──────────────┴────────────────────┘
                                    │
┌─────────────────────────────────────────────────────────────────┐
│  DB (SQLite default / PostgreSQL)                                │
│  strategies, strategy_results, signals, positions, trades,      │
│  prices, macro_indicators, notification_log                       │
└─────────────────────────────────────────────────────────────────┘
```

## Strategy plug-ins

Each strategy under `backend/strategies/` can implement:

- **generate_signals(prices)** — returns DataFrame with timestamp, symbol, signal, confidence
- Backtest logic is centralized in `BacktestService`; strategy-specific logic is in `BacktestService.run()` (e.g. momentum in `_run_momentum`).

New strategies: add a module (e.g. `stat_arb.py`, `regime_detection.py`) and register in `BacktestService.run()` and `strategies/__init__.py`.

## Data flow

1. **Ingestion** (Celery or manual): Polygon → `prices`; FRED → `macro_indicators`.
2. **Signals**: Active strategies run over latest data → `signals` table.
3. **Portfolio**: (Phase 2) Combine signals → target positions.
4. **Execution**: (Phase 2) Alpaca (or IB) → `trades`, `positions`.

## Config

- `config/settings.py` — Pydantic settings from env.
- `config/.env` — Local secrets (copy from `.env.example`).
- `config/SERVICES_CHECKLIST.md` — List of accounts/APIs to obtain.

## Running

- **API + dashboard**: `PYTHONPATH=. uvicorn backend.main:app --reload --port 8000`
- **Celery worker**: `celery -A backend.tasks.celery_app worker -l info` (requires Redis and `REDIS_URL`)
