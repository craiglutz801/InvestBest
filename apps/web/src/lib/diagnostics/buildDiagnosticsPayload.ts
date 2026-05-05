import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { snapshotsToDrawdownSeries, snapshotsToEquitySeries } from "@/lib/performance/metrics";
import { regimeLabelFromRunNotes } from "@/lib/diagnostics/regimeFromRun";
import {
  dailyReturnsFromTotalValues,
  dailyTotalValuesFromSnapshots,
  maxDrawdownFromValues,
  sharpeAnnualized,
  sortinoAnnualized,
} from "@/lib/diagnostics/riskRatios";
import type {
  ClosedTradeSummary,
  DiagnosticsBucketRow,
  DiagnosticsPayload,
} from "@/lib/diagnostics/types";
import { buildDiagnosticsWarnings } from "@/lib/diagnostics/warnings";
import { DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS } from "@/lib/diagnostics/constants";

type Lot = {
  qty: number;
  unitCost: number;
  buyAt: Date;
  buyScore: number | null;
  vol20: number | null;
};

type InternalClosed = {
  sellTradeId: string;
  sellAt: Date;
  ticker: string;
  symbolId: string;
  segmentKey: string | null;
  realizedPnl: number;
  qty: number;
  holdingDays: number;
  exitReason: string | null;
  entryScoreBucket: string;
  volatilityBucket: string;
  regimeAtSellRun: string;
  triggerSource: string;
  strategyFamily: string | null;
  dow: string;
};

function entryScoreBucket(score: number | null): string {
  if (score == null) return "unknown";
  if (score < 45) return "<45";
  if (score < 55) return "45–55";
  if (score < 65) return "55–65";
  return "≥65";
}

function volBucket(vol: number | null): string {
  if (vol == null) return "unknown";
  if (vol < 0.15) return "low (<15% ann.)";
  if (vol < 0.3) return "medium (15–30%)";
  return "high (>30%)";
}

function holdingBucket(days: number): string {
  if (days < 2) return "<2d";
  if (days <= 7) return "2–7d";
  if (days <= 30) return "8–30d";
  return ">30d";
}

const DOW = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

const EXIT_REASON_LABELS: Record<string, string> = {
  stop_loss: "Stop loss",
  take_profit: "Take profit",
  trailing_stop: "Trailing stop",
  sell_risk: "Sell-risk score",
  momentum_break: "Momentum break",
  confidence_collapse: "Confidence collapse",
  rebalance: "Rebalance",
  unknown: "Unknown",
};

type Agg = { label: string; pnl: number; wins: number; count: number };

function bump(map: Map<string, Agg>, key: string, label: string, pnl: number, win: boolean) {
  const cur = map.get(key) ?? { label, pnl: 0, wins: 0, count: 0 };
  cur.pnl += pnl;
  cur.count += 1;
  if (win) cur.wins += 1;
  map.set(key, cur);
}

function rowsFromMap(map: Map<string, Agg>): DiagnosticsBucketRow[] {
  return [...map.entries()]
    .map(([key, v]) => ({
      key,
      label: v.label,
      trades: v.count,
      realizedPnl: Math.round(v.pnl * 100) / 100,
      winRatePct: v.count > 0 ? Math.round((1000 * v.wins) / v.count) / 10 : null,
      avgPnl: v.count > 0 ? Math.round((100 * v.pnl) / v.count) / 100 : 0,
    }))
    .sort((a, b) => b.realizedPnl - a.realizedPnl);
}

function closedToSummary(c: InternalClosed): ClosedTradeSummary {
  return {
    id: c.sellTradeId,
    executedAt: c.sellAt.toISOString(),
    ticker: c.ticker,
    segmentKey: c.segmentKey,
    qty: Math.round(c.qty * 10000) / 10000,
    realizedPnl: Math.round(c.realizedPnl * 100) / 100,
    holdingDays: Math.round(c.holdingDays * 10) / 10,
    exitReason: c.exitReason,
    entryScoreBucket: c.entryScoreBucket,
    regimeAtSellRun: c.regimeAtSellRun,
    triggerSource: c.triggerSource,
    volatilityBucket: c.volatilityBucket,
  };
}

