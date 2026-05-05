# InvestBest Strategy

InvestBest is a paper-trading system that tries to make money by systematically buying liquid equities and ETF-style market proxies when their recent technical profile looks favorable, then selling when risk, losses, profit targets, or momentum deterioration tell the agent to exit.

The current engine is a rules-based, long-only strategy. It does not use real money, does not place broker orders, and does not currently short stocks. The "Shorting" setting is saved in the database, but the MVP paper engine does not use it when making trades.

This document describes the strategy as implemented today.

## High-Level Idea

InvestBest is trying to capture medium-term momentum while controlling downside risk.

In plain English:

1. Build a curated universe of stocks and ETFs.
2. Pull recent daily price and volume data for each symbol.
3. Convert that data into simple technical features.
4. Score each symbol for buy attractiveness, sell risk, and confidence.
5. Sell existing holdings first if they trip an exit rule.
6. Rank remaining buy candidates by buy score.
7. Buy the highest-ranked candidates, subject to cash, position size, diversification, cooldown, liquidity, and market-regime limits.
8. Record every decision so the user can inspect why the agent bought, sold, held, or skipped a symbol.

The system is not trying to predict exact prices. It is trying to stack simple probabilistic edges: positive momentum, healthy trend structure, controlled volatility, and disciplined exits.

## What InvestBest Trades

The default universe is a curated set of large/liquid equities plus ETF or ETP proxies across several segments:

- Large/liquid equities: examples include AAPL, MSFT, NVDA, AMZN, META, GOOGL, TSLA, JPM, XOM, UNH, COST, WMT, AMD, NFLX, BRK.B, AVGO, LLY, GE, CAT, CRM.
- Defense/aerospace: examples include LMT, NOC, RTX, GD, LHX, HII, LDOS, KTOS, ITA, XAR.
- Energy: examples include XOM, CVX, COP, EOG, SLB, HAL, OXY, MPC, XLE, USO, UNG, XOP, OIH.
- Agriculture and soft commodity proxies: CORN, WEAT, SOYB, DBA, CANE, JO, NIB.
- Metals and miners: GLD, SLV, PPLT, CPER, GDX, GDXJ.
- Macro/rates/dollar/commodity proxies: UUP, TLT, IEF, SHY, DBC, TIP.

The app uses enabled universe segments when available. If segment links are not configured, it falls back to all active symbols.

## Information The Strategy Uses

For each symbol, the agent uses recent daily OHLCV data:

- Open price.
- High price.
- Low price.
- Close price.
- Volume.

From that data it computes:

- 1-day return.
- 5-day return.
- 20-day return.
- Distance from 20-day simple moving average.
- Distance from 50-day simple moving average.
- 14-day RSI.
- 20-day annualized volatility.
- Whether volume is unusually high, defined as current volume greater than 2x the 20-day average.
- Average dollar volume, used by the optional liquidity filter.

For open holdings, the agent also tries to fetch a fresh live quote before selling. If a quote is stale and the setting `staleQuoteAllowSells` is false, the agent blocks the sell and holds the position.

For market regime, the agent checks SPY and compares it to moving averages. This is used as a throttle on new buys, not as a direct sell signal.

## Current Default Settings

The seeded defaults are:

- Starting cash: $100,000.
- Max position size: 10% of portfolio value.
- Max new positions per run: 3.
- Target holdings: 12.
- Stop loss: 8%.
- Take profit: 15%.
- Minimum confidence: 40.
- Cash reserve: 10%.
- Run frequency: 60 minutes.
- Default slippage: 0.05%.
- Buy score threshold: 45.
- Sell-risk threshold: 65.
- Cooldown after sell: 24 hours.
- News enrichment: saved only; not used by current buy/sell math.
- Shorting: saved only; not implemented in the MVP paper engine.

Users can change many of these in Settings.

## Feature Scoring

Each symbol receives three main scores:

- Buy score: how attractive the symbol looks as a new long position.
- Sell-risk score: how risky an existing position looks.
- Confidence score: how reliable the signal appears, mostly based on volatility and data quality.

The current model version is `rules-v1`.

### Buy Score

Buy score starts at 50 and is adjusted by technical factors.

Positive adjustments:

