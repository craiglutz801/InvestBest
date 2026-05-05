import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { grossNotional, toNum, unrealizedPnlPosition } from "@/lib/portfolio/math";
import {
  snapshotsToDrawdownSeries,
  snapshotsToEquitySeries,
  totalReturnPct,
} from "@/lib/performance/metrics";
import {
  buildPositionValueHistory,
  fetchHoldingValueLogs,
  fetchMarketSnapshotsSince,
} from "@/lib/server/positionValueHistory";
import { getLatestClosesMap } from "@/lib/server/prices";

/** Uses raw SQL so the dashboard works even when an outdated Prisma client omits `decisionSearchSnapshot`. */
async function fetchDecisionSearchSnapshotRow(decisionRunId: string) {
  try {
    const rows = await prisma.$queryRaw<{ profileName: string | null; statsJson: string | null }[]>(
      Prisma.sql`
        SELECT "profileName", "statsJson"
        FROM "DecisionSearchSnapshot"
        WHERE "decisionRunId" = ${decisionRunId}
        LIMIT 1
      `,
    );
    return rows[0] ?? null;
  } catch {
    return null;
  }
}

export async function buildDashboardPayload(userId: string) {
  const settings = await prisma.appSettings.findUnique({ where: { userId } });
  if (!settings) throw new Error("settings missing");

  const starting = toNum(settings.startingCash);

  const latestSnap = await prisma.portfolioSnapshot.findFirst({
    where: { userId },
    orderBy: { timestamp: "desc" },
  });

  const firstSnap = await prisma.portfolioSnapshot.findFirst({
    where: { userId },
    orderBy: { timestamp: "asc" },
  });

  const cash = latestSnap ? toNum(latestSnap.cash) : starting;
  const invested = latestSnap ? toNum(latestSnap.investedValue) : 0;
  const totalValue = latestSnap ? toNum(latestSnap.totalValue) : starting;
  const unrealized = latestSnap ? toNum(latestSnap.unrealizedPnl) : 0;
  const realized = latestSnap ? toNum(latestSnap.realizedPnl) : 0;
  const benchmarkVal = latestSnap?.benchmarkValue != null ? toNum(latestSnap.benchmarkValue) : null;

  const totalReturn = totalReturnPct(starting, totalValue);
  const benchmarkReturn =
    benchmarkVal != null && starting > 0 ? totalReturnPct(starting, benchmarkVal) : null;

  const snaps = await prisma.portfolioSnapshot.findMany({
    where: { userId },
    orderBy: { timestamp: "asc" },
    take: 500,
  });
  const { points: equityCurve, maxDrawdown } = snapshotsToEquitySeries(snaps);
  const drawdownCurve = snapshotsToDrawdownSeries(snaps);

  const lastRun = await prisma.decisionRun.findFirst({
    where: { userId },
    orderBy: { startedAt: "desc" },
  });

  const lastCompletedRun = await prisma.decisionRun.findFirst({
    where: { userId, status: "completed" },
    orderBy: { finishedAt: "desc" },
  });

  const lastSearchSnapshot =
    lastCompletedRun != null ? await fetchDecisionSearchSnapshotRow(lastCompletedRun.id) : null;

  const recentTrades = await prisma.paperTrade.findMany({
    where: { userId },
    orderBy: { executedAt: "desc" },
    take: 12,
    include: { symbol: true },
  });

  const buys = recentTrades.filter((t) => t.action === "BUY").slice(0, 5);
  const sells = recentTrades.filter((t) => t.action === "SELL").slice(0, 5);
  const shorts = recentTrades.filter((t) => t.action === "SHORT" || t.action === "COVER").slice(0, 5);

  const positions = await prisma.paperPosition.findMany({
    where: { userId, isOpen: true },
    include: { symbol: true },
  });
  const ids = positions.map((p) => p.symbolId);
  const pxMap = await getLatestClosesMap(ids);

  const winnersLosers = positions
    .map((p) => {
      const px = pxMap.get(p.symbolId) ?? toNum(p.avgCost);
      const qty = toNum(p.quantity);
      const avg = toNum(p.avgCost);
      const mv = grossNotional(qty, px);
      const uPnL = unrealizedPnlPosition(qty, avg, px, p.isShort);
      const uPct =
        avg > 0 ? (p.isShort ? ((avg - px) / avg) * 100 : ((px - avg) / avg) * 100) : 0;
      return {
        symbol: p.isShort ? `${p.symbol.ticker} (short)` : p.symbol.ticker,
        unrealizedPnl: uPnL,
        unrealizedPct: uPct,
        marketValue: mv,
      };
    })
    .sort((a, b) => b.unrealizedPnl - a.unrealizedPnl);

  const topWinners = winnersLosers.slice(0, 5);
  const topLosers = [...winnersLosers].sort((a, b) => a.unrealizedPnl - b.unrealizedPnl).slice(0, 5);

  const allocation = positions
    .map((p) => {
      const px = pxMap.get(p.symbolId) ?? toNum(p.avgCost);
      const qty = toNum(p.quantity);
      const notion = grossNotional(qty, px);
      return {
        name: p.isShort ? `${p.symbol.ticker} (short)` : p.symbol.ticker,
        value: notion,
      };
    })
    .filter((x) => x.value > 0);

  const minOpened =
    positions.length > 0
      ? positions.reduce((min, p) => (p.openedAt < min ? p.openedAt : min), positions[0]!.openedAt)
      : new Date();
  const [positionSnapshots, runLogs] =
    ids.length > 0
      ? await Promise.all([
          fetchMarketSnapshotsSince(ids, minOpened),
          fetchHoldingValueLogs(userId, ids, minOpened),
        ])
      : [[], []];

  const holdingsPerformance = positions
    .map((p) => {
      const px = pxMap.get(p.symbolId) ?? toNum(p.avgCost);
      const qty = toNum(p.quantity);
      const avg = toNum(p.avgCost);
      const mv = grossNotional(qty, px);
      const uPct =
        avg > 0 ? (p.isShort ? ((avg - px) / avg) * 100 : ((px - avg) / avg) * 100) : 0;
      const hist = buildPositionValueHistory(p.symbolId, p.openedAt, qty, avg, px, runLogs, positionSnapshots);
      return {
        ticker: p.symbol.ticker,
        marketValue: mv,
        unrealizedPct: uPct,
        valueHistory: hist.valueHistory,
        costBasisValue: hist.costBasisValue,
        vsLastSnapshotPct: hist.vsLastSnapshotPct,
        dayOverDayPct: hist.dayOverDayPct,
      };
    })
    .sort((a, b) => a.ticker.localeCompare(b.ticker));

  const latestDecisions =
    lastRun != null
      ? await prisma.decisionRunItem.findMany({
          where: { decisionRunId: lastRun.id },
          take: 30,
          include: { symbol: true },
          orderBy: { rank: "asc" },
        })
      : [];

  return {
    summary: {
      totalValue,
      cash,
      invested,
      unrealizedPnl: unrealized,
      realizedPnl: realized,
      totalReturnPct: totalReturn,
      benchmarkReturnPct: benchmarkReturn,
      benchmarkValue: benchmarkVal,
      openPositions: positions.length,
      startingCash: starting,
      maxDrawdownPct: maxDrawdown * 100,
      firstSnapshotAt: firstSnap?.timestamp.toISOString() ?? null,
    },
    lastRun: lastRun
      ? {
          id: lastRun.id,
          status: lastRun.status,
          startedAt: lastRun.startedAt.toISOString(),
          finishedAt: lastRun.finishedAt?.toISOString() ?? null,
          buysCount: lastRun.buysCount,
          sellsCount: lastRun.sellsCount,
          llmSummary: lastRun.llmSummary,
        }
      : null,
    equityCurve,
    drawdownCurve,
    latestBuys: buys.map((t) => ({
      id: t.id,
      at: t.executedAt.toISOString(),
      ticker: t.symbol.ticker,
      qty: toNum(t.quantity),
      price: toNum(t.price),
      confidence: t.confidenceScore != null ? toNum(t.confidenceScore) : null,
    })),
    latestSells: sells.map((t) => ({
      id: t.id,
      at: t.executedAt.toISOString(),
      ticker: t.symbol.ticker,
      qty: toNum(t.quantity),
      price: toNum(t.price),
      reason: t.reasonText,
    })),
    latestShortActivity: shorts.map((t) => ({
      id: t.id,
      at: t.executedAt.toISOString(),
      ticker: t.symbol.ticker,
      action: t.action,
      qty: toNum(t.quantity),
      price: toNum(t.price),
      reason: t.reasonText,
    })),
    topWinners,
    topLosers,
    latestDecisionItems: latestDecisions.map((d) => ({
      ticker: d.symbol.ticker,
      action: d.actionRecommendation,
      blocked: d.blocked,
      blockedReason: d.blockedReason,
      buyScore: d.buyScore != null ? toNum(d.buyScore) : null,
      sellRisk: d.sellRiskScore != null ? toNum(d.sellRiskScore) : null,
      confidence: d.confidenceScore != null ? toNum(d.confidenceScore) : null,
      note: d.rationaleShort,
    })),
    allocation,
    holdingsPerformance,
    discoverySummary:
      lastCompletedRun != null && lastSearchSnapshot != null
        ? {
            runId: lastCompletedRun.id,
            finishedAt: lastCompletedRun.finishedAt?.toISOString() ?? null,
            profileName: lastSearchSnapshot.profileName,
            stats: JSON.parse(lastSearchSnapshot.statsJson || "{}") as Record<string, unknown>,
          }
        : null,
  };
}
