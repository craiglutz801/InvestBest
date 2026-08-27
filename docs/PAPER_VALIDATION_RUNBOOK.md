# NorthstarAlpha / InvestBest — paper validation runbook

This is a **research and paper-trading** system. Simulated results are **not** evidence of alpha, are **not** a live track record, and are **not** financial advice. No real-money or live-broker capability is in the active runtime.

Approved operator path: fail-closed `EXECUTION_MODE=paper` only. Do not merge this hardening as a live-trading release, and do not deploy brokerage keys.

## Preconditions (every environment)

1. Active app is `apps/web` (Next.js paper engine). Legacy `backend/` + `config/` Alpaca fields are unused isolation leftovers — do not wire them.
2. Set **exactly**:
   - `EXECUTION_MODE=paper`
   - `USE_MOCK_MARKET_DATA=false` for a market-data soak (or `true` only for local dry plumbing)
   - `TWELVE_DATA_API_KEY` when mock is off
3. Apply schema: `cd apps/web && npx prisma db push` (adds `AppSettings.agentPaused`).
4. Confirm the operator pause is **off** in Settings, and `AGENT_PAUSE` / `AGENT_KILL_SWITCH` are unset.
5. Keep shipped risk defaults unless a later approved change says otherwise: $100k starting cash, 10% max position, 10% cash reserve, 3 new positions/run, 8% stop, 15% take-profit, 24h cooldown, 0.05% slippage.

Missing, empty, or non-paper `EXECUTION_MODE` (including `live`) **cannot** start an agent run or mutate simulated positions.

## Operator pause / kill

| Control | Effect |
|---|---|
| Settings → Pause agent | Blocks manual and scheduled runs. History is kept. |
| `AGENT_PAUSE=true` or `AGENT_KILL_SWITCH=true` | Emergency kill; same fail-closed skip. |

Un-pausing does not backfill skipped hours.

## Ten-trading-day reliability soak

Goal: prove the paper engine stays fail-closed, auditable, and single-flight under real scheduler load.

**Daily (each US cash-session day):**

1. Confirm `EXECUTION_MODE=paper` is still set.
2. Confirm pause/kill is off unless you are testing it.
3. Let the scheduled tick run (or one manual run if the scheduler is not hosted).
4. Record for the day:
   - DecisionRun id, status (`completed` / `skipped` / `failed`)
   - Whether any `PaperTrade` rows were created
   - Data-quality skips (`MISSING_BARS`, `STALE_BARS`, `NON_FINITE`, `INCONSISTENT_OHLC`, `PARTIAL_SERIES`, `DUPLICATE_BARS`, `OUT_OF_ORDER_BARS`, `FUTURE_BARS`, `MISSING_QUOTE_TIMESTAMP`, `FUTURE_QUOTE`, other quote failures)
   - Duplicate/concurrent triggers: a second click or overlapping cron must return `skipped_in_progress` or `skipped_duplicate` and must not create a second trade set
5. Reconstruct **one sampled decision** from `DecisionRun.notesJson.audit` plus `FeatureSnapshot` / `PaperTrade` (settings version, feature inputs, reason code, slippage, cash before/after, portfolio after).

**Pass criteria after 10 trading days:**

- Zero runs with a non-paper execution mode
- Zero attempts to place a broker order (none exist in `apps/web`)
- Invalid/stale input produced skip/no-trade rows, never a fill
- SPY/benchmark series shorter than 200 bars (SMA200) produced **zero new buys**
- Quotes without an authoritative provider timestamp were treated as stale/no-trade, not fresh
- Missing or nonpositive volume was recorded as unusable (`PARTIAL_SERIES`), not coerced to a valid 0
- Duplicate, out-of-order, or materially future-dated bars/quotes produced skip/no-trade, never a fill
- Duplicate/concurrent triggers produced at most one trade set per hour bucket
- Cash / position / cooldown / stop / take-profit behavior still matches shipped defaults
- At least one sampled fill (if any trades occurred) reconstructs from persisted audit fields
- Pause test: flip pause on, trigger once, confirm skip and unchanged positions, then unpause

**Fail / stop-the-line:** any live-mode config, any broker SDK import, duplicate fills, or a trade from invalid data.

## Later 90-day shadow cohort

After the 10-day soak is clean, run the **same** long-only curated-universe paper engine for 90 calendar days as a shadow cohort:

- Paper only; no live broker, no strategy optimization, no LLM trade decisions
- Keep risk defaults frozen
- Weekly: sample 3 decisions for audit completeness; review skip reason-code mix; confirm locks still serialize
- Do **not** interpret equity curve, hit rate, or vs-benchmark charts as proof of alpha
- Cohort output is operational reliability + reproducibility, not a performance claim

## Useful commands

```bash
cd apps/web
npm test
npm run agent:tick   # one scheduler tick; still requires EXECUTION_MODE=paper
```

Settings → Run agent now shares the same lock and admission gates as the scheduler.