- Add 15 if both 5-day and 20-day returns are positive. This favors symbols with short- and medium-term momentum.
- Add 10 if price is above both the 20-day and 50-day moving averages. This favors symbols in an established uptrend.
- Add 10 if RSI is between 35 and 70. This favors momentum that is not too weak and not too overextended.

Negative adjustments:

- Subtract 25 if RSI is 75 or higher. This penalizes overbought symbols.
- Subtract 15 if volume is more than 2x the 20-day average. This avoids chasing unusual volume spikes.
- Subtract 10 if annualized 20-day volatility is above 35%. This penalizes noisy, unstable symbols.

The final buy score is clamped between 0 and 100.

### Sell-Risk Score

Sell-risk score starts at 30 and increases when risk signals appear.

Risk adjustments:

- Add 20 if 5-day return is below -3%.
- Add 15 if RSI is above 80.
- Add 20 if price is more than 5% below the 20-day moving average.
- Add 15 if there is a volume spike on a down day.

If none of these fire, the position is recorded as having no elevated risk signals.

The final sell-risk score is clamped between 0 and 100.

### Confidence Score

Confidence starts at 40.

Positive adjustments:

- Add 20 if annualized 20-day volatility is below 25%. Lower volatility makes the technical signal less noisy.
- Add 20 if RSI is well-defined, meaning the price history is sufficient and not at an unusable extreme.

The final confidence score is clamped at 100.

## Buy Rules

A symbol is not bought just because it has a good buy score. It must pass every buy block rule.

The agent blocks a buy when:

- Cash reserve would be violated.
- Confidence score is below the minimum confidence setting.
- Buy score is below the buy score threshold.
- The symbol is already held. Pyramiding is disabled, so the agent does not add to existing positions.
- Annualized 20-day volatility is above 60%.
- Price is more than 15% above its 20-day moving average. This avoids chasing symbols extended far above trend.
- The symbol was sold recently and is still in cooldown.
- Average dollar volume is below the configured minimum dollar volume, if that optional setting is enabled.

Only symbols that pass all buy filters become buy candidates.

## Candidate Ranking

After filtering, buy candidates are sorted by buy score from highest to lowest.

The agent then walks down that ranked list and buys until one of these limits stops it:

- Max new positions per run is reached.
- Target holdings cap is reached.
- Available cash is too low.
- Cash reserve would be violated.
- Whole-share quantity would be zero.

Candidates that pass the filters but are not bought are still recorded as skipped, usually because they were ranked below the positions actually executed or because a portfolio limit stopped further buying.

## Position Sizing

The current sizing logic is conservative and cash-aware.

For each buy candidate:

- The agent computes a maximum position size from `maxPositionPct`.
- It also computes a base target as the smaller of:
  - 8% of portfolio value.
  - 33% of current cash.
- It applies an optional volatility-targeting multiplier if `volTargetAnnualized` is configured.
- It respects the minimum cash reserve.
- It buys whole shares only.
- It applies configured slippage to the execution price.

The practical effect is that InvestBest avoids putting too much money into any one symbol, avoids spending all cash at once, and can optionally size volatile symbols smaller.

## Sell Rules

Existing holdings are evaluated before new buys.

The agent sells a position when the first matching sell rule fires:

- Stop loss: current price is down at least the configured stop-loss percentage from average cost.
- Take profit: current price is up at least the configured take-profit percentage from average cost.
- Trailing stop: if the position has reached at least halfway to the take-profit target, then a meaningful give-back from the recent high can trigger a sell. The default give-back is 4% from the recent high unless overridden.
- Sell risk: sell-risk score is greater than or equal to the configured sell-risk threshold.
- Momentum break: 5-day return is below -4% and RSI is below 45.

If none of these rules fire, the agent holds the position.

## Market Regime Filter

InvestBest uses SPY as a broad market proxy.

It classifies the regime as:

- Bullish: SPY is above its 200-day moving average and the 50-day moving average is also above the 200-day moving average.
- Bearish: SPY is below its 200-day moving average and the 50-day moving average is also below the 200-day moving average.
- Neutral: anything else, including insufficient data.

The regime filter only throttles new buys. It does not force sells.

Modes:

- Off: do not adjust new buys.
- Soft: bullish or neutral allows normal buying; bearish cuts max new buys in half.
- Strict: bullish allows normal buying; neutral cuts max new buys in half; bearish blocks new buys.

If no explicit mode is configured, the code falls back to soft mode.

## Why It Makes Decisions

