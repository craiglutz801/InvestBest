import { loadPortfolioState, savePortfolioState } from "@/lib/paperPortfolio";
import { fetchDailyCloses, fetchUpcomingEarnings, UNIVERSE } from "@/lib/marketData";
import { getNextScheduledRun, getScheduledSlotKey, isScheduledMarketRunTime } from "@/lib/schedule";
import type {
  EarningsEvent,
  PaperPortfolioState,
  PaperTrade,
  PortfolioPosition,
  PriceBar,
  ScoredCandidate,
  SimulationRun,
  UniverseSegment,
  UniverseSymbol,
} from "@/lib/types";

type ScheduledSimulationResult = {
  state: PaperPortfolioState;
  skipped: boolean;
  reason?: string;
  run?: SimulationRun;
};

type CandidateMetrics = {
  symbol: string;
  segment: UniverseSegment;
  lastPrice: number;
  return5d: number;
  return20d: number;
  trend50d: number;
  volatility20d: number;
  rsi14: number;
  breakout20d: number;
};

type SegmentContext = {
  return5d: number;
  return20d: number;
};

const ACTIVE_MODEL = "regression_v1_manual";
const CAPITAL_DEPLOYMENT = 0.9;
const MIN_TRADE_NOTIONAL = 1500;
const ROTATION_EDGE_THRESHOLD = 0.035;
const BULLISH_MAX_HOLDINGS = 5;
const NEUTRAL_MAX_HOLDINGS = 6;
const DEFENSIVE_MAX_HOLDINGS = 4;
const TRAILING_STOP_PCT = 0.08;
const MAX_HOLD_DAYS = 12;
const BUY_EARNINGS_BUFFER_DAYS = 2;
const SELL_EARNINGS_BUFFER_DAYS = 1;

