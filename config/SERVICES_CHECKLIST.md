# InvestBest — Services & Accounts Checklist

Use this list to obtain accounts and API keys. Check off as you go.

## Data Providers

| Service | Purpose | Get it | Status |
|--------|---------|--------|--------|
| **Polygon.io** | Equities prices, options, real-time | [polygon.io](https://polygon.io) | ☐ |
| **Alpha Vantage** | Prices, fundamentals, forex | [alphavantage.co](https://www.alphavantage.co/support/#api-key) | ☐ |
| **FRED** | Macro (rates, inflation, unemployment) | [fred.stlouisfed.org](https://fred.stlouisfed.org/docs/api/api_key.html) | ☐ |
| **News / RSS** | Headlines, sentiment | RSS feeds or NewsAPI | ☐ |

## Broker / Execution

| Service | Purpose | Get it | Status |
|--------|---------|--------|--------|
| **Alpaca** | Commission-free trading, paper + live | [alpaca.markets](https://alpaca.markets) | ☐ |
| **Interactive Brokers** | Optional; more products | [interactivebrokers.com](https://www.interactivebrokers.com) | ☐ |

## AI / Research

| Service | Purpose | Get it | Status |
|--------|---------|--------|--------|
| **OpenAI** | Strategy generation, sentiment, agents | [platform.openai.com](https://platform.openai.com/api-keys) | ☐ |

## Notifications (optional)

| Service | Purpose | Get it | Status |
|--------|---------|--------|--------|
| **SMTP** | Email alerts | Your email provider or SendGrid/Mailgun | ☐ |
| **Slack** | Webhook for alerts | [api.slack.com](https://api.slack.com/messaging/webhooks) | ☐ |
| **Telegram** | Bot for alerts | [BotFather](https://t.me/BotFather) | ☐ |

## Infrastructure (local or cloud)

| Service | Purpose | Notes |
|--------|---------|--------|
| **PostgreSQL** | Main database | Local: `brew install postgresql` or Docker |
| **Redis** | Cache + Celery broker | Local: `brew install redis` or Docker |

## Env vars to set (in `config/.env`)

After obtaining keys, set:

- `POLYGON_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `FRED_API_KEY`
- `ALPACA_API_KEY`, `ALPACA_SECRET_KEY`, `ALPACA_BASE_URL`
- `OPENAI_API_KEY`
- `DATABASE_URL`, `REDIS_URL`
- Optional: `SMTP_*`, `SLACK_WEBHOOK_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
