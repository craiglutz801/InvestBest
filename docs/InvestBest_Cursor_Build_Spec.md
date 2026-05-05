# InvestBest Build Spec for Cursor
**Version:** 1.0  
**Date:** 2026-04-01  
**Goal:** Build a very simple AI-powered paper-trading web app that runs on an hourly schedule, decides what to pretend-buy and pretend-sell for stocks and commodities, and tracks performance from a starting paper balance of **$100,000** for **3 months**.

---

## 1) Product Summary

Build **InvestBest** as a lightweight web app with these core behaviors:

1. Every hour, an automated decision engine scans a fixed universe of stocks and commodities.
2. The system predicts which assets are most attractive to **buy now**.
3. The system also predicts which current holdings are most likely to **dip soon** and should be **sold now**.
4. The system does **not** place real trades initially.
5. Instead, it executes **paper trades**:
   - pretend buys
   - pretend sells
   - position tracking
   - cash balance tracking
   - realized and unrealized P&L
6. The UI makes it easy to see:
   - current paper holdings
   - trade history
   - current equity curve
   - agent decisions and reasoning
   - performance over the 3-month test

This is **not** a portfolio research terminal and **not** a social trading app. Keep it focused and simple.

---

## 2) Non-Negotiable Requirements

### Functional requirements
- Start with a pretend portfolio of **$100,000 cash**
- Run the decision engine **every hour**
- Make buy decisions automatically
- Make sell decisions automatically
- Log every action as if it really happened
- Track positions and portfolio value over time
- Show current holdings and performance in a simple dashboard
- Simulate for **3 months**
- No real brokerage execution yet
- Design the code so real execution can be enabled later with minimal refactor

### Product constraints
- Keep the app simple
- Favor reliability and maintainability over “fancy quant” complexity
- AI should be involved in decisions, but **not** as a free-form hallucinating trader
- Use AI in a structured, auditable way:
  - ML/ranking model for signal generation
  - LLM only for explanation / summarization / optional tie-breaking
- Every decision must be reproducible from stored inputs

### Safety / realism requirements
- Do **not** market this internally as guaranteed prediction
- Do **not** make unrestricted all-in bets
- Add hard portfolio constraints:
  - max position size
  - max new buys per run
  - minimum liquidity filter
  - stop-loss / take-profit rules
  - cash reserve rules
- Log why a trade was made
- Log model score, confidence, and the features used

---

## 3) Recommended Stack

This is the stack I want Cursor to use unless there is a very strong implementation reason not to.

### Frontend
- **Next.js** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui**
- **Recharts** for charts

### Backend / app server
- **Next.js server routes** for app APIs
- **Background jobs** using **Trigger.dev** for durable scheduled runs  
  Why: It is purpose-built for scheduled tasks, retries, monitoring, concurrency controls, and long-running AI workflows.

### Database
- **Postgres**
- **Prisma ORM**
- Recommended hosted DB: **Neon Postgres**

### Auth
- **Clerk** or **NextAuth**
- If auth slows down the MVP, ship single-user local auth first, but structure the app so multi-user auth can be added later

### Market data
Use a **single primary provider** for MVP simplicity.

#### Primary recommendation: Twelve Data
Use Twelve Data as the main market-data provider because it gives one API surface for stocks, commodities, time series, quotes, and technical indicators, which keeps the MVP much simpler than stitching together multiple vendors.

Use it for:
- price history
- quotes
- symbol metadata
- technical indicators
- commodities coverage

#### Secondary / optional enrichment: Finnhub
Use Finnhub only for:
- company news
- basic fundamentals
- sentiment-related enrichment for equities

Do not make Finnhub a hard dependency for the first working version.

### AI / ML
- **Python microservice** for feature engineering and model scoring
- **FastAPI** for internal scoring API
- **pandas**, **numpy**
- **scikit-learn**
- **XGBoost** or **LightGBM** for the first production model
- **OpenAI API** for natural-language explanations only