/** Keeps endpoints stable while capping chart payload size. */
function downsampleSeries<T>(items: T[], maxPoints: number): T[] {
  if (items.length <= maxPoints) return items;
  const out: T[] = [];
  const step = (items.length - 1) / (maxPoints - 1);
  for (let i = 0; i < maxPoints; i++) {
    const idx = Math.min(items.length - 1, Math.round(i * step));
    out.push(items[idx]!);
  }
  return out;
}

const EMPTY_DIAGNOSTICS_TABLES: DiagnosticsPayload["tables"] = {
  bySymbol: [],
  bySegment: [],
  byExitReason: [],
  byEntryScoreBucket: [],
  byRegime: [],
  byHoldingPeriod: [],
  byTriggerSource: [],
  byVolatilityRegime: [],
  byStrategyFamily: [],
  byExitDayOfWeek: [],
};

/** Safe fallback when `buildDiagnosticsPayload` throws so the dashboard can still render. */
export function diagnosticsPayloadFailed(detail: string): DiagnosticsPayload {
  const now = new Date().toISOString();
  return {
    generatedAt: now,
    windowStart: now,
    windowEnd: now,
    windowDays: DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS,
    snapshotId: null,
    charts: null,
    metrics: {
      totalReturnPct: null,
      benchmarkReturnPct: null,
      excessReturnPct: null,
      maxDrawdownPct: null,
      sharpeAnnualized: null,
      sortinoAnnualized: null,
      winRatePct: null,
      avgWin: null,
      avgLoss: null,
      profitFactor: null,
      expectancyPerTrade: null,
      avgHoldingDays: null,
      turnoverApproxPct: null,
      exposurePctLatest: null,
      cashPctLatest: null,
      closedTradeCount: 0,
      openNote: null,
    },
    tables: EMPTY_DIAGNOSTICS_TABLES,
    trades: { best: [], worst: [] },
    warnings: [
      {
        severity: "critical",
        code: "diagnostics_build_failed",
        title: "Diagnostics failed to load",
        detail: detail.slice(0, 2000),
      },
    ],
  };
}

