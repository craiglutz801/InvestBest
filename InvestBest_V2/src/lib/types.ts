export type ModelStage =
  | "candidate"
  | "backtesting"
  | "incubating"
  | "active"
  | "decayed"
  | "rejected";

export type ModelFamily = "rules" | "alpha" | "regression" | "factor";

export type StrategyModel = {
  id: string;
  name: string;
  family: ModelFamily;
  stage: ModelStage;
  oosSharpe: number;
  meanIc: number;
  alphaTstat: number;
  maxDrawdownPct: number;
  profitFactor: number;
  notes: string;
};

export type Experiment = {
  id: string;
  title: string;
  hypothesis: string;
  status: "queued" | "running" | "approved" | "rejected";
  holdoutSharpe: number;
  walkForwardPasses: string;
  icSummary: string;
  bonferroniBar: string;
};

export type CandidateIdea = {
  id: string;
  symbol: string;
  family: string;
  stage: "found" | "compiled" | "tested" | "approved" | "rejected";
  thesis: string;
  verdict: string;
};

export type SystemAlert = {
  id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
  timestamp: string;
};

export type SummaryMetric = {
  label: string;
  value: string;
  change?: string;
  tone?: "positive" | "neutral" | "negative";
};

export type UniverseSegment = "leadership" | "growth" | "quality" | "defensive";

export type UniverseSymbol = {
  symbol: string;
  segment: UniverseSegment;
};

export type PriceBar = {
  date: string;
  close: number;
};

export type EarningsEvent = {
  symbol: string;
  reportDate: string;
};

export type ScoredCandidate = {
  symbol: string;
  segment: UniverseSegment;
  lastPrice: number;
  score: number;
  return5d: number;
  return20d: number;
  trend50d: number;
  volatility20d: number;
  rsi14: number;
  breakout20d: number;
  relative5d: number;
  relative20d: number;
  segmentReturn20d: number;
  earningsDaysAway: number | null;
  eventPenalty: number;
};

export type PortfolioPosition = {
  symbol: string;
  segment: UniverseSegment;
  shares: number;
  averageCost: number;
  openedAt: string;
  highWaterMark: number;
  daysHeld: number;
  lastPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  score: number;
};

export type PaperTrade = {
  id: string;
  runId: string;
  symbol: string;
  side: "buy" | "sell";
  shares: number;
  price: number;
  notional: number;
  timestamp: string;
  reason: string;
};

export type SimulationRun = {
  id: string;
  executedAt: string;
  source: "manual" | "scheduled";
  status: "completed" | "failed";
  model: string;
  regime: "bullish" | "neutral" | "defensive";
  universeSize: number;
  buys: number;
  sells: number;
  cashBefore: number;
  cashAfter: number;
  equityBefore: number;
  equityAfter: number;
  portfolioChange: number;
  note: string;
};

export type PaperPortfolioState = {
  updatedAt: string;
  startingCash: number;
  cash: number;
  equity: number;
  benchmarkSymbol: string;
  benchmarkStartPrice: number | null;
  benchmarkCurrentPrice: number | null;
  holdings: PortfolioPosition[];
  trades: PaperTrade[];
  runHistory: SimulationRun[];
  latestCandidates: ScoredCandidate[];
  lastRegime: "bullish" | "neutral" | "defensive";
  automation: {
    enabled: boolean;
    cadence: "hourly";
    marketHoursOnly: boolean;
    marketDaysOnly: boolean;
    lastAttemptAt: string | null;
    lastCompletedAt: string | null;
    nextPlannedRunAt: string | null;
    launchAgentLabel: string;
  };
};

export type DashboardSnapshot = {
  portfolio: PaperPortfolioState;
  totalReturnPct: number;
  benchmarkReturnPct: number | null;
  activeModel: string;
};
