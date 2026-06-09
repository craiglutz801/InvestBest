import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import {
  type RegressionFeatureVector,
  type RegressionTrainingRow,
  computeForwardTargets,
} from "@/lib/research/regressionV1";

type FeatureSnapshotWithSymbol = Awaited<ReturnType<typeof loadFeatureSnapshots>>[number];
type MarketSnapshotRow = Awaited<ReturnType<typeof loadMarketSnapshots>>[number];

function parseFeatureVector(featuresJson: string): RegressionFeatureVector | null {
  try {
    const raw = JSON.parse(featuresJson) as Partial<RegressionFeatureVector>;
    const candidate: RegressionFeatureVector = {
      ret1d: Number(raw.ret1d ?? 0),
      ret5d: Number(raw.ret5d ?? 0),
      ret20d: Number(raw.ret20d ?? 0),
      distSma20: Number(raw.distSma20 ?? 0),
      distSma50: Number(raw.distSma50 ?? 0),
      rsi14: Number(raw.rsi14 ?? 50),
      vol20: Number(raw.vol20 ?? 0),
      volSpike: Boolean(raw.volSpike),
    };
    if (Object.values(candidate).some((v) => typeof v === "number" && !Number.isFinite(v))) {
      return null;
    }
    return candidate;
  } catch {
    return null;
  }
}

async function loadFeatureSnapshots(since: Date | null) {
  return prisma.featureSnapshot.findMany({
    where: since ? { timestamp: { gte: since } } : undefined,
    include: {
      symbol: {
        select: {
          id: true,
          ticker: true,
          segmentKey: true,
        },
      },
    },
    orderBy: [{ symbolId: "asc" }, { timestamp: "asc" }],
    take: 50000,
  });
}

async function loadMarketSnapshots(symbolIds: string[], since: Date | null) {
  return prisma.marketSnapshot.findMany({
    where: {
      symbolId: { in: symbolIds },
      ...(since ? { timestamp: { gte: since } } : {}),
    },
    select: {
      symbolId: true,
      timestamp: true,
      close: true,
    },
    orderBy: [{ symbolId: "asc" }, { timestamp: "asc" }],
    take: 100000,
  });
}

function groupBySymbol<T extends { symbolId: string }>(rows: T[]) {
  const map = new Map<string, T[]>();
  for (const row of rows) {
    const bucket = map.get(row.symbolId);
    if (bucket) bucket.push(row);
    else map.set(row.symbolId, [row]);
  }
  return map;
}

function buildRowsForSymbol(
  features: FeatureSnapshotWithSymbol[],
  markets: MarketSnapshotRow[],
  lookaheadBars: number,
  maxRowsPerSymbol: number,
): RegressionTrainingRow[] {
  if (features.length === 0 || markets.length < lookaheadBars + 1) return [];

  const rows: RegressionTrainingRow[] = [];
  let marketIdx = -1;
  const seenBaseSnapshots = new Set<string>();

  for (const feat of features) {
    while (marketIdx + 1 < markets.length && markets[marketIdx + 1]!.timestamp <= feat.timestamp) {
      marketIdx += 1;
    }
    if (marketIdx < 0) continue;
    if (marketIdx + lookaheadBars >= markets.length) break;

    const baseMarket = markets[marketIdx]!;
    const dedupeKey = `${feat.symbolId}:${baseMarket.timestamp.toISOString()}`;
    if (seenBaseSnapshots.has(dedupeKey)) continue;

    const parsed = parseFeatureVector(feat.featuresJson);
    if (!parsed) continue;

    const baseClose = toNum(baseMarket.close);
    const forward = markets.slice(marketIdx + 1, marketIdx + 1 + lookaheadBars).map((m) => toNum(m.close));
    if (forward.some((v) => !Number.isFinite(v) || v <= 0)) continue;

    const targets = computeForwardTargets(baseClose, forward);
    rows.push({
      symbolId: feat.symbolId,
      ticker: feat.symbol.ticker,
      segmentKey: feat.symbol.segmentKey ?? null,
      featureTimestamp: feat.timestamp.toISOString(),
      marketTimestamp: baseMarket.timestamp.toISOString(),
      baseClose,
      ...parsed,
      lookaheadBars,
      targetClose: targets.targetClose,
      targetReturn: targets.targetReturn,
      downsideReturn: targets.downsideReturn,
      downsideHit: targets.downsideHit,
    });
    seenBaseSnapshots.add(dedupeKey);
    if (rows.length >= maxRowsPerSymbol) break;
  }

  return rows;
}

export async function buildRegressionDataset(options?: {
  lookaheadBars?: number;
  since?: Date | null;
  maxRowsPerSymbol?: number;
}) {
  const lookaheadBars = Math.max(1, options?.lookaheadBars ?? 5);
  const maxRowsPerSymbol = Math.max(10, options?.maxRowsPerSymbol ?? 250);
  const since = options?.since ?? null;

  const features = await loadFeatureSnapshots(since);
  if (features.length === 0) {
    return {
      generatedAt: new Date().toISOString(),
      lookaheadBars,
      rowCount: 0,
      rows: [] as RegressionTrainingRow[],
    };
  }

  const symbolIds = [...new Set(features.map((f) => f.symbolId))];
  const markets = await loadMarketSnapshots(symbolIds, since);
  const featuresBySymbol = groupBySymbol(features);
  const marketsBySymbol = groupBySymbol(markets);
  const rows: RegressionTrainingRow[] = [];

  for (const [symbolId, featureRows] of featuresBySymbol) {
    rows.push(
      ...buildRowsForSymbol(
        featureRows,
        marketsBySymbol.get(symbolId) ?? [],
        lookaheadBars,
        maxRowsPerSymbol,
      ),
    );
  }

  rows.sort((a, b) => a.featureTimestamp.localeCompare(b.featureTimestamp) || a.ticker.localeCompare(b.ticker));

  return {
    generatedAt: new Date().toISOString(),
    lookaheadBars,
    rowCount: rows.length,
    rows,
  };
}
