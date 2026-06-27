# InvestBest_V2

`InvestBest_V2` is a clean-room successor to the current InvestBest app.

It keeps the best ideas from V1:
- paper-trading only
- transparent run logs
- explicit strategy modes
- explainable scoring

And it shifts the architecture toward what V1 was missing:
- research-first workflow
- validation-first promotion gates
- separate candidate, experiment, and model lifecycle
- strategy decay monitoring
- regression / factor modeling as a first-class lane

## Why it exists

V1 is useful as a live paper-trading sandbox, but it was not originally designed as a full research platform.
V2 is a separate app so we can build the stronger design without destabilizing the current deployment.

## Current state

This directory contains the first scaffold:
- a standalone Next.js app
- V2 product pages
- mock data and domain models that reflect the new architecture
- documentation for the V2 design direction

## Run locally

```bash
cd InvestBest_V2
npm install
cp .env.example .env.local
# Add your real ALPHA_VANTAGE_API_KEY to .env.local
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000).

## Runtime config

V2 reads `ALPHA_VANTAGE_API_KEY` from `InvestBest_V2/.env.local`.

- Without it, the earnings calendar fetch is skipped and the event-penalty logic stays effectively off.
- After adding or changing the key, restart `npm run dev`.

## What comes next

1. Add a real database schema for experiments, validations, model versions, and promotion gates.
2. Connect the V2 app to exported InvestBest datasets.
3. Build walk-forward validation and experiment scoring.
4. Add shadow-model promotion and decay monitoring.