function average(values: number[]): number {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function standardDeviation(values: number[]): number {
  if (values.length < 2) {
    return 0;
  }

  const mean = average(values);
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

function startOfUtcDay(value: Date): number {
  return Date.UTC(value.getUTCFullYear(), value.getUTCMonth(), value.getUTCDate());
}

function daysBetween(fromIso: string, toIso: string): number {
  const from = new Date(fromIso);
  const to = new Date(toIso);
  return Math.max(0, Math.floor((startOfUtcDay(to) - startOfUtcDay(from)) / 86_400_000));
}

function daysUntil(reportDate: string, asOfIso: string): number | null {
  const report = new Date(reportDate);
  const asOf = new Date(asOfIso);

  if (Number.isNaN(report.getTime()) || Number.isNaN(asOf.getTime())) {
    return null;
  }

  return Math.floor((startOfUtcDay(report) - startOfUtcDay(asOf)) / 86_400_000);
}

function eventPenaltyFromDaysAway(daysAway: number | null, segment: UniverseSegment): number {
  if (daysAway == null || segment === "defensive") {
    return 0;
  }

  if (daysAway <= 0) {
    return 0.12;
  }

  if (daysAway <= 1) {
    return 0.09;
  }

  if (daysAway <= 2) {
    return 0.065;
  }

  if (daysAway <= 4) {
    return 0.03;
  }

  return 0;
}

function simpleMovingAverage(closes: number[], length: number): number {
  return average(closes.slice(-length));
}

function computeRsi(closes: number[], length = 14): number {
  const deltas = closes
    .slice(-(length + 1))
    .map((value, index, source) => {
      if (index === 0) {
        return 0;
      }

      return value - source[index - 1];
    })
    .slice(1);

  const gains = deltas.filter((delta) => delta > 0);
  const losses = deltas.filter((delta) => delta < 0).map((delta) => Math.abs(delta));
  const averageGain = gains.length > 0 ? average(gains) : 0;
  const averageLoss = losses.length > 0 ? average(losses) : 0;

  if (averageLoss === 0) {
    return 100;
  }

  const relativeStrength = averageGain / averageLoss;
  return 100 - 100 / (1 + relativeStrength);
}

function getMaxHoldings(regime: "bullish" | "neutral" | "defensive"): number {
  if (regime === "bullish") {
    return BULLISH_MAX_HOLDINGS;
  }

  if (regime === "defensive") {
    return DEFENSIVE_MAX_HOLDINGS;
  }

  return NEUTRAL_MAX_HOLDINGS;
}

function scoreSegment(segment: UniverseSegment, regime: "bullish" | "neutral" | "defensive"): number {
  if (regime === "bullish") {
    if (segment === "leadership") return 0.055;
    if (segment === "growth") return 0.04;
    if (segment === "quality") return 0.012;
    return -0.05;
  }

  if (regime === "neutral") {
    if (segment === "leadership") return 0.02;
    if (segment === "growth") return 0.01;
    if (segment === "quality") return 0.01;
    return -0.015;
  }

  if (segment === "defensive") return 0.035;
  if (segment === "quality") return 0.015;
  return -0.02;
}

function computeCandidateMetrics(symbol: UniverseSymbol, bars: PriceBar[]): CandidateMetrics {
  const closes = bars.map((bar) => bar.close);
  const lastPrice = closes.at(-1) ?? 0;
  const close5 = closes.at(-6) ?? lastPrice;
  const close20 = closes.at(-21) ?? lastPrice;
  const sma50 = simpleMovingAverage(closes, 50);
  const rolling20High = Math.max(...closes.slice(-20));
  const recentReturns = closes
    .slice(-21)
    .map((close, index, source) => {
      if (index === 0) {
        return 0;
      }

      return close / source[index - 1] - 1;
    })
    .slice(1);

  const return5d = lastPrice / close5 - 1;
  const return20d = lastPrice / close20 - 1;
  const trend50d = lastPrice / sma50 - 1;
  const volatility20d = standardDeviation(recentReturns) * Math.sqrt(252);
  const rsi14 = computeRsi(closes, 14);

  return {
    symbol: symbol.symbol,
    segment: symbol.segment,
    lastPrice,
    return5d,
    return20d,
    trend50d,
    volatility20d,
    rsi14,
    breakout20d: rolling20High === 0 ? 0 : lastPrice / rolling20High - 1,
  };
}

function scoreCandidate(
  metrics: CandidateMetrics,
  regime: "bullish" | "neutral" | "defensive",
  segmentContext: SegmentContext,
  earningsEvent: EarningsEvent | undefined,
  asOfIso: string,
): ScoredCandidate {
  const relative5d = metrics.return5d - segmentContext.return5d;
  const relative20d = metrics.return20d - segmentContext.return20d;
  const earningsDaysAway = earningsEvent ? daysUntil(earningsEvent.reportDate, asOfIso) : null;
  const eventPenalty = eventPenaltyFromDaysAway(earningsDaysAway, metrics.segment);

  let score =
    metrics.return20d * 0.28 +
    metrics.return5d * 0.24 +
    metrics.trend50d * 0.22 +
    metrics.breakout20d * 0.2 +
    relative20d * 0.28 +
    relative5d * 0.16 +
    segmentContext.return20d * 0.18 -
    metrics.volatility20d * 0.08 +
    scoreSegment(metrics.segment, regime);

  if (metrics.rsi14 > 80) {
    score -= 0.045;
  }

  if (metrics.return5d < -0.02 && metrics.rsi14 < 45) {
    score -= 0.05;
  }

  if (metrics.breakout20d > -0.02 && metrics.return5d > 0) {
    score += 0.03;
  }

  if (regime === "bullish" && (metrics.segment === "leadership" || metrics.segment === "growth")) {
    score += Math.max(0, relative20d) * 0.12;
  }

  if (regime !== "defensive" && metrics.segment === "defensive") {
    score -= 0.04;
  }

  score -= eventPenalty;

  return {
    symbol: metrics.symbol,
    segment: metrics.segment,
    lastPrice: metrics.lastPrice,
    score,
    return5d: metrics.return5d,
    return20d: metrics.return20d,
    trend50d: metrics.trend50d,
    volatility20d: metrics.volatility20d,
    rsi14: metrics.rsi14,
    breakout20d: metrics.breakout20d,
    relative5d,
    relative20d,
    segmentReturn20d: segmentContext.return20d,
    earningsDaysAway,
    eventPenalty,
  };
}

function classifyRegime(spyBars: PriceBar[]): "bullish" | "neutral" | "defensive" {
  const closes = spyBars.map((bar) => bar.close);
  const lastPrice = closes.at(-1) ?? 0;
  const sma50 = simpleMovingAverage(closes, 50);
  const sma200 = simpleMovingAverage(closes, 200);

  if (lastPrice > sma50 && lastPrice > sma200) {
    return "bullish";
  }

  if (lastPrice < sma50 && lastPrice < sma200) {
    return "defensive";
  }

  return "neutral";
}

function markToMarket(
  holdings: PortfolioPosition[],
  latestBySymbol: Map<string, ScoredCandidate>,
  asOfIso: string,
): PortfolioPosition[] {
  return holdings
    .map((position) => {
      const latest = latestBySymbol.get(position.symbol);
      if (!latest) {
        return {
          ...position,
          daysHeld: daysBetween(position.openedAt, asOfIso),
        };
      }

      const marketValue = position.shares * latest.lastPrice;
      const costBasis = position.shares * position.averageCost;
      const unrealizedPnl = marketValue - costBasis;

      return {
        ...position,
        lastPrice: latest.lastPrice,
        marketValue,
        unrealizedPnl,
        unrealizedPnlPct: costBasis === 0 ? 0 : unrealizedPnl / costBasis,
        score: latest.score,
        highWaterMark: Math.max(position.highWaterMark, latest.lastPrice),
        daysHeld: daysBetween(position.openedAt, asOfIso),
      };
    })
    .filter((position) => position.shares > 0.0001);
}

function sumMarketValue(positions: PortfolioPosition[]): number {
  return positions.reduce((sum, position) => sum + position.marketValue, 0);
}

export async function refreshPortfolioValuation(state: PaperPortfolioState): Promise<PaperPortfolioState> {
  const asOfIso = new Date().toISOString();
  const symbolsToRefresh = Array.from(new Set(["SPY", ...state.holdings.map((position) => position.symbol)]));

  if (symbolsToRefresh.length === 0) {
    return state;
  }

  const refreshedBars = await Promise.allSettled(
    symbolsToRefresh.map(async (symbol) => ({
      symbol,
      bars: await fetchDailyCloses(symbol),
    })),
  );

  const latestCloses = new Map(
    refreshedBars
      .filter(
        (result): result is PromiseFulfilledResult<{ symbol: string; bars: PriceBar[] }> => result.status === "fulfilled",
      )
      .map(({ value }) => [value.symbol, value.bars.at(-1)?.close ?? null] as const)
      .filter((entry): entry is [string, number] => entry[1] != null && Number.isFinite(entry[1])),
  );

  if (latestCloses.size === 0) {
    return state;
  }

  const refreshedHoldings = state.holdings.map((position) => {
    const latestPrice = latestCloses.get(position.symbol);
    if (latestPrice == null) {
      return {
        ...position,
        daysHeld: daysBetween(position.openedAt, asOfIso),
      };
    }

    const marketValue = position.shares * latestPrice;
    const costBasis = position.shares * position.averageCost;
    const unrealizedPnl = marketValue - costBasis;

    return {
      ...position,
      lastPrice: latestPrice,
      marketValue,
      unrealizedPnl,
      unrealizedPnlPct: costBasis === 0 ? 0 : unrealizedPnl / costBasis,
      highWaterMark: Math.max(position.highWaterMark, latestPrice),
      daysHeld: daysBetween(position.openedAt, asOfIso),
    };
  });

  return {
    ...state,
    updatedAt: asOfIso,
    equity: state.cash + sumMarketValue(refreshedHoldings),
    benchmarkCurrentPrice: latestCloses.get("SPY") ?? state.benchmarkCurrentPrice,
    holdings: refreshedHoldings,
  };
}

function createTrade(
  runId: string,
  symbol: string,
  side: "buy" | "sell",
  shares: number,
  price: number,
  reason: string,
): PaperTrade {
  const notional = shares * price;

  return {
    id: `${runId}-${side}-${symbol}-${Date.now()}`,
    runId,
    symbol,
    side,
    shares,
    price,
    notional,
    timestamp: new Date().toISOString(),
    reason,
  };
}

function buildExitDecision(
  position: PortfolioPosition,
  latest: ScoredCandidate | undefined,
  weakestSelectedScore: number,
  selectedSymbols: Set<string>,
): { exit: boolean; reason: string } {
  if (!latest) {
    return {
      exit: true,
      reason: "Missing latest market data",
    };
  }

  const trailingStopHit =
    position.highWaterMark > 0 && latest.lastPrice <= position.highWaterMark * (1 - TRAILING_STOP_PCT);
  if (trailingStopHit) {
    return {
      exit: true,
      reason: "Trailing stop exit",
    };
  }

  const eventExit =
    latest.earningsDaysAway != null &&
    latest.earningsDaysAway <= SELL_EARNINGS_BUFFER_DAYS &&
    latest.segment !== "defensive";
  if (eventExit) {
    return {
      exit: true,
      reason: "Ahead of earnings event",
    };
  }

  const timeStopHit =
    position.daysHeld >= MAX_HOLD_DAYS &&
    (position.unrealizedPnlPct < 0.02 || latest.score < weakestSelectedScore + 0.01);
  if (timeStopHit) {
    return {
      exit: true,
      reason: "Time-stop recycle",
    };
  }

  const deteriorationExit =
    latest.score < weakestSelectedScore - ROTATION_EDGE_THRESHOLD ||
    (latest.return5d < -0.035 && latest.rsi14 < 45) ||
    latest.trend50d < -0.025;
  if (deteriorationExit) {
    return {
      exit: true,
      reason: "Rotation or deterioration exit",
    };
  }

  if (!selectedSymbols.has(position.symbol)) {
    return {
      exit: true,
      reason: "Rank fell below active basket",
    };
  }

  return {
    exit: false,
    reason: "",
  };
}

async function runSimulation(source: "manual" | "scheduled"): Promise<PaperPortfolioState> {
  const state = await loadPortfolioState();
  const runId = `run_${Date.now()}`;
  const executedAt = new Date().toISOString();

  const symbolBarsSettled = await Promise.allSettled(
    UNIVERSE.map(async (item) => ({
      symbol: item,
      bars: await fetchDailyCloses(item.symbol),
    })),
  );

  const symbolBars = symbolBarsSettled
    .filter(
      (result): result is PromiseFulfilledResult<{ symbol: UniverseSymbol; bars: PriceBar[] }> =>
        result.status === "fulfilled",
    )
    .map((result) => result.value);

  const spyBars = await fetchDailyCloses("SPY");
  const earningsBySymbol = await fetchUpcomingEarnings(symbolBars.map(({ symbol }) => symbol.symbol));
  const regime = classifyRegime(spyBars);
  const metrics = symbolBars.map(({ symbol, bars }) => computeCandidateMetrics(symbol, bars));
  const segmentContexts = new Map<UniverseSegment, SegmentContext>();

  for (const segment of ["leadership", "growth", "quality", "defensive"] as UniverseSegment[]) {
    const members = metrics.filter((candidate) => candidate.segment === segment);
    segmentContexts.set(segment, {
      return5d: members.length > 0 ? average(members.map((candidate) => candidate.return5d)) : 0,
      return20d: members.length > 0 ? average(members.map((candidate) => candidate.return20d)) : 0,
    });
  }

  const scored = metrics
    .map((candidate) =>
      scoreCandidate(
        candidate,
        regime,
        segmentContexts.get(candidate.segment) ?? { return5d: 0, return20d: 0 },
        earningsBySymbol.get(candidate.symbol),
        executedAt,
      ),
    )
    .sort((left, right) => right.score - left.score);

  const maxHoldings = getMaxHoldings(regime);
  const selected = scored
    .filter((candidate) => regime !== "defensive" || candidate.segment === "defensive" || candidate.segment === "quality")
    .slice(0, maxHoldings);
  const buyableSelected = selected.filter(
    (candidate) => candidate.earningsDaysAway == null || candidate.earningsDaysAway > BUY_EARNINGS_BUFFER_DAYS,
  );

  const latestBySymbol = new Map(scored.map((candidate) => [candidate.symbol, candidate]));
  let holdings = markToMarket(state.holdings, latestBySymbol, executedAt);
  let cash = state.cash;
  const cashBefore = cash;
  const equityBefore = cash + sumMarketValue(holdings);
  const trades: PaperTrade[] = [];
  const selectedSymbols = new Set(buyableSelected.map((candidate) => candidate.symbol));
  const weakestSelectedScore = buyableSelected.at(-1)?.score ?? -Infinity;

  for (const position of holdings) {
    const decision = buildExitDecision(
      position,
      latestBySymbol.get(position.symbol),
      weakestSelectedScore,
      selectedSymbols,
    );

    if (decision.exit) {
      cash += position.marketValue;
      trades.push(
        createTrade(
          runId,
          position.symbol,
          "sell",
          position.shares,
          position.lastPrice,
          decision.reason,
        ),
      );
    }
  }

  holdings = holdings.filter((position) => {
    const decision = buildExitDecision(
      position,
      latestBySymbol.get(position.symbol),
      weakestSelectedScore,
      selectedSymbols,
    );
    return !decision.exit;
  });

  const deployedCapitalTarget = (cash + sumMarketValue(holdings)) * CAPITAL_DEPLOYMENT;
  const targetValuePerPosition = buyableSelected.length > 0 ? deployedCapitalTarget / buyableSelected.length : 0;

  for (const candidate of buyableSelected) {
    const existing = holdings.find((position) => position.symbol === candidate.symbol);
    const currentValue = existing?.marketValue ?? 0;
    const gap = targetValuePerPosition - currentValue;

    if (gap > MIN_TRADE_NOTIONAL && cash > MIN_TRADE_NOTIONAL) {
      const dollarsToSpend = Math.min(gap, cash);
      const shares = Math.floor((dollarsToSpend / candidate.lastPrice) * 1000) / 1000;
      const notional = shares * candidate.lastPrice;

      if (shares > 0 && notional >= MIN_TRADE_NOTIONAL) {
        cash -= notional;

        if (existing) {
          const totalShares = existing.shares + shares;
          const totalCost = existing.shares * existing.averageCost + notional;
          existing.shares = totalShares;
          existing.averageCost = totalCost / totalShares;
          existing.lastPrice = candidate.lastPrice;
          existing.marketValue = totalShares * candidate.lastPrice;
          existing.unrealizedPnl = existing.marketValue - totalCost;
          existing.unrealizedPnlPct = totalCost === 0 ? 0 : existing.unrealizedPnl / totalCost;
          existing.score = candidate.score;
          existing.highWaterMark = Math.max(existing.highWaterMark, candidate.lastPrice);
          existing.daysHeld = daysBetween(existing.openedAt, executedAt);
        } else {
          holdings.push({
            symbol: candidate.symbol,
            segment: candidate.segment,
            shares,
            averageCost: candidate.lastPrice,
            openedAt: executedAt,
            highWaterMark: candidate.lastPrice,
            daysHeld: 0,
            lastPrice: candidate.lastPrice,
            marketValue: notional,
            unrealizedPnl: 0,
            unrealizedPnlPct: 0,
            score: candidate.score,
          });
        }

        trades.push(createTrade(runId, candidate.symbol, "buy", shares, candidate.lastPrice, "Top-ranked candidate"));
      }
    }
  }

  holdings = markToMarket(holdings, latestBySymbol, executedAt).sort((left, right) => right.score - left.score);
  const equityAfter = cash + sumMarketValue(holdings);
  const latestSpyPrice = spyBars.at(-1)?.close ?? null;

  const run: SimulationRun = {
    id: runId,
    executedAt,
    source,
    status: "completed",
    model: ACTIVE_MODEL,
    regime,
    universeSize: scored.length,
    buys: trades.filter((trade) => trade.side === "buy").length,
    sells: trades.filter((trade) => trade.side === "sell").length,
    cashBefore,
    cashAfter: cash,
    equityBefore,
    equityAfter,
    portfolioChange: equityAfter - equityBefore,
    note:
      trades.length > 0
        ? `Selected ${buyableSelected.map((candidate) => candidate.symbol).join(", ")}`
        : selected.length !== buyableSelected.length
          ? "Top basket unchanged or blocked by near-term earnings risk."
          : "No rebalance needed; current holdings still matched the top basket.",
  };

  const nextState: PaperPortfolioState = {
    ...state,
    updatedAt: run.executedAt,
    cash,
    equity: equityAfter,
    benchmarkStartPrice: state.benchmarkStartPrice ?? latestSpyPrice,
    benchmarkCurrentPrice: latestSpyPrice,
    holdings,
    trades: [...trades, ...state.trades].slice(0, 200),
    runHistory: [run, ...state.runHistory].slice(0, 100),
    latestCandidates: scored.slice(0, 12),
    lastRegime: regime,
    automation: {
      ...state.automation,
      lastAttemptAt: run.executedAt,
      lastCompletedAt: source === "scheduled" ? run.executedAt : state.automation.lastCompletedAt,
      nextPlannedRunAt: getNextScheduledRun(new Date(run.executedAt))?.toISOString() ?? null,
    },
  };

  await savePortfolioState(nextState);
  return nextState;
}

export async function runManualSimulation(): Promise<PaperPortfolioState> {
  return runSimulation("manual");
}

function buildSkippedState(
  state: PaperPortfolioState,
  attemptedAt: string,
  nextPlannedRunAt: string | null,
): PaperPortfolioState {
  return {
    ...state,
    updatedAt: attemptedAt,
    automation: {
      ...state.automation,
      lastAttemptAt: attemptedAt,
      nextPlannedRunAt,
    },
  };
}

export async function runScheduledSimulationResult(): Promise<ScheduledSimulationResult> {
  const state = await loadPortfolioState();
  const now = new Date();
  const attemptedAt = now.toISOString();
  const nextPlannedRunAt = getNextScheduledRun(now)?.toISOString() ?? null;
  const forceRun = process.env.INVESTBEST_V2_FORCE_SCHEDULED === "1";

  if (!state.automation.enabled) {
    const nextState = buildSkippedState(state, attemptedAt, nextPlannedRunAt);
    await savePortfolioState(nextState);
    return {
      state: nextState,
      skipped: true,
      reason: "Automation disabled.",
    };
  }

  if (state.automation.marketHoursOnly && !forceRun && !isScheduledMarketRunTime(now)) {
    const nextState = buildSkippedState(state, attemptedAt, nextPlannedRunAt);
    await savePortfolioState(nextState);
    return {
      state: nextState,
      skipped: true,
      reason: "Outside allowed market-hour run window.",
    };
  }

  const currentSlotKey = getScheduledSlotKey(now);
  const lastCompletedAt = state.automation.lastCompletedAt ? new Date(state.automation.lastCompletedAt) : null;
  const lastCompletedSlotKey = lastCompletedAt ? getScheduledSlotKey(lastCompletedAt) : null;

  if (!forceRun && currentSlotKey && lastCompletedSlotKey === currentSlotKey) {
    const nextState = buildSkippedState(state, attemptedAt, nextPlannedRunAt);
    await savePortfolioState(nextState);
    return {
      state: nextState,
      skipped: true,
      reason: "Scheduled slot already completed.",
    };
  }

  const nextState = await runSimulation("scheduled");
  return {
    state: nextState,
    skipped: false,
    run: nextState.runHistory[0],
  };
}

export async function runScheduledSimulation(): Promise<PaperPortfolioState> {
  const result = await runScheduledSimulationResult();
  return result.state;
}