### Deployment
- **Vercel** for the Next.js app
- **Neon** for Postgres
- **Trigger.dev** for scheduled jobs
- Python scoring service can be:
  - deployed separately on Railway / Render / Fly.io, or
  - containerized and deployed wherever easiest

---

## 4) Why This Approach Is Best For The MVP

The easiest way to fail is to build an “AI trader” that is really:
- a giant prompt,
- unpredictable,
- impossible to audit,
- impossible to backtest.

Do **not** do that.

### Correct decision architecture
Use this separation:

#### Layer A — Quant scoring model
A structured ML model outputs:
- short-term upside score
- short-term downside risk score
- expected move
- confidence score

#### Layer B — Portfolio rules engine
The rules engine decides:
- can we buy?
- how much can we buy?
- must we sell?
- is this blocked by risk rules?

#### Layer C — LLM explainer
The LLM converts the structured output into human-readable reasoning:
- “Bought GLD because momentum is positive, volatility is acceptable, and the expected 5-day return rank was top 3 in the universe.”

The LLM may **not** invent trades.
It can explain trades.
It can summarize trades.
It can optionally rank between two nearly-equal candidates only if all raw metrics are provided and stored.

---

## 5) MVP Scope

The MVP should focus on a curated universe and avoid trying to scan the whole market.

### Trading universe for MVP
Use a small, fixed watchlist:
- 20–30 large-cap stocks
- 5–10 commodity-linked ETFs or commodity symbols

### Suggested initial universe
#### Stocks
- AAPL
- MSFT
- NVDA
- AMZN
- META
- GOOGL
- TSLA
- JPM
- XOM
- UNH
- COST
- WMT
- AMD
- NFLX
- BRK.B
- AVGO
- LLY
- GE
- CAT
- CRM

#### Commodity proxies / ETFs
- GLD
- SLV
- USO
- UNG
- DBA
- DBA can be optional if pricing/feed is awkward
- CPER or copper proxy if available
- PPLT optional
- commodity symbols from Twelve Data if cleaner than ETFs

### Important note
For simplicity and consistent liquidity, **prefer ETFs as the initial commodity exposure layer** rather than raw futures contracts. This avoids futures-specific issues such as rollover logic, expiry, contract selection, margin assumptions, and irregular liquidity.

---

## 6) Exact User Experience To Build

The app should have exactly these screens:

### A. Dashboard
Show:
- total portfolio value
- current cash
- invested capital
- unrealized P&L
- realized P&L
- total return %
- benchmark comparison (SPY)
- equity curve chart
- today’s latest decisions
- latest buys
- latest sells
- top current winners
- top current losers

### B. Holdings page
Table with:
- symbol
- asset type
- shares/units
- average cost
- current price
- market value
- unrealized P&L $
- unrealized P&L %
- current model score
- current sell-risk score
- holding since
- last agent note

### C. Trades page
Chronological log:
- datetime
- symbol
- action (BUY / SELL)
- quantity
- execution price (paper)
- fees (default 0 for MVP unless explicitly simulated)
- reason
- model confidence
- expected horizon
- before cash / after cash

### D. Decisions page
Every hourly run should have a decision record:
- run timestamp
- universe scanned
- candidates considered
- scores generated
- risk blocks applied
- final buy list
- final sell list
- skipped symbols and why
- full model snapshot link

### E. Settings page
Configurable:
- starting cash
- max position size %
- max new positions per run
- target number of holdings
- stop loss %
- take profit %
- minimum confidence threshold
- allowed symbols
- enable/disable shorting (default OFF)
- enable/disable news enrichment (default OFF)
- run frequency (default hourly)
- paper trading start date / end date

---

## 7) Core System Design

Build the app as 5 logical subsystems.

### Subsystem 1: Market data ingestion
Responsibilities:
- fetch quotes
- fetch historical candles
- fetch metadata
- fetch indicator values
- store raw snapshots
- cache recent responses
- handle API failures gracefully

### Subsystem 2: Feature store
Responsibilities:
- convert raw market data into model features
- compute rolling stats
- compute momentum / volatility / mean reversion features
- store per-symbol feature snapshots at each run

