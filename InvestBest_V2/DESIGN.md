# InvestBest_V2 Design

## V2 principles

1. Research comes before trading.
2. A model is not "working" unless it survives holdout and walk-forward validation.
3. Paper execution is downstream of validation, not the proof of validation.
4. The durable asset is the research engine, not any single signal.
5. LLMs may help with explanation and hypothesis generation, but not with money-critical arithmetic.

## Core differences from V1

### V1
- centered on the hourly paper-trading loop
- score-based candidate ranking
- run logs and diagnostics
- strategy modes inside a single trading agent

### V2
- centered on experiment lifecycle and promotion gates
- explicit model registry
- validation battery as a first-class object
- candidate -> experiment -> incubating -> active -> decayed pipeline
- paper trading becomes one consumer of validated models

## Initial V2 modules

- `Dashboard`: portfolio, system state, active model, promotion queue
- `Research`: validation battery, leaderboard, experiment outcomes
- `Experiments`: structured experiment cards and model comparisons
- `Candidates`: hypothesis pipeline from source idea to approved test
- `System`: guardrails, monitor events, deployment mode
- `Chat`: grounded explanations over validated system data

## Near-term build order

1. Standalone UI scaffold
2. Shared V2 domain model
3. Validation engine service
4. Dataset ingestion from V1 / exported market history
5. Model registry + promotion gate
6. Shadow-run integration