export async function buildDiagnosticsPayload(
  userId: string,
  opts?: { windowDays?: number | null },
): Promise<DiagnosticsPayload> {
  const windowDays = opts?.windowDays === undefined ? 365 : opts.windowDays;
  const windowEnd = new Date();
  const winStart =
    windowDays === null ? new Date(0) : new Date(windowEnd.getTime() - windowDays * 86400000);

  const [snaps, trades, latestSnap, scheduleRow] = await Promise.all([
    prisma.portfolioSnapshot.findMany({
      where: { userId, timestamp: { gte: winStart, lte: windowEnd } },
      orderBy: { timestamp: "asc" },
      take: 5000,
    }),
    prisma.paperTrade.findMany({
      where: { userId, executedAt: { gte: winStart, lte: windowEnd } },
      orderBy: { executedAt: "asc" },
      include: { symbol: true },
    }),
    prisma.portfolioSnapshot.findFirst({
      where: { userId },
      orderBy: { timestamp: "desc" },
    }),
    prisma.agentScheduleSettings.findUnique({ where: { userId } }),
  ]);

  const runIds = [...new Set(trades.map((t) => t.decisionRunId).filter(Boolean))] as string[];
  const runs =
    runIds.length > 0
      ? await prisma.decisionRun.findMany({
          where: { id: { in: runIds } },
          select: { id: true, triggerSource: true, dryRun: true, notesJson: true },
        })
      : [];

  const runMap = new Map(runs.map((r) => [r.id, r]));
  const dryRunIds = new Set(runs.filter((r) => r.dryRun).map((r) => r.id));

  const buyTrades = trades.filter((t) => t.action === "BUY" && t.decisionRunId && !dryRunIds.has(t.decisionRunId));
  const orClause = buyTrades.map((t) => ({
    decisionRunId: t.decisionRunId as string,
    symbolId: t.symbolId,
  }));
  const candidates =
    orClause.length > 0
      ? await prisma.decisionRunCandidate.findMany({
          where: { OR: orClause },
          select: {
            decisionRunId: true,
            symbolId: true,
            buyScore: true,
            volatility20d: true,
          },
        })
      : [];

  const candMap = new Map<string, (typeof candidates)[number]>(
    candidates.map((c) => [`${c.decisionRunId}:${c.symbolId}`, c]),
  );

  const lots = new Map<string, Lot[]>();
  const closed: InternalClosed[] = [];

  for (const t of trades) {
    if (t.decisionRunId && dryRunIds.has(t.decisionRunId)) continue;

    const sym = t.symbolId;
    const ticker = t.symbol.ticker;
    const segmentKey = t.symbol.segmentKey ?? null;

    if (t.action === "BUY") {
      const ck = t.decisionRunId ? `${t.decisionRunId}:${sym}` : "";
      const cand = ck ? candMap.get(ck) : undefined;
      const arr = lots.get(sym) ?? [];
      arr.push({
        qty: toNum(t.quantity),
        unitCost: toNum(t.price),
        buyAt: t.executedAt,
        buyScore: cand?.buyScore != null ? toNum(cand.buyScore) : null,
        vol20: cand?.volatility20d != null ? toNum(cand.volatility20d) : null,
      });
      lots.set(sym, arr);
      continue;
    }

    if (t.action !== "SELL") continue;

    let sellQty = toNum(t.quantity);
    const sellPrice = toNum(t.price);
    const sellFees = toNum(t.fees);
    const gross = toNum(t.grossAmount);
    const arr = lots.get(sym) ?? [];

    let weightedHoldHours = 0;
    let totalMatchedQty = 0;
    let totalCost = 0;
    let firstBuyScore: number | null = null;
    let firstVol: number | null = null;

    while (sellQty > 1e-12 && arr.length > 0) {
      const lot = arr[0]!;
      const take = Math.min(sellQty, lot.qty);
      const costChunk = take * lot.unitCost;
      totalCost += costChunk;
      totalMatchedQty += take;
      weightedHoldHours += take * ((t.executedAt.getTime() - lot.buyAt.getTime()) / 3600000);
      if (firstBuyScore == null && lot.buyScore != null) firstBuyScore = lot.buyScore;
      if (firstVol == null && lot.vol20 != null) firstVol = lot.vol20;
      sellQty -= take;
      lot.qty -= take;
      if (lot.qty <= 1e-12) arr.shift();
    }
    lots.set(sym, arr);

    if (totalMatchedQty <= 1e-12) continue;

    const proceeds = totalMatchedQty * sellPrice;
    const feeShare = gross > 1e-9 ? sellFees * (proceeds / gross) : sellFees;
    const realizedPnl = proceeds - totalCost - feeShare;
    const holdingDays = weightedHoldHours / totalMatchedQty / 24;

    const runMeta = t.decisionRunId ? runMap.get(t.decisionRunId) : undefined;
    const regime =
      runMeta?.notesJson != null ? regimeLabelFromRunNotes(runMeta.notesJson) : "unknown";
    const triggerSource =
      runMeta?.triggerSource === "manual"
        ? "manual"
        : runMeta?.triggerSource === "scheduled"
          ? "scheduled"
          : runMeta?.triggerSource ?? "legacy";

    closed.push({
      sellTradeId: t.id,
      sellAt: t.executedAt,
      ticker,
      symbolId: sym,
      segmentKey,
      realizedPnl,
      qty: totalMatchedQty,
      holdingDays,
      exitReason: t.reasonCode ?? null,
      entryScoreBucket: entryScoreBucket(firstBuyScore),
      volatilityBucket: volBucket(firstVol),
      regimeAtSellRun: regime === "unknown" ? "unknown" : regime,
      triggerSource,
      strategyFamily: t.modelVersion ?? null,
      dow: DOW[t.executedAt.getUTCDay()] ?? "?",
    });
  }

  /* ----- Portfolio metrics from snapshots ----- */
  const snapVals = snaps.map((s) => toNum(s.totalValue));
  const benchVals = snaps.map((s) => (s.benchmarkValue != null ? toNum(s.benchmarkValue) : null));

  let totalReturnPct: number | null = null;
  let benchmarkReturnPct: number | null = null;
  let excessReturnPct: number | null = null;
  if (snapVals.length >= 2) {
    const a = snapVals[0]!;
    const b = snapVals[snapVals.length - 1]!;
    if (a > 1e-9) totalReturnPct = ((b - a) / a) * 100;
    const ba = benchVals[0];
    const bb = benchVals[benchVals.length - 1];
    if (ba != null && bb != null && ba > 1e-9) {
      benchmarkReturnPct = ((bb - ba) / ba) * 100;
      if (totalReturnPct != null) excessReturnPct = totalReturnPct - benchmarkReturnPct;
    }
  }

  const maxDrawdownPct =
    snapVals.length >= 2 ? maxDrawdownFromValues(snapVals) * 100 : null;

  const { points: equityCurveRaw } = snapshotsToEquitySeries(snaps);
  const drawdownCurveRaw = snapshotsToDrawdownSeries(snaps);
  const charts: DiagnosticsPayload["charts"] =
    equityCurveRaw.length === 0
      ? null
      : {
          equity: downsampleSeries(equityCurveRaw, 400),
          drawdown: downsampleSeries(drawdownCurveRaw, 400),
        };

  const dailySeries = dailyTotalValuesFromSnapshots(
    snaps.map((s) => ({ timestamp: s.timestamp, totalValue: toNum(s.totalValue) })),
  );
  const rets = dailyReturnsFromTotalValues(dailySeries);
  const sharpe = sharpeAnnualized(rets);
  const sortino = sortinoAnnualized(rets);

  /* ----- Trade statistics ----- */
  const pnls = closed.map((c) => c.realizedPnl);
  const wins = pnls.filter((p) => p > 0);
  const losses = pnls.filter((p) => p < 0);
  const winRatePct =
    pnls.length > 0 ? (100 * wins.length) / pnls.length : null;
  const avgWin = wins.length > 0 ? wins.reduce((s, x) => s + x, 0) / wins.length : null;
  const avgLoss = losses.length > 0 ? losses.reduce((s, x) => s + x, 0) / losses.length : null;
  const sumWin = wins.reduce((s, x) => s + x, 0);
  const sumLossAbs = losses.reduce((s, x) => s + -x, 0);
  const profitFactor = sumLossAbs > 1e-9 ? sumWin / sumLossAbs : null;
  const expectancyPerTrade = pnls.length > 0 ? pnls.reduce((s, x) => s + x, 0) / pnls.length : null;
  const avgHoldingDays =
    closed.length > 0 ? closed.reduce((s, c) => s + c.holdingDays, 0) / closed.length : null;

  let turnoverApproxPct: number | null = null;
  const avgNav =
    snapVals.length > 0 ? snapVals.reduce((s, v) => s + v, 0) / snapVals.length : null;
  if (avgNav != null && avgNav > 1e-9) {
    const turnoverSum = trades.reduce((s, t) => s + Math.abs(toNum(t.grossAmount)), 0);
    turnoverApproxPct = (turnoverSum / avgNav) * 100;
  }

  let exposurePctLatest: number | null = null;
  let cashPctLatest: number | null = null;
  if (latestSnap) {
    const tv = toNum(latestSnap.totalValue);
    if (tv > 1e-9) {
      exposurePctLatest = (toNum(latestSnap.investedValue) / tv) * 100;
      cashPctLatest = (toNum(latestSnap.cash) / tv) * 100;
    }
  }

  /* ----- Aggregation maps ----- */
  const bySymbol = new Map<string, Agg>();
  const bySegment = new Map<string, Agg>();
  const byExit = new Map<string, Agg>();
  const byEntry = new Map<string, Agg>();
  const byRegime = new Map<string, Agg>();
  const byHold = new Map<string, Agg>();
  const byTrigger = new Map<string, Agg>();
  const byVol = new Map<string, Agg>();
  const byFamily = new Map<string, Agg>();
  const byDow = new Map<string, Agg>();

  let manualWins = 0;
  let manualN = 0;
  let schedWins = 0;
  let schedN = 0;

  for (const c of closed) {
    const win = c.realizedPnl > 0;
    bump(bySymbol, c.ticker, c.ticker, c.realizedPnl, win);
    const seg = c.segmentKey ?? "unclassified";
    bump(bySegment, seg, c.segmentKey ?? "Unclassified", c.realizedPnl, win);
    const ex = c.exitReason ?? "unknown";
    const exLabel = EXIT_REASON_LABELS[ex] ?? ex;
    bump(byExit, ex, exLabel, c.realizedPnl, win);
    bump(byEntry, c.entryScoreBucket, c.entryScoreBucket, c.realizedPnl, win);
    bump(byRegime, c.regimeAtSellRun, c.regimeAtSellRun, c.realizedPnl, win);
    const hb = holdingBucket(c.holdingDays);
    bump(byHold, hb, hb, c.realizedPnl, win);
    bump(byTrigger, c.triggerSource, c.triggerSource, c.realizedPnl, win);
    bump(byVol, c.volatilityBucket, c.volatilityBucket, c.realizedPnl, win);
    const fam = c.strategyFamily ?? "unknown";
    bump(byFamily, fam, fam, c.realizedPnl, win);
    bump(byDow, c.dow, c.dow, c.realizedPnl, win);

    if (c.triggerSource === "manual") {
      manualN++;
      if (win) manualWins++;
    }
    if (c.triggerSource === "scheduled") {
      schedN++;
      if (win) schedWins++;
    }
  }

  const warnings = buildDiagnosticsWarnings({
    closedTradeCount: closed.length,
    scheduleFrequencyMinutes: scheduleRow?.frequencyMinutes ?? null,
    metrics: {
      totalReturnPct,
      sharpeAnnualized: sharpe,
      winRatePct,
    },
    segmentRows: rowsFromMap(bySegment),
    exitReasonRows: rowsFromMap(byExit),
    manualVsScheduled: {
      manualWinRate: manualN >= 2 ? (manualWins / manualN) * 100 : null,
      scheduledWinRate: schedN >= 2 ? (schedWins / schedN) * 100 : null,
      manualN,
      scheduledN: schedN,
    },
  });

  const sortedClosed = [...closed].sort((a, b) => b.realizedPnl - a.realizedPnl);
  const best = sortedClosed.slice(0, 10).map(closedToSummary);
  const worst = [...sortedClosed].sort((a, b) => a.realizedPnl - b.realizedPnl).slice(0, 10).map(closedToSummary);

  return {
    generatedAt: new Date().toISOString(),
    windowStart: winStart.toISOString(),
    windowEnd: windowEnd.toISOString(),
    windowDays,
    snapshotId: null,
    charts,
    metrics: {
      totalReturnPct: totalReturnPct != null ? Math.round(totalReturnPct * 100) / 100 : null,
      benchmarkReturnPct:
        benchmarkReturnPct != null ? Math.round(benchmarkReturnPct * 100) / 100 : null,
      excessReturnPct: excessReturnPct != null ? Math.round(excessReturnPct * 100) / 100 : null,
      maxDrawdownPct: maxDrawdownPct != null ? Math.round(maxDrawdownPct * 100) / 100 : null,
      sharpeAnnualized: sharpe != null ? Math.round(sharpe * 100) / 100 : null,
      sortinoAnnualized: sortino != null ? Math.round(sortino * 100) / 100 : null,
      winRatePct: winRatePct != null ? Math.round(winRatePct * 10) / 10 : null,
      avgWin: avgWin != null ? Math.round(avgWin * 100) / 100 : null,
      avgLoss: avgLoss != null ? Math.round(avgLoss * 100) / 100 : null,
      profitFactor: profitFactor != null ? Math.round(profitFactor * 100) / 100 : null,
      expectancyPerTrade:
        expectancyPerTrade != null ? Math.round(expectancyPerTrade * 100) / 100 : null,
      avgHoldingDays: avgHoldingDays != null ? Math.round(avgHoldingDays * 10) / 10 : null,
      turnoverApproxPct:
        turnoverApproxPct != null ? Math.round(turnoverApproxPct * 100) / 100 : null,
      exposurePctLatest:
        exposurePctLatest != null ? Math.round(exposurePctLatest * 100) / 100 : null,
      cashPctLatest: cashPctLatest != null ? Math.round(cashPctLatest * 100) / 100 : null,
      closedTradeCount: closed.length,
      openNote:
        "Closed-trade stats use FIFO matching from paper ledger rows. Unrealized open positions are excluded.",
    },
    tables: {
      bySymbol: rowsFromMap(bySymbol),
      bySegment: rowsFromMap(bySegment),
      byExitReason: rowsFromMap(byExit),
      byEntryScoreBucket: rowsFromMap(byEntry),
      byRegime: rowsFromMap(byRegime),
      byHoldingPeriod: rowsFromMap(byHold),
      byTriggerSource: rowsFromMap(byTrigger),
      byVolatilityRegime: rowsFromMap(byVol),
      byStrategyFamily: rowsFromMap(byFamily),
      byExitDayOfWeek: rowsFromMap(byDow),
    },
    trades: { best, worst },
    warnings,
  };
}