### Subsystem 3: Scoring engine
Responsibilities:
- produce buy scores
- produce sell-risk scores
- produce expected short-term return estimates
- produce confidence values

### Subsystem 4: Portfolio simulator
Responsibilities:
- maintain cash
- maintain open positions
- process buys
- process sells
- compute realized and unrealized P&L
- compute daily/hourly equity snapshots

### Subsystem 5: Web UI
Responsibilities:
- make the state visible
- explain what the agent is doing
- make debugging easy

---

## 8) Exact Trading Logic To Implement First

Do not start with deep reinforcement learning.
Do not start with LSTMs.
Do not start with “agentic autonomous hedge fund” behavior.

Start with a robust and testable **rank-and-allocate** system.

### Buy-side logic
Every hourly run:

1. Gather fresh data for all symbols in universe
2. Compute/update features
3. Score every symbol for **near-term upside attractiveness**
4. Filter out symbols that fail hard constraints:
   - bad liquidity
   - huge recent volatility spike
   - price gap beyond threshold
   - already overweight
   - insufficient confidence
5. Rank remaining symbols
6. Buy top candidates until:
   - max new positions reached, or
   - no candidates exceed threshold, or
   - no cash available, or
   - target holdings count reached

### Sell-side logic
Every hourly run:

1. Re-score current holdings for **dip / downside risk**
2. Sell if any of these are true:
   - sell-risk score exceeds threshold
   - stop-loss hit
   - take-profit hit
   - momentum breakdown
   - model confidence collapses
   - holding no longer ranks in acceptable band
3. Record the reason category for the sale

### Position sizing logic
For MVP:
- equal weight or volatility-adjusted equal weight
- max 10% of portfolio in one position
- max 3 new positions per hourly run
- keep at least 10% cash reserve

Default position sizing formula:
- target_position_value = min( portfolio_value * 0.08, available_cash * 0.33 )

Round down to whole shares for stocks/ETFs.

---

## 9) Modeling Strategy

## Primary recommendation for first real model
Use **gradient-boosted trees** on engineered market features.

Preferred order:
1. **LightGBM**
2. **XGBoost**
3. Random Forest as fallback baseline

### Why
For this kind of tabular, mixed-feature financial ranking problem, boosted trees are usually a better first production choice than LSTMs because:
- faster to train
- easier to debug
- easier feature importance inspection
- more reliable on small/medium datasets
- simpler to backtest and iterate

### Prediction target
Use supervised learning with a short prediction horizon.

Start with:
- **5 trading day forward return** for buy ranking
- **5 trading day downside probability** for sell-risk ranking

You can train two separate models:
- `buy_model`
- `sell_model`

### Model outputs
For each symbol at each run:
- `buy_score` (0–100)
- `sell_risk_score` (0–100)
- `expected_return_5d`
- `expected_drawdown_risk_5d`
- `confidence_score` (0–100)

### Confidence
Confidence should not be invented by the LLM.
Compute confidence from a combination of:
- model calibration
- probability margin
- data completeness
- signal agreement across features

---

## 10) Features To Engineer

At minimum, compute these features per symbol.

### Price / return features
- 1h return
- 4h return
- 1d return
- 3d return
- 5d return
- 10d return
- 20d return

### Momentum features
- distance from 20-day moving average
- distance from 50-day moving average
- EMA crossover state
- momentum slope

### Volatility features
- rolling 5d volatility
- rolling 20d volatility
- ATR
- volatility regime percentile

### Mean reversion features
- RSI
- Bollinger band position
- z-score from recent mean

### Volume / participation features
- relative volume
- recent volume spike
- price-volume trend

### Market regime features
- SPY return
- SPY volatility
- VIX proxy if available
- sector ETF relative strength if applicable

### Cross-asset / commodity features
- dollar index proxy optional
- gold/oil trend proxies optional
- correlation to SPY over rolling window

