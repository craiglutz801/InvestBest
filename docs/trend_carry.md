# Stage 3 — Multi-speed trend and futures carry (research)

**Status:** research-only draft  
**Package:** `research/trend_carry` (`northstar_trend_carry`)  
**Roadmap:** `docs/NorthstarAlpha_Chan_Integration_Roadmap.md` Stage 3  
**Safety:** not wired to the hourly agent, portfolio engine, broker, or live/paper orders

This note documents what the module computes, what it must not be used for, and
which listed-contract fields a later real-data shadow test will need.

## What this stage is for

Trend should be a **diversified primary return engine**, not one lookback
indicator. Futures carry should inform **confidence** without double-counting
the same exposure as trend, and without confusing a back-adjusted research
series with executable contract P&L.

The module therefore:

1. Evaluates a **multi-speed time-series momentum ensemble** (defaults around
   21 / 63 / 126 / 252 trading days ≈ 1m / 3m / 6m / 12m).
2. **Volatility-normalizes** each horizon return and **caps** strength.
3. Attaches **explicit horizon metadata** to every result.
4. Emits a **cross-asset research signal contract** (diagnostic weights only).
5. Reports **neighboring-parameter / plateau** robustness and **refuses** to
   select a single optimized lookback from a performance sweep.
6. Reports **trend-health** ingredients: horizon agreement, persistence,
   whipsaw rate, volatility-shock state, breadth.
7. Exposes **provider-neutral** futures chain / roll / carry types.
8. Keeps **research continuous series** and **executable contract economics**
   as separate objects.
9. Hooks **Edge-to-Friction** using Stage 1 field names when that package is
   installed, otherwise a local fallback. There is **no hard branch
   dependency** on Stage 1.

## What these calculations can establish

| Object | Can establish |
|---|---|
| Horizon / ensemble strength | Whether trailing returns, after vol scaling and caps, point the same way across configured speeds **in the supplied sample**. |
| Horizon agreement | Whether short and long speeds currently agree. Disagreement is a research warning, not a veto authority. |
| Persistence / whipsaw | How often the point-in-time ensemble sign flipped in a trailing window. |
| Vol shock | Whether current realized vol is elevated vs a trailing median. |
| Plateau report | Whether neighboring lookbacks share a sign (a stability property). |
| Carry / curve state | Contango vs backwardation and an annualized roll-yield **from caller-supplied, temporally aligned prices**. The front/deferred **curve gap is carry**, not a cost. |
| EFR hook | Whether a **caller-supplied** expected edge covers **caller-supplied execution friction**, including futures *roll transaction* costs when known. |

## What they cannot establish

- That a trend “works” or should be promoted to paper/live.
- That one lookback is the correct trading parameter (the module will not pick it).
- That back-adjusted continuous prices equal tradeable P&L.
- That short expression is permitted by the broker or RiskGovernor.
- Expected edge or **execution** friction from market data when bid/ask/fees are absent (those remain caller inputs; the curve gap is not a substitute).
- Live contract selection, roll execution, leverage, or order routing.

Health labels (`healthy` / `mixed` / `degraded`) are **research tags**. Stage 4
owns formal throttle / pause / retire contracts. Nothing here places an order.

Stage 6's native adapter calls `evaluate_asset_trend(series, config, *, as_of=)`
and `refuse_performance_sweep_selection`. Those signatures are unchanged by the
carry/friction correction. CarrySnapshot no longer exposes
`estimated_roll_friction`; Stage 6 does not read that field.

## Ensemble construction (no optimized lookback)

For lookback \(L\):

```text
raw_return     = P[t] / P[t-L] - 1
daily_vol      = stdev(log-returns over vol_lookback, ddof=1)
strength       = raw_return / (daily_vol * sqrt(L))
capped         = clip(strength, -signal_cap, +signal_cap)
ensemble       = mean(usable capped strengths)
```

`ensemble_method` is always `equal_weight_capped_horizons`.
`neighboring_parameter_plateau` and `refuse_performance_sweep_selection` set
`selected_lookback = None` and `refuses_single_horizon_selection = True`.