export function diagnosticsPayloadToSnapshotParts(userId: string, p: DiagnosticsPayload) {
  return {
    userId,
    windowStart: new Date(p.windowStart),
    windowEnd: new Date(p.windowEnd),
    metricsJson: JSON.stringify(p.metrics),
    bySymbolJson: JSON.stringify(p.tables.bySymbol),
    bySegmentJson: JSON.stringify(p.tables.bySegment),
    byExitReasonJson: JSON.stringify(p.tables.byExitReason),
    byEntryScoreBucketJson: JSON.stringify(p.tables.byEntryScoreBucket),
    byRegimeJson: JSON.stringify(p.tables.byRegime),
    byHoldingPeriodJson: JSON.stringify(p.tables.byHoldingPeriod),
    byTriggerSourceJson: JSON.stringify(p.tables.byTriggerSource),
    byVolatilityRegimeJson: JSON.stringify(p.tables.byVolatilityRegime),
    byStrategyFamilyJson: JSON.stringify(p.tables.byStrategyFamily),
    byExitDayOfWeekJson: JSON.stringify(p.tables.byExitDayOfWeek),
    closedTradesJson: JSON.stringify(p.trades),
    warningsJson: JSON.stringify(p.warnings),
    chartsJson: p.charts ? JSON.stringify(p.charts) : null,
  };
}

