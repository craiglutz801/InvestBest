/**
 * Strategy Diagnostics (Sprint 2 — spec §18).
 * Serializable shapes shared by API routes and snapshot persistence.
 */

export type DiagnosticsBucketRow = {
  key: string;
  label: string;
  trades: number;
  realizedPnl: number;
  winRatePct: number | null;
  avgPnl: number;
};

export type ClosedTradeSummary = {
  id: string;
  executedAt: string;
  ticker: string;
  segmentKey: string | null;
  qty: number;
  realizedPnl: number;
  holdingDays: number;
  exitReason: string | null;
  entryScoreBucket: string;
  regimeAtSellRun: string;
  triggerSource: string;
  volatilityBucket: string;
};

export type DiagnosticsMetricCard = {
  key: string;
  label: string;
  value: string;
  hint?: string | null;
};

export type DiagnosticWarning = {
  severity: "info" | "warning" | "critical";
  code: string;
  title: string;
  detail: string;
};

/** Matches `ChartPoint` / snapshot equity curve — kept local to avoid client/server coupling. */
export type DiagnosticsEquityPoint = { t: string; value: number; benchmark?: number | null };

/** Matches `DrawdownChartPoint`. */
export type DiagnosticsDrawdownPoint = { t: string; ddPct: number };

export type DiagnosticsPayload = {
  generatedAt: string;
  windowStart: string;
  windowEnd: string;
  windowDays: number | null;
  snapshotId?: string | null;
  /**
   * Portfolio value vs SPY benchmark and running drawdown within the same window as metrics.
   * Null when there are no snapshots in-range.
   */
  charts: {
    equity: DiagnosticsEquityPoint[];
    drawdown: DiagnosticsDrawdownPoint[];
  } | null;
  metrics: {
    totalReturnPct: number | null;
    benchmarkReturnPct: number | null;
    excessReturnPct: number | null;
    maxDrawdownPct: number | null;
    sharpeAnnualized: number | null;
    sortinoAnnualized: number | null;
    winRatePct: number | null;
    avgWin: number | null;
    avgLoss: number | null;
    profitFactor: number | null;
    expectancyPerTrade: number | null;
    avgHoldingDays: number | null;
    turnoverApproxPct: number | null;
    exposurePctLatest: number | null;
    cashPctLatest: number | null;
    closedTradeCount: number;
    openNote: string | null;
  };
  tables: {
    bySymbol: DiagnosticsBucketRow[];
    bySegment: DiagnosticsBucketRow[];
    byExitReason: DiagnosticsBucketRow[];
    byEntryScoreBucket: DiagnosticsBucketRow[];
    byRegime: DiagnosticsBucketRow[];
    byHoldingPeriod: DiagnosticsBucketRow[];
    byTriggerSource: DiagnosticsBucketRow[];
    byVolatilityRegime: DiagnosticsBucketRow[];
    byStrategyFamily: DiagnosticsBucketRow[];
    byExitDayOfWeek: DiagnosticsBucketRow[];
  };
  trades: {
    best: ClosedTradeSummary[];
    worst: ClosedTradeSummary[];
  };
  warnings: DiagnosticWarning[];
};