### News / sentiment features (Phase 2)
- recent news count
- sentiment score
- earnings proximity flag
- headline volatility flag

---

## 11) Training / Backtesting Requirements

The system is incomplete if it only runs live paper trading. Build offline backtesting too.

### Must-have offline capabilities
- historical feature generation
- rolling-window training
- walk-forward backtesting
- benchmark comparison
- trade log export
- performance metrics export

### Backtest metrics
- CAGR or annualized return
- total return
- max drawdown
- Sharpe ratio
- win rate
- average winner
- average loser
- turnover
- exposure
- number of trades
- benchmark relative performance

### Walk-forward setup
Example:
- train on trailing 12 months
- score next week/day/hour windows depending on data resolution
- roll forward continuously

### Important
Do **not** leak future data.
All features must be built strictly from information available at decision time.

---

## 12) The Paper Trading Rules

This is the simulation engine behavior.

### Starting state
- cash = 100000
- no positions
- no leverage
- no margin
- no shorting for MVP
- no options
- no futures contracts in MVP

### Execution assumptions
For MVP:
- market order paper fills at most recent available price at run time
- add optional slippage:
  - default 0.05% for highly liquid equities / ETFs
- fees:
  - default 0 unless manually enabled

### Sell precedence
In each run:
1. evaluate sell rules first
2. free cash from sales
3. then evaluate buys

### No duplicate buys
Do not add to a position more than once in the same run.

### Cooldown rule
After selling a symbol, optional cooldown:
- default 24 hours before re-buying same symbol

---

## 13) Data Model / Database Schema

Use Prisma with a normalized but practical schema.

### Tables

#### `users`
- id
- email
- createdAt
- updatedAt

#### `app_settings`
- id
- userId
- startingCash
- maxPositionPct
- maxNewPositionsPerRun
- targetHoldings
- stopLossPct
- takeProfitPct
- minConfidence
- cashReservePct
- runFrequencyMinutes
- paperStartDate
- paperEndDate
- newsEnabled
- createdAt
- updatedAt

#### `symbols`
- id
- ticker
- name
- assetType
- exchange
- isActive
- dataProviderSymbol
- createdAt
- updatedAt

#### `market_snapshots`
- id
- symbolId
- timestamp
- open
- high
- low
- close
- volume
- source
- interval

#### `indicator_snapshots`
- id
- symbolId
- timestamp
- rsi
- sma20
- sma50
- ema12
- ema26
- macd
- atr
- bbUpper
- bbLower
- relVolume
- volatility5d
- volatility20d

#### `feature_snapshots`
- id
- symbolId
- timestamp
- featuresJson
- dataCompletenessScore

#### `model_scores`
- id
- symbolId
- timestamp
- buyScore
- sellRiskScore
- expectedReturn5d
- expectedDrawdownRisk5d
- confidenceScore
- modelVersion
- featureSnapshotId

#### `decision_runs`
- id
- userId
- startedAt
- finishedAt
- status
- universeSize
- candidatesCount
- buysCount
- sellsCount
- portfolioValueBefore
- portfolioValueAfter
- notesJson

#### `decision_run_items`
- id
- decisionRunId
- symbolId
- actionRecommendation
- rank
- blocked
- blockedReason
- buyScore
- sellRiskScore
- confidenceScore
- rationaleShort

#### `paper_positions`
- id
- userId
- symbolId
- quantity
- avgCost
- openedAt
- lastUpdatedAt
- isOpen

#### `paper_trades`
- id
- userId
- symbolId
- decisionRunId
- action
- quantity
- price
- slippagePct
- fees
- grossAmount
- reasonCode
- reasonText
- modelVersion
- confidenceScore
- executedAt

#### `portfolio_snapshots`
- id
- userId
- timestamp
- cash
- investedValue
- totalValue
- unrealizedPnl
- realizedPnl
- benchmarkValue

---

## 14) Hourly Job Pipeline

Implement one hourly orchestrator job.

### Job name
`hourly-market-agent`

