import { prisma } from "@/lib/db";
import { toNum, unrealizedPnlPosition } from "@/lib/portfolio/math";
import {
  buildPositionValueHistory,
  fetchHoldingValueLogs,
  fetchMarketSnapshotsSince,
} from "@/lib/server/positionValueHistory";
import { getLatestClosesMap, getLatestModelScoresMap } from "@/lib/server/prices";

export async function buildHoldingsPayload(userId: string) {
  const positions = await prisma.paperPosition.findMany({
    where: { userId, isOpen: true },
    include: { symbol: true },
    orderBy: { openedAt: "asc" },
  });

  const ids = positions.map((p) => p.symbolId);
  const pxMap = await getLatestClosesMap(ids);
  const sinceScores = new Date(Date.now() - 48 * 3600 * 1000);
  const scores = await getLatestModelScoresMap(ids, sinceScores);

  const minOpened =
    positions.length > 0
      ? positions.reduce((min, p) => (p.openedAt < min ? p.openedAt : min), positions[0]!.openedAt)
      : new Date();
  const [snapshots, runLogs] =
    ids.length > 0
      ? await Promise.all([fetchMarketSnapshotsSince(ids, minOpened), fetchHoldingValueLogs(userId, ids, minOpened)])
      : [[], []];

  return positions.map((p) => {
    const px = pxMap.get(p.symbolId) ?? toNum(p.avgCost);
    const qty = toNum(p.quantity);
    const avg = toNum(p.avgCost);
    const mv = qty * px;
    const u = unrealizedPnlPosition(qty, avg, px, p.isShort);
    const uPct =
      avg > 0 ? (p.isShort ? ((avg - px) / avg) * 100 : ((px - avg) / avg) * 100) : 0;
    const s = scores.get(p.symbolId);
    const hist = buildPositionValueHistory(p.symbolId, p.openedAt, qty, avg, px, runLogs, snapshots);
    return {
      symbol: p.symbol.ticker,
      isShort: p.isShort,
      segmentKey: p.symbol.segmentKey,
      assetType: p.symbol.assetType,
      quantity: qty,
      avgCost: avg,
      currentPrice: px,
      marketValue: mv,
      unrealizedPnl: u,
      unrealizedPnlPct: uPct,
      buyScore: s?.buy ?? null,
      sellRiskScore: s?.sellRisk ?? null,
      confidenceScore: s?.conf ?? null,
      expectedReturn5d: s?.expectedReturn5d ?? null,
      openedAt: p.openedAt.toISOString(),
      lastQuoteAt: p.lastQuoteAt?.toISOString() ?? null,
      valuationStatus: p.valuationStatus as "ok" | "stale" | null,
      lastAgentNote: p.lastAgentNote,
      valueHistory: hist.valueHistory,
      costBasisValue: hist.costBasisValue,
      vsLastSnapshotPct: hist.vsLastSnapshotPct,
      dayOverDayPct: hist.dayOverDayPct,
    };
  });
}