InvestBest buys when a symbol appears to have:

- Positive short- and medium-term momentum.
- Price strength relative to moving averages.
- RSI that is healthy but not extremely overbought.
- Manageable volatility.
- Enough confidence and liquidity.
- Room in the portfolio.
- Enough cash after preserving the reserve.

InvestBest sells when a position appears to have:

- Hit the predefined loss limit.
- Hit the predefined profit target.
- Given back too much from a recent high after making progress toward the profit target.
- Accumulated enough technical risk.
- Broken down in short-term momentum.

InvestBest holds when:

- A position has not tripped any sell rule.
- A sell would require stale quote data and stale-quote selling is disabled.
- A candidate looks interesting but does not outrank stronger candidates or cannot be bought within portfolio limits.

## What The Strategy Is Not Doing Today

The current MVP does not:

- Short stocks.
- Use options.
- Use leverage or margin.
- Use broker execution.
- Use news headlines in the scoring math.
- Use fundamental data such as revenue, earnings, valuation, debt, or analyst estimates.
- Use macroeconomic data directly in scoring.
- Use an ML model for price prediction.
- Optimize parameters through backtesting during each run.
- Rebalance to target weights across the whole portfolio.
- Add to existing positions.
- Consider tax impacts.

Some of these may exist as saved settings, future hooks, or roadmap ideas, but they are not active parts of the current paper-trading decision engine.

## Strengths Of The Current Strategy

- It is explainable. Every buy, sell, hold, and skip can be traced to concrete factors.
- It avoids highly concentrated bets through position limits and target holdings.
- It protects cash through a reserve rule.
- It avoids obvious chase conditions such as extreme RSI and large extension above the moving average.
- It exits losers through stop loss and momentum/risk rules.
- It locks in winners through take profit and trailing-stop behavior.
- It throttles buying in weak broad-market regimes.
- It is suitable for paper-trading iteration because decisions are auditable.

## Main Weaknesses And Risks

- It is mostly technical and backward-looking.
- It can underperform in sideways or choppy markets where momentum signals whipsaw.
- It may sell winners too early if take-profit settings are tight.
- It may hold weak names too long if risk scores do not cross thresholds.
- It does not currently learn from historical outcomes automatically.
- It does not compare candidate trades against factor exposure, correlation, or sector crowding.
- It does not dynamically choose different strategies for different market regimes beyond throttling new buys.
- It cannot profit directly from falling stocks because shorting is not implemented.
- It may miss opportunities outside the curated universe.

## How To Make It Better

The most valuable improvements are not simply "more aggressive settings." Better gains should come from better evidence, better risk control, and better research.

High-impact improvements:

1. Add backtesting and parameter sweeps.
   - Test buy thresholds, stop losses, take-profit levels, sell-risk thresholds, target holdings, and cooldown settings across historical periods.

2. Add walk-forward validation.
   - Tune on one period, then test on a later unseen period to reduce overfitting.

3. Add attribution.
   - Break performance down by symbol, segment, rule, trade cohort, and market regime so the user can see what is actually working.

4. Add portfolio risk controls.
   - Track concentration, sector exposure, correlation, volatility contribution, drawdown, and beta.

5. Add richer candidate data.
   - Include fundamentals, earnings trends, analyst revisions, macro context, sentiment, and news only after they can be tested.

6. Improve sell logic.
   - Evaluate whether trailing stops, profit targets, and momentum exits are helping or hurting across historical runs.

7. Add strategy variants.
   - Separate momentum, defensive, macro, and mean-reversion strategies may behave better than one generic ruleset.

8. Implement shorting only if the rest of the system supports it.
   - Real shorting requires borrow/margin modeling, separate risk limits, different P&L math, and stricter loss controls. A saved checkbox is not enough.

## Summary

InvestBest currently uses an explainable long-only momentum and risk-control strategy. It scans a curated universe, scores symbols using recent price/volume behavior, buys the strongest candidates that pass risk filters, sells holdings that trip exit rules, and records the reasoning behind each decision.

Its edge, if any, comes from disciplined participation in upward trends while limiting losses, avoiding overextended entries, preserving cash, and reducing new exposure in weaker markets.

To get meaningfully better, the next step is not just "trade more." The next step is to measure which rules actually improve returns, tune them with backtesting, validate them out of sample, and add portfolio-level risk intelligence.