### Steps
1. Load settings
2. Load tradable universe
3. Fetch fresh quotes + recent candles
4. Calculate indicators and features
5. Score buy and sell models
6. Load current positions
7. Evaluate sell decisions
8. Execute paper sells
9. Recalculate cash / portfolio state
10. Evaluate buy candidates
11. Execute paper buys
12. Save all decisions
13. Save portfolio snapshot
14. Generate natural-language summary
15. Mark run complete
16. Emit alert on failure

### Failure handling
- retry transient API failures
- keep idempotency keys so repeated runs do not double-trade
- log partial failures
- if data is incomplete for too many symbols, mark run as degraded

---

## 15) Exact Service Recommendation

## Primary recommendation
### App + scheduler
- **Vercel** for the web app
- **Trigger.dev** for durable hourly jobs

### Database
- **Neon Postgres**
- **Prisma**

### Market data
- **Twelve Data** as the single primary provider

### Optional enrichment
- **Finnhub** for company news/fundamentals

### ML service
- **FastAPI** Python service

### Reasoning / explanations
- **OpenAI API**

---

## 16) Trigger.dev / Scheduler Implementation Notes

Use Trigger.dev to:
- schedule an hourly recurring task
- run the full decision pipeline
- maintain retry behavior
- inspect logs
- view task history
- prevent duplicate overlapping runs

If Trigger.dev integration causes too much setup friction, fallback option:
- use **Vercel Cron** to call a secure internal route every hour

But the preferred implementation is Trigger.dev.

---

## 17) API Endpoints To Build

### App APIs
- `GET /api/dashboard`
- `GET /api/holdings`
- `GET /api/trades`
- `GET /api/decisions`
- `GET /api/settings`
- `PUT /api/settings`
- `POST /api/runs/trigger` (manual run)
- `GET /api/runs/:id`
- `GET /api/symbols`
- `PUT /api/symbols`
- `GET /api/performance/equity-curve`
- `GET /api/performance/benchmark`

### Internal secure endpoints
- `POST /api/internal/hourly-run`
- `POST /api/internal/rebuild-features`
- `POST /api/internal/backtest`

### Python scoring service
- `POST /score/batch`
- `POST /train/buy-model`
- `POST /train/sell-model`
- `POST /backtest/run`
- `GET /health`

---

## 18) UI Design Requirements

Keep the UI clean, modern, minimal.

### Visual priorities
- simple cards
- high readability
- no clutter
- clear green/red P&L indicators
- one main chart per section
- a strong dashboard summary at the top

### Required dashboard widgets
- Portfolio value
- Cash
- Total return
- Unrealized P&L
- Realized P&L
- Open positions count
- Last run status
- Equity curve
- Latest buys
- Latest sells
- Agent summary text

### Required charts
- equity curve
- portfolio vs SPY benchmark
- allocation by symbol
- realized monthly P&L (optional if easy)

---

## 19) Rule Engine Requirements

Create a dedicated rule engine module with explicit, testable rules.

### Buy blocks
Block a buy if:
- cash reserve would be violated
- confidence below threshold
- buy score below threshold
- symbol already held and pyramiding disabled
- price too extended from mean
- volatility above threshold
- spread/liquidity unacceptable
- cooldown active

### Sell triggers
Sell if:
- stop-loss triggered
- take-profit triggered
- sell-risk score above threshold
- momentum breakdown
- confidence collapse
- better ranked replacement needed and portfolio full

### Rule priority
1. hard risk exits
2. model-based exits
3. replacement / rebalance exits
4. new buys

---

## 20) Logging / Auditability

Every decision must be inspectable later.

### Log these for every run
- all inputs used
- model version
- feature snapshot ids
- thresholds used
- rankings generated
- positions before/after
- cash before/after
- final action list
- LLM explanation prompt and output
- execution assumptions

### Important
Store enough structured data that the app can explain:
- why something was bought
- why something was sold
- why something was skipped

without having to re-run the model.

---

## 21) LLM Usage Requirements

The LLM is **not** the trading model.