export function diagnosticsPayloadFromSnapshotRow(row: {
  id: string;
  generatedAt: Date;
  windowStart: Date;
  windowEnd: Date;
  metricsJson: string;
  bySymbolJson: string;
  bySegmentJson: string;
  byExitReasonJson: string;
  byEntryScoreBucketJson: string;
  byRegimeJson: string;
  byHoldingPeriodJson: string;
  byTriggerSourceJson: string;
  byVolatilityRegimeJson: string;
  byStrategyFamilyJson: string;
  byExitDayOfWeekJson: string;
  closedTradesJson: string;
  warningsJson: string;
  chartsJson?: string | null;
}): DiagnosticsPayload {
  const metrics = JSON.parse(row.metricsJson) as DiagnosticsPayload["metrics"];
  const warnings = JSON.parse(row.warningsJson) as DiagnosticsPayload["warnings"];
  const best = (JSON.parse(row.closedTradesJson) as { best: ClosedTradeSummary[] }).best;
  const worst = (JSON.parse(row.closedTradesJson) as { worst: ClosedTradeSummary[] }).worst;
  let charts: DiagnosticsPayload["charts"] = null;
  if (row.chartsJson) {
    try {
      charts = JSON.parse(row.chartsJson) as DiagnosticsPayload["charts"];
    } catch {
      charts = null;
    }
  }
  return {
    generatedAt: row.generatedAt.toISOString(),
    windowStart: row.windowStart.toISOString(),
    windowEnd: row.windowEnd.toISOString(),
    windowDays: null,
    snapshotId: row.id,
    charts,
    metrics,
    tables: {
      bySymbol: JSON.parse(row.bySymbolJson) as DiagnosticsBucketRow[],
      bySegment: JSON.parse(row.bySegmentJson) as DiagnosticsBucketRow[],
      byExitReason: JSON.parse(row.byExitReasonJson) as DiagnosticsBucketRow[],
      byEntryScoreBucket: JSON.parse(row.byEntryScoreBucketJson) as DiagnosticsBucketRow[],
      byRegime: JSON.parse(row.byRegimeJson) as DiagnosticsBucketRow[],
      byHoldingPeriod: JSON.parse(row.byHoldingPeriodJson) as DiagnosticsBucketRow[],
      byTriggerSource: JSON.parse(row.byTriggerSourceJson) as DiagnosticsBucketRow[],
      byVolatilityRegime: JSON.parse(row.byVolatilityRegimeJson) as DiagnosticsBucketRow[],
      byStrategyFamily: JSON.parse(row.byStrategyFamilyJson) as DiagnosticsBucketRow[],
      byExitDayOfWeek: JSON.parse(row.byExitDayOfWeekJson) as DiagnosticsBucketRow[],
    },
    trades: { best, worst },
    warnings,
  };
}