`allow_short` only controls **research expression**. Negative strength may be
flattened to flat. That flag is not broker permission and does not enable live
shorting.

Cross-asset `research_weights` are L1-normalized, vol-targeted diagnostic
weights. They are **not** written into the live portfolio engine.

## Point-in-time rule

Every historical call takes `as_of` (inclusive index or timestamp). Quotes,
prices, and roll events after that cutoff are ignored. Continuous-series roll
adjustments use only same-session (or earlier) prices of the outgoing and
incoming contracts. Missing old-front quotes are **not** filled from the
future.

Carry snapshots additionally fail closed when:

- any observation `root` does not match `ContractChain.root`;
- the front or deferred quote is older than `QuoteSyncConfig.max_quote_age` vs `as_of` (default 3 days);
- front and deferred quote timestamps differ by more than `max_front_next_skew` (default 1 day).

Stale or misaligned pairs do **not** produce a usable contango/backwardation/carry reading.

## Research continuous vs executable economics

| Representation | Use | Must not be used as |
|---|---|---|
| `ResearchContinuousSeries` | Trend research on a back-adjusted path (`not_executable_pnl=True`) | Trade P&L, margin, or an order |
| `ExecutableContractEconomics` | Which listed contract is front, DTE, roll direction, **curve/roll gap** (carry), and **execution** roll friction when bid/ask are present | A continuous price series, a broker instruction, or a substitute for carry |

Trend on the continuous series and carry on the listed curve are **complementary
context**. Do not add them as if they were independent bets on the same contract
without an explicit exposure map (out of scope here).

## Friction / Stage 1 relationship

Stage 1 (`research/statistical_diagnostics`, draft PR) defines:

```text
EFR = expected_gross_edge / expected_round_trip_friction
```

with components: commission, spread, slippage, market_impact, borrow_fees,
dividend_substitute, financing, futures_roll, other.

This package copies those field names on `FrictionInputs`. 
`research_edge_to_friction`:

1. Tries `from northstar_diagnostics.efr import edge_to_friction_ratio`.
2. If that import fails, computes the same ratio locally.

`merge_roll_friction` copies **only** `carry.execution_roll_friction` into
`futures_roll`. That estimate is the sum of bid/ask half-spreads on the two
roll legs when both books are present. If bid/ask are absent, execution
friction is **unknown**: the function leaves caller-supplied `FrictionInputs`
unchanged and does **not** infer a cost from `|F_next - F_front| / |F_front|`.

That relative price gap is stored separately as `curve_gap` / `roll_gap`
(signed `(F_next - F_front) / |F_front|`). It is the curve/basis term that
drives roll yield. Treating it as friction would double-count the same
economic effect (once as carry, again as a cost).

There is **no required git dependency** on the Stage 1 branch.

## Provider fields needed later (real-data shadow testing)

No paid data vendor is used in this build. A later adapter should implement
`FuturesChainProvider.contract_observations(root, start=, end=)` and supply:

### Required

| Field | Purpose |
|---|---|
| `contract_symbol` | Identity of the listed contract (e.g. `ESH26`) |
| `root` | Product / chain key (e.g. `ES`, `CL`) |
| `expiry` | Live vs expired; roll schedule |
| `price` | Quote or settlement used at `timestamp` (document which) |
| `timestamp` | Point-in-time observation time (timezone-aware) |

### Recommended

| Field | Purpose |
|---|---|
| `volume` | Liquidity / volume-based roll rules |
| `open_interest` | Liquidity / OI-based roll rules |
| `multiplier` | Currency P&L and friction |
| `bid` / `ask` | Spread component of friction |
| `settlement_type` | Distinguish last vs settle |
| `exchange` | Calendar / session |
| `currency` | FX for friction |
| `last_trade_date` | If distinct from expiry |

Synthetic fixtures in `northstar_trend_carry.fixtures` populate the required
fields plus volume, open interest, multiplier, exchange, and currency so tests
do not depend on a vendor.

## Isolation

- Package code must not import broker/order APIs.
- `hourlyMarketAgent`, buy/sell/short rules, and sizing must not import this
  package.
- Root `requirements.txt` and `apps/web` dependencies are unchanged on purpose.