### Allowed LLM use cases
- Explain latest decisions in plain English
- Summarize portfolio changes
- Create dashboard narrative
- Convert structured model outputs into understandable notes
- Generate “top 3 reasons” for each action from provided inputs only

### Forbidden LLM behaviors
- deciding trades without structured scores
- inventing prices
- inventing signals
- using unstored hidden rationale
- overriding hard risk constraints

### Example explanation prompt pattern
The LLM should receive only structured data like:
- symbol
- current price
- buy score
- sell score
- confidence
- top features
- triggered rules
- action chosen

Then output:
- 2–4 sentence explanation
- concise bullet reasons
- no financial-advice language
- no certainty language

---

## 22) Performance Reporting Requirements

The app must compute and display:

### Portfolio metrics
- current value
- cumulative return
- return since inception
- realized P&L
- unrealized P&L
- max drawdown
- best trade
- worst trade
- win rate
- average holding period
- turnover

### Benchmarking
Track SPY as default benchmark:
- if $100,000 had been invested in SPY at start
- compare current value
- compare return %
- compare drawdown visually

---

## 23) Initial Milestones

Build in this order.

### Milestone 1 — Working paper trader without ML
Build:
- dashboard
- universe config
- hourly scheduler
- data ingestion
- simple rules-based signals
- paper portfolio
- holdings/trades/performance

Use a baseline signal such as:
- buy when momentum + trend alignment + RSI not overbought
- sell on stop-loss / momentum breakdown / take-profit

This gets the full product loop working.

### Milestone 2 — Replace rules-only scoring with ML ranking
Build:
- offline training pipeline
- feature snapshots
- buy/sell model
- score integration
- confidence computation

### Milestone 3 — Add LLM explanations
Build:
- decision explanations
- summary cards
- daily summary text

### Milestone 4 — Add backtesting page
Build:
- historical simulation runner
- metric tables
- strategy comparison

### Milestone 5 — Add optional real brokerage adapter
Structure but do not enable:
- brokerage interface
- Alpaca paper/live adapter placeholder

---

## 24) Files / Project Structure To Generate

Create a monorepo or a clean single repo.

Recommended structure:

```text
investbest/
  apps/
    web/
      src/
        app/
        components/
        lib/
        server/
        styles/
      prisma/
      public/
      package.json
    ml-service/
      app/
      models/
      training/
      backtests/
      requirements.txt
      pyproject.toml
  packages/
    shared/
      types/
      constants/
      utils/
  docs/
    ARCHITECTURE.md
    TRADING_RULES.md
    DATA_MODEL.md
  .env.example
  docker-compose.yml
  README.md
```

### Key modules in `apps/web`
- `lib/data-provider/twelveData.ts`
- `lib/data-provider/finnhub.ts`
- `lib/portfolio/simulator.ts`
- `lib/rules/buyRules.ts`
- `lib/rules/sellRules.ts`
- `lib/decision/agent.ts`
- `lib/decision/explainer.ts`
- `lib/performance/metrics.ts`
- `lib/jobs/hourlyMarketAgent.ts`

### Key modules in `apps/ml-service`
- `app/main.py`
- `app/scoring.py`
- `app/features.py`
- `training/train_buy_model.py`
- `training/train_sell_model.py`
- `backtests/walk_forward.py`

---

## 25) Environment Variables

Create `.env.example` with at least:

```env
DATABASE_URL=
NEXTAUTH_SECRET=
NEXTAUTH_URL=
OPENAI_API_KEY=
TWELVE_DATA_API_KEY=
FINNHUB_API_KEY=
TRIGGER_SECRET_KEY=
TRIGGER_PROJECT_ID=
ML_SERVICE_URL=
APP_BASE_URL=
```

Optional future vars:
```env
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_PAPER=true
```

---

## 26) Acceptance Criteria

The MVP is complete only when all of the following are true:

1. I can open the app and see a dashboard with current paper portfolio value
2. The system starts at $100,000
3. A scheduled hourly run actually happens automatically
4. Each run scans the allowed symbol universe
5. The app creates paper buy/sell events automatically
6. Holdings update correctly after buys and sells
7. Cash updates correctly
8. Realized and unrealized P&L update correctly
9. I can view all historical paper trades
10. I can see why each trade happened
11. I can see current holdings and each holding’s performance
12. The system can run for a 3-month paper trading window
13. The code is clean enough to later swap paper execution for real execution
14. Model scores and decision data are stored and auditable
15. The app handles provider/API failure without corrupting the portfolio

---

## 27) Engineering Quality Requirements

Cursor should build production-style code quality even for MVP.

### Code quality
- strict TypeScript
- linting + formatting
- schema validation with Zod
- centralized error handling
- typed API responses
- idempotent trade execution logic
- unit tests for portfolio math
- unit tests for buy/sell rules
- integration tests for hourly run pipeline

### Testing requirements
At minimum test:
- buy execution math
- sell execution math
- average cost calculation
- realized P&L calculation
- portfolio value calculation
- stop-loss trigger
- take-profit trigger
- cooldown enforcement
- no duplicate run double-execution

---

## 28) Important Product Decisions

Cursor should follow these product decisions exactly:

### Do
- keep the universe curated
- keep the UI simple
- use structured ML
- use paper trading first
- prioritize transparency
- prefer ETFs for commodity exposure first
- build for future live-trading extensibility

### Do not
- do live trading yet
- use free-form LLM trade generation
- support options/futures/shorting in MVP
- try to predict every ticker in the market
- build social/community features
- overcomplicate the first version

---

## 29) Future Phase (Not Now, But Architecture Should Allow)

Later, after 3-month paper validation:
- enable brokerage adapter
- real order placement
- broker reconciliation
- notifications
- watchlists
- alerting
- model retraining dashboard
- strategy comparison
- multi-user support
- advanced risk controls
- tax lots / FIFO/LIFO support
- paper/live mode switch

---

## 30) Final Build Instruction To Cursor

Build **InvestBest** exactly as a simple, reliable, AI-assisted paper-trading web app.

The product should:
- run hourly,
- score a curated universe of stocks and commodity proxies,
- decide pretend buys and pretend sells,
- track a $100,000 paper portfolio,
- show holdings and performance clearly,
- store decision reasoning,
- be architected for later live execution.

Start with a working end-to-end MVP even if the initial scoring model is rules-based.
Then upgrade the scoring engine to gradient-boosted ML ranking.
Use the LLM only for explanations, not for raw trading authority.

---

## 31) Recommended External References For Cursor

Use these as implementation references while building. Verify the latest docs during implementation.

### Twelve Data
- Market data overview: https://twelvedata.com/market-data
- Docs: https://twelvedata.com/docs
- Commodities catalog: https://twelvedata.com/docs/llms/asset-catalogs/commodities-list
- Pricing: https://twelvedata.com/pricing

### Finnhub
- API docs: https://finnhub.io/docs/api

### Trigger.dev
- Product/docs entry: https://trigger.dev/

### Vercel
- Project configuration / cron support: https://vercel.com/docs/project-configuration
- vercel.json docs: https://vercel.com/docs/project-configuration/vercel-json
- Functions docs: https://vercel.com/docs/functions
- Storage overview: https://vercel.com/docs/storage

### Alpaca (future live/paper broker integration)
- Trading API docs: https://docs.alpaca.markets/docs/getting-started-with-trading-api
- Market data docs: https://docs.alpaca.markets/docs/getting-started-with-alpaca-market-data

---

## 32) Recommendation Summary

If Cursor asks “what exact stack should I use?”, the answer is:

- **Next.js + TypeScript + Tailwind + shadcn/ui**
- **Postgres + Prisma + Neon**
- **Trigger.dev** for hourly jobs
- **Twelve Data** as primary market data provider
- **Finnhub** as optional enrichment
- **FastAPI + LightGBM/XGBoost** for scoring
- **OpenAI API** for explanations
- **Vercel** for deployment

That is the recommended MVP architecture.

