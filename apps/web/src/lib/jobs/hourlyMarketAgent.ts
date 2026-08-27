/**
 * Orchestrator: `hourly-market-agent` — Build Spec §14
 */
import type { AppSettings } from "@prisma/client";
import { Prisma } from "@prisma/client";
import { randomUUID } from "node:crypto";
import { prisma } from "@/lib/db";
import { fetchDailySeries, fetchQuoteDetail } from "@/lib/data-provider/twelveData";
import { getTradableSymbols } from "@/lib/server/tradableSymbols";
import { writeDecisionExplainerSummary } from "@/lib/decision/explainer";
import type { OhlcvBar } from "@/lib/data-provider/twelveData";
import {
  computeFeatures,
  strategyScores,
  bearScores,
  type BearScoreBreakdown,
  type ScoreBreakdown,
  type StrategyMode,
} from "@/lib/portfolio/features";
import { applySlippage, grossNotional, realizedPnlCoverShort, signedExposureMarketValue, toNum, unrealizedPnlPosition, wholeShares } from "@/lib/portfolio/math";
import { assessMarketRegime, regimeAdjustedMaxNew } from "@/lib/portfolio/marketRegime";
import {
  computeAvgDollarVolume,
  readOptionalNumber,
  readOptionalString,
  volTargetSizeMultiplier,
} from "@/lib/portfolio/sizing";
import { evaluateBuyBlock } from "@/lib/rules/buyRules";
import { pickRotationTarget } from "@/lib/rules/rotationRules";
import { evaluateShortBlock, shouldCoverShort } from "@/lib/rules/shortRules";
import { shouldSell } from "@/lib/rules/sellRules";
import { applyLongUniversePolicy } from "@/lib/rules/universePolicy";
import {
  appendHoldingsReview,
  appendRunProgress,
  parseRunNotes,
  type HoldingsMarkEntry,
} from "@/lib/jobs/runProgress";
import { orderUniverseHoldingsFirst, prepareUniverseForFreeTier } from "@/lib/jobs/freeTierUniverse";
import {
  buildSettingsSnapshot,
  createRunAuditRecord,
  recordAuditFill,
  recordDataQualitySkip,
  type RunAuditRecord,
} from "@/lib/safety/auditTrail";
import {
  dataQualitySkipMessage,
  evaluateBars,
  evaluateQuote,
  type DataQualityResult,
  MIN_BARS_FOR_REGIME_SMA200,
  canOpenNewBuysFromBenchmark,
} from "@/lib/safety/marketDataGate";
import { admitPaperAgentRun } from "@/lib/safety/runAdmission";
import { hourBucketKey, shouldSkipDuplicateHourlyRun } from "@/lib/scheduler/idempotency";

export type RunAgentTrigger = "hourly" | "manual";

type SymbolRow = Awaited<ReturnType<typeof getTradableSymbols>>[number];
type RotationHolding = {
  positionId: string;
  symbolId: string;
  ticker: string;
  segmentKey: string | null;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  buyScore: number;
  sellRiskScore: number;
  confidenceScore: number;
  breakdown: ScoreBreakdown;
};

/** Stale `@prisma/client` may omit model delegates — `undefined.findFirst` at runtime. */
async function findLatestCashAfterPaperTrade(userId: string): Promise<{ cashAfter: unknown } | null> {
  const pt = (prisma as unknown as { paperTrade?: typeof prisma.paperTrade }).paperTrade;
  if (pt?.findFirst) {
    return pt.findFirst({
      where: { userId },
      orderBy: { executedAt: "desc" },
      select: { cashAfter: true },
    });
  }
  try {
    const rows = await prisma.$queryRaw<{ cashAfter: unknown }[]>(
      Prisma.sql`
        SELECT "cashAfter" FROM "PaperTrade"
        WHERE "userId" = ${userId}
        ORDER BY "executedAt" DESC
        LIMIT 1
      `,
    );
    return rows[0] ?? null;
  } catch {
    return null;
  }
}

async function findPreviousPortfolioSnapshotForPnl(userId: string): Promise<{ realizedPnl: unknown } | null> {
  const ps = (prisma as unknown as { portfolioSnapshot?: typeof prisma.portfolioSnapshot }).portfolioSnapshot;
  if (ps?.findFirst) {
    return ps.findFirst({
      where: { userId },
      orderBy: { timestamp: "desc" },
      select: { realizedPnl: true },
    });
  }
  try {
    const rows = await prisma.$queryRaw<{ realizedPnl: unknown }[]>(
      Prisma.sql`
        SELECT "realizedPnl" FROM "PortfolioSnapshot"
        WHERE "userId" = ${userId}
        ORDER BY "timestamp" DESC
        LIMIT 1
      `,
    );
    return rows[0] ?? null;
  } catch {
    return null;
  }
}

async function findRecentSellInCooldownWindow(
  userId: string,
  symbolId: string,
  cooldownCutoff: Date,
): Promise<{ id: string } | null> {
  const pt = (prisma as unknown as { paperTrade?: typeof prisma.paperTrade }).paperTrade;
  if (pt?.findFirst) {
    return pt.findFirst({
      where: {
        userId,
        symbolId,
        action: "SELL",
        executedAt: { gte: cooldownCutoff },
      },
      select: { id: true },
    });
  }
  try {
    const rows = await prisma.$queryRaw<{ id: string }[]>(
      Prisma.sql`
        SELECT id FROM "PaperTrade"
        WHERE "userId" = ${userId} AND "symbolId" = ${symbolId} AND action = 'SELL'
          AND "executedAt" >= ${cooldownCutoff}
        LIMIT 1
      `,
    );
    return rows[0] ?? null;
  } catch {
    return null;
  }
}

async function findRecentCoverInCooldownWindow(
  userId: string,
  symbolId: string,
  cooldownCutoff: Date,
): Promise<{ id: string } | null> {
  const pt = (prisma as unknown as { paperTrade?: typeof prisma.paperTrade }).paperTrade;
  if (pt?.findFirst) {
    return pt.findFirst({
      where: {
        userId,
        symbolId,
        action: "COVER",
        executedAt: { gte: cooldownCutoff },
      },
      select: { id: true },
    });
  }
  try {
    const rows = await prisma.$queryRaw<{ id: string }[]>(
      Prisma.sql`
        SELECT id FROM "PaperTrade"
        WHERE "userId" = ${userId} AND "symbolId" = ${symbolId} AND action = 'COVER'
          AND "executedAt" >= ${cooldownCutoff}
        LIMIT 1
      `,
    );
    return rows[0] ?? null;
  } catch {
    return null;
  }
}

async function fetchDefaultSearchProfile(userId: string): Promise<{
  id: string;
  name: string;
  profileJson: string;
} | null> {
  const sp = (prisma as unknown as { searchProfile?: typeof prisma.searchProfile }).searchProfile;
  if (sp?.findFirst) {
    return sp.findFirst({
      where: { userId, isDefault: true },
      select: { id: true, name: true, profileJson: true },
    });
  }
  try {
    const rows = await prisma.$queryRaw<{ id: string; name: string; profileJson: string }[]>(
      Prisma.sql`
        SELECT id, name, "profileJson" FROM "SearchProfile"
        WHERE "userId" = ${userId} AND "isDefault" = true
        LIMIT 1
      `,
    );
    return rows[0] ?? null;
  } catch {
    return null;
  }
}

async function getCurrentCash(userId: string, startingCash: number): Promise<number> {
  const last = await findLatestCashAfterPaperTrade(userId);
  if (last?.cashAfter != null) return toNum(last.cashAfter);
  return startingCash;
}

function mockBars(symbol: string, days = 90): OhlcvBar[] {
  const out: OhlcvBar[] = [];
  let seed = 0;
  for (let i = 0; i < symbol.length; i++) seed += symbol.charCodeAt(i);
  let p = 100 + (seed % 40);
  const start = new Date();
  start.setDate(start.getDate() - days);
  for (let i = 0; i < days; i++) {
    const t = new Date(start);
    t.setDate(t.getDate() + i);
    const pseudo = Math.sin(i * 0.15 + seed * 0.01) * 0.012;
    const ch = pseudo * p;
    p = Math.max(10, p + ch);
    out.push({
      time: t,
      open: p * 0.998,
      high: p * 1.005,
      low: p * 0.995,
      close: p,
      volume: 1e6,
    });
  }
  return out;
}

type SymbolTrends = { ret1d: number; ret5d: number; ret20d: number };

type PositionWithSymbol = {
  id: string;
  symbolId: string;
  symbol: { ticker: string; dataProviderSymbol: string | null; segmentKey: string | null };
  quantity: { toString(): string };
  avgCost: { toString(): string };
  isShort: boolean;
};

/** Live quotes for open lots — persists `QuoteSnapshot` rows when `persistQuoteRows`. */
async function applyLiveQuotesForHoldings(
  positions: PositionWithSymbol[],
  priceBySymbol: Map<string, number>,
  useMock: boolean,
  apiKey: string,
  runId: string,
  userId: string,
  persistQuoteRows: boolean,
): Promise<Map<string, "ok" | "stale">> {
  const m = new Map<string, "ok" | "stale">();
  if (positions.length === 0) return m;
  if (useMock) {
    for (const p of positions) m.set(p.symbolId, "ok");
    return m;
  }

  const rows: QuoteSnapshotBatchRow[] = [];

  for (const p of positions) {
    const sym = p.symbol.dataProviderSymbol ?? p.symbol.ticker;
    try {
      const q = await fetchQuoteDetail(sym, apiKey);
      const qQuality = evaluateQuote(q);
      if (!qQuality.ok || q.timestamp == null) {
        m.set(p.symbolId, "stale");
        continue;
      }
      priceBySymbol.set(p.symbolId, q.price);
      m.set(p.symbolId, "ok");
      if (persistQuoteRows) {
        rows.push({
          symbolId: p.symbolId,
          decisionRunId: runId,
          userId,
          timestamp: q.timestamp,
          price: q.price,
          open: q.open,
          high: q.high,
          low: q.low,
          previousClose: q.previousClose,
          change: q.change,
          changePercent: q.changePercent,
          volume: q.volume,
          source: "twelvedata",
          isRealtime: q.isRealtime,
          asOfMarketSession: q.asOfMarketSession,
        });
      }
    } catch {
      m.set(p.symbolId, "stale");
    }
  }
  if (persistQuoteRows && rows.length > 0) {
    await createQuoteSnapshotsMany(rows);
  }
  return m;
}

async function syncPaperQuoteFields(
  userId: string,
  positions: PositionWithSymbol[],
  fresh: Map<string, "ok" | "stale">,
) {
  const now = new Date();
  for (const p of positions) {
    const st = fresh.get(p.symbolId);
    /** Raw SQL: stale `@prisma/client` bundles may omit `lastQuoteAt` / `valuationStatus` on `updateMany`. */
    try {
      if (st === "ok") {
        await prisma.$executeRaw(
          Prisma.sql`
            UPDATE "PaperPosition"
            SET "lastQuoteAt" = ${now}, "valuationStatus" = 'ok'
            WHERE "userId" = ${userId} AND "symbolId" = ${p.symbolId} AND "isOpen" = true
          `,
        );
      } else {
        await prisma.$executeRaw(
          Prisma.sql`
            UPDATE "PaperPosition"
            SET "valuationStatus" = 'stale'
            WHERE "userId" = ${userId} AND "symbolId" = ${p.symbolId} AND "isOpen" = true
          `,
        );
      }
    } catch {
      /* columns not migrated yet or DB error */
    }
  }
}

type QuoteSnapshotBatchRow = {
  symbolId: string;
  decisionRunId: string;
  userId: string;
  timestamp: Date;
  price: number;
  open: number | null;
  high: number | null;
  low: number | null;
  previousClose: number | null;
  change: number | null;
  changePercent: number | null;
  volume: number | null;
  source: string;
  isRealtime: boolean;
  asOfMarketSession: string | null;
};

/** Stale `@prisma/client` may omit `quoteSnapshot.createMany`. */
async function createQuoteSnapshotsMany(rows: QuoteSnapshotBatchRow[]) {
  if (rows.length === 0) return;
  const cm = (prisma as unknown as { quoteSnapshot?: { createMany: (args: { data: QuoteSnapshotBatchRow[] }) => Promise<unknown> } })
    .quoteSnapshot?.createMany;
  if (cm) {
    await cm({ data: rows });
    return;
  }
  try {
    const tuples = rows.map((r) =>
      Prisma.sql`(${randomUUID()}, ${r.symbolId}, ${r.decisionRunId}, ${r.userId}, ${r.timestamp}, ${r.price}, ${r.open}, ${r.high}, ${r.low}, ${r.previousClose}, ${r.change}, ${r.changePercent}, ${r.volume}, ${r.source}, ${r.isRealtime}, ${r.asOfMarketSession})`,
    );
    await prisma.$executeRaw(
      Prisma.sql`
        INSERT INTO "QuoteSnapshot" (
          "id", "symbolId", "decisionRunId", "userId", "timestamp", "price",
          "open", "high", "low", "previousClose", "change", "changePercent", "volume",
          "source", "isRealtime", "asOfMarketSession"
        ) VALUES ${Prisma.join(tuples, ", ")}
      `,
    );
  } catch {
    /* optional */
  }
}

type PositionValuationBatchRow = {
  userId: string;
  symbolId: string;
  decisionRunId: string;
  quantity: number;
  avgCost: number;
  currentPrice: number;
  marketValue: number;
  unrealizedPnl: number;
  unrealizedPnlPct: number;
  valuationStatus: string;
};

/** Stale client may omit `positionValuation.createMany`. */
async function createPositionValuationsMany(data: PositionValuationBatchRow[]) {
  if (data.length === 0) return;
  const cm = (prisma as unknown as { positionValuation?: { createMany: (args: { data: PositionValuationBatchRow[] }) => Promise<unknown> } })
    .positionValuation?.createMany;
  if (cm) {
    await cm({ data });
    return;
  }
  const ts = new Date();
  try {
    const tuples = data.map((d) =>
      Prisma.sql`(${randomUUID()}, ${d.userId}, ${d.symbolId}, ${d.decisionRunId}, ${ts}, ${d.quantity}, ${d.avgCost}, ${d.currentPrice}, ${d.marketValue}, ${d.unrealizedPnl}, ${d.unrealizedPnlPct}, ${null}, ${null}, ${null}, ${d.valuationStatus})`,
    );
    await prisma.$executeRaw(
      Prisma.sql`
        INSERT INTO "PositionValuation" (
          "id", "userId", "symbolId", "decisionRunId", "timestamp",
          "quantity", "avgCost", "currentPrice", "marketValue", "unrealizedPnl", "unrealizedPnlPct",
          "sellRiskScore", "confidenceScore", "quoteSnapshotId", "valuationStatus"
        ) VALUES ${Prisma.join(tuples, ", ")}
      `,
    );
  } catch {
    /* optional */
  }
}

type MarketSnapshotBatchRow = {
  symbolId: string;
  timestamp: Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number | null;
  source: string;
  interval: string;
};

/** Stale client may omit `marketSnapshot.createMany`. */
async function createMarketSnapshotsMany(rows: MarketSnapshotBatchRow[]) {
  if (rows.length === 0) return;
  const cm = (prisma as unknown as { marketSnapshot?: { createMany: (args: { data: MarketSnapshotBatchRow[] }) => Promise<unknown> } })
    .marketSnapshot?.createMany;
  if (cm) {
    await cm({ data: rows });
    return;
  }
  try {
    const tuples = rows.map((r) =>
      Prisma.sql`(${randomUUID()}, ${r.symbolId}, ${r.timestamp}, ${r.open}, ${r.high}, ${r.low}, ${r.close}, ${r.volume}, ${r.source}, ${r.interval})`,
    );
    await prisma.$executeRaw(
      Prisma.sql`
        INSERT INTO "MarketSnapshot" (
          "id", "symbolId", "timestamp", "open", "high", "low", "close", "volume", "source", "interval"
        ) VALUES ${Prisma.join(tuples, ", ")}
      `,
    );
  } catch {
    /* optional */
  }
}

async function persistPositionValuationRound(
  userId: string,
  runId: string,
  positions: PositionWithSymbol[],
  priceBySymbol: Map<string, number>,
  fresh: Map<string, "ok" | "stale">,
) {
  const data: PositionValuationBatchRow[] = positions.map((p) => {
    const px = priceBySymbol.get(p.symbolId) ?? toNum(p.avgCost);
    const qty = toNum(p.quantity);
    const avg = toNum(p.avgCost);
    const isShort = p.isShort;
    const mv = qty * px;
    const u = unrealizedPnlPosition(qty, avg, px, isShort);
    const denom = qty * avg;
    const uPct = denom > 0 ? (u / denom) * 100 : 0;
    return {
      userId,
      symbolId: p.symbolId,
      decisionRunId: runId,
      quantity: qty,
      avgCost: avg,
      currentPrice: px,
      marketValue: mv,
      unrealizedPnl: u,
      unrealizedPnlPct: uPct,
      valuationStatus: fresh.get(p.symbolId) === "ok" ? "ok" : "stale",
    };
  });
  await createPositionValuationsMany(data);
}

async function ensureHeldSymbolPricing(
  pos: PositionWithSymbol,
  priceBySymbol: Map<string, number>,
  trendBySymbolId: Map<string, SymbolTrends>,
  useMock: boolean,
  apiKey: string,
  barsBySymbol?: Map<string, OhlcvBar[]>,
): Promise<void> {
  if (priceBySymbol.has(pos.symbolId) && trendBySymbolId.has(pos.symbolId)) return;
  const td = pos.symbol.dataProviderSymbol ?? pos.symbol.ticker;
  try {
    const bars = useMock ? mockBars(pos.symbol.ticker) : await fetchDailySeries(td, apiKey, 120);
    const quality = evaluateBars(bars);
    if (!quality.ok) return;
    const last = bars[bars.length - 1];
    if (last) priceBySymbol.set(pos.symbolId, last.close);
    barsBySymbol?.set(pos.symbolId, bars);
    if (last) priceBySymbol.set(pos.symbolId, last.close);
    const { features } = computeFeatures(bars);
    trendBySymbolId.set(pos.symbolId, {
      ret1d: features.ret1d,
      ret5d: features.ret5d,
      ret20d: features.ret20d,
    });
  } catch {
    /* missing price handled in buildHoldingsMarkPayload */
  }
}

function buildHoldingsMarkPayload(
  positions: PositionWithSymbol[],
  priceBySymbol: Map<string, number>,
  trendBySymbolId: Map<string, SymbolTrends>,
): { lines: { message: string; detail: string | null }[]; entries: HoldingsMarkEntry[] } {
  const sorted = [...positions].sort((a, b) => a.symbol.ticker.localeCompare(b.symbol.ticker));
  const lines: { message: string; detail: string | null }[] = [];
  const entries: HoldingsMarkEntry[] = [];
  const pct = (x: number) => (Math.abs(x) * 100).toFixed(2);
  const sgn = (n: number) => (n >= 0 ? "+" : "");

  for (const pos of sorted) {
    const px = priceBySymbol.get(pos.symbolId);
    const qty = toNum(pos.quantity);
    const avg = toNum(pos.avgCost);
    const isShort = pos.isShort;
    const t = trendBySymbolId.get(pos.symbolId) ?? { ret1d: 0, ret5d: 0, ret20d: 0 };

    if (px == null || Number.isNaN(px)) {
      lines.push({
        message: `${pos.symbol.ticker}: no quote — cannot mark P&L`,
        detail: "Symbol may be outside the active universe or data failed.",
      });
      continue;
    }

    const costBasis = qty * avg;
    const marketValue = qty * px;
    const unrealizedPnl = unrealizedPnlPosition(qty, avg, px, isShort);
    const unrealizedPct = costBasis > 0 ? (unrealizedPnl / costBasis) * 100 : 0;
    const tag = isShort ? "SHORT " : "";

    entries.push({
      ticker: pos.symbol.ticker,
      symbolId: pos.symbolId,
      quantity: qty,
      avgCost: avg,
      lastPrice: px,
      marketValue,
      costBasis,
      unrealizedPnl,
      unrealizedPct,
      ret1d: t.ret1d,
      ret5d: t.ret5d,
      ret20d: t.ret20d,
    });

    lines.push({
      message: `${tag}${pos.symbol.ticker}: $${marketValue.toFixed(2)} mkt vs $${costBasis.toFixed(2)} entry → ${sgn(unrealizedPnl)}$${Math.abs(unrealizedPnl).toFixed(2)} (${sgn(unrealizedPct)}${Math.abs(unrealizedPct).toFixed(2)}%)`,
      detail: `Share price moves: 1d ${sgn(t.ret1d)}${pct(t.ret1d)}% · 5d ${sgn(t.ret5d)}${pct(t.ret5d)}% · 20d ${sgn(t.ret20d)}${pct(t.ret20d)}%`,
    });
  }

  return { lines, entries };
}

/** Per-symbol row for DecisionRunCandidate (full explorer grid). */
type ExplorerRow = {
  ticker: string;
  segmentKey: string | null;
  status: string;
  currentPrice: number | null;
  ret1d: number | null;
  ret5d: number | null;
  volatility20d: number | null;
  buyScore: number | null;
  sellRiskScore: number | null;
  confidenceScore: number | null;
  buyRank: number | null;
  rejectionReason: string | null;
};

function mergeExplorer(
  m: Map<string, ExplorerRow>,
  symbolId: string,
  patch: Partial<ExplorerRow> & { ticker: string },
) {
  const prev = m.get(symbolId);
  m.set(symbolId, {
    ticker: patch.ticker,
    segmentKey: patch.segmentKey !== undefined ? patch.segmentKey : (prev?.segmentKey ?? null),
    status: patch.status ?? prev?.status ?? "scored",
    currentPrice: patch.currentPrice !== undefined ? patch.currentPrice : (prev?.currentPrice ?? null),
    ret1d: patch.ret1d !== undefined ? patch.ret1d : (prev?.ret1d ?? null),
    ret5d: patch.ret5d !== undefined ? patch.ret5d : (prev?.ret5d ?? null),
    volatility20d: patch.volatility20d !== undefined ? patch.volatility20d : (prev?.volatility20d ?? null),
    buyScore: patch.buyScore !== undefined ? patch.buyScore : (prev?.buyScore ?? null),
    sellRiskScore: patch.sellRiskScore !== undefined ? patch.sellRiskScore : (prev?.sellRiskScore ?? null),
    confidenceScore: patch.confidenceScore !== undefined ? patch.confidenceScore : (prev?.confidenceScore ?? null),
    buyRank: patch.buyRank !== undefined ? patch.buyRank : (prev?.buyRank ?? null),
    rejectionReason:
      patch.rejectionReason !== undefined ? patch.rejectionReason : (prev?.rejectionReason ?? null),
  });
}

async function persistQualitySkip(args: {
  runId: string;
  symbolId: string;
  ticker: string;
  segmentKey: string | null;
  result: Extract<DataQualityResult, { ok: false }>;
  explorer: Map<string, ExplorerRow>;
  audit: RunAuditRecord;
  phase?: string;
  status?: string;
}): Promise<void> {
  mergeExplorer(args.explorer, args.symbolId, {
    ticker: args.ticker,
    segmentKey: args.segmentKey,
    status: args.status ?? "ingest_failed",
    currentPrice: null,
    ret1d: null,
    ret5d: null,
    volatility20d: null,
    buyScore: null,
    sellRiskScore: null,
    confidenceScore: null,
    buyRank: null,
    rejectionReason: args.result.reason,
  });
  await prisma.decisionRunItem.create({
    data: {
      decisionRunId: args.runId,
      symbolId: args.symbolId,
      actionRecommendation: "skip",
      blocked: true,
      blockedReason: args.result.reason,
      rationaleShort: dataQualitySkipMessage(args.result),
    },
  });
  recordDataQualitySkip(args.audit, {
    ticker: args.ticker,
    reason: args.result.reason,
    detail: args.result.detail,
  });
  await appendRunProgress(
    args.runId,
    args.phase ?? "ingest",
    `${args.ticker}: no-trade (${args.result.reason})`,
    args.result.detail,
  );
}

async function persistExplorerRows(runId: string, explorer: Map<string, ExplorerRow>) {
  const data = [...explorer.entries()].map(([symbolId, r]) => ({
    decisionRunId: runId,
    symbolId,
    ticker: r.ticker,
    segmentKey: r.segmentKey,
    status: r.status,
    currentPrice: r.currentPrice,
    ret1d: r.ret1d,
    ret5d: r.ret5d,
    volatility20d: r.volatility20d,
    buyScore: r.buyScore,
    sellRiskScore: r.sellRiskScore,
    confidenceScore: r.confidenceScore,
    buyRank: r.buyRank,
    rejectionReason: r.rejectionReason,
  }));
  if (data.length === 0) return;

  const delegate = (prisma as unknown as { decisionRunCandidate?: { createMany: (args: { data: typeof data }) => Promise<unknown> } })
    .decisionRunCandidate?.createMany;
  if (delegate) {
    await delegate({ data });
    return;
  }

  try {
    const tuples = [...explorer.entries()].map(([symbolId, r]) =>
      Prisma.sql`(${randomUUID()}, ${runId}, ${symbolId}, ${r.ticker}, ${r.segmentKey}, ${r.status}, ${r.currentPrice}, ${r.ret1d}, ${r.ret5d}, ${r.volatility20d}, ${r.buyScore}, ${r.sellRiskScore}, ${r.confidenceScore}, ${r.buyRank}, ${r.rejectionReason})`,
    );
    await prisma.$executeRaw(
      Prisma.sql`
        INSERT INTO "DecisionRunCandidate" (
          "id", "decisionRunId", "symbolId", "ticker", "segmentKey", "status",
          "currentPrice", "ret1d", "ret5d", "volatility20d",
          "buyScore", "sellRiskScore", "confidenceScore", "buyRank", "rejectionReason"
        ) VALUES ${Prisma.join(tuples, ", ")}
      `,
    );
  } catch {
    /* stale client or missing table — explorer persistence is optional */
  }
}

async function fetchEnabledSegmentsMeta(): Promise<{ key: string; name: string }[]> {
  const d = (prisma as unknown as { universeSegment?: typeof prisma.universeSegment }).universeSegment;
  if (d?.findMany) {
    return d.findMany({ where: { isEnabled: true }, select: { key: true, name: true } });
  }
  try {
    return await prisma.$queryRaw<{ key: string; name: string }[]>(
      Prisma.sql`SELECT key, name FROM "UniverseSegment" WHERE "isEnabled" = true`,
    );
  } catch {
    return [];
  }
}

async function insertDecisionSearchSnapshotRow(data: {
  decisionRunId: string;
  searchProfileId: string | null | undefined;
  profileName: string | null;
  profileJson: string | null;
  statsJson: string;
  filtersJson: string;
  rankingInputsJson: string;
  candidateExplorerJson: string;
}) {
  const create = (prisma as unknown as { decisionSearchSnapshot?: { create: (args: { data: typeof data }) => Promise<unknown> } })
    .decisionSearchSnapshot?.create;
  if (create) {
    await create({ data });
    return;
  }
  try {
    await prisma.$executeRaw(
      Prisma.sql`
        INSERT INTO "DecisionSearchSnapshot" (
          "id", "decisionRunId", "searchProfileId", "profileName", "profileJson",
          "filtersJson", "rankingInputsJson", "candidateExplorerJson", "statsJson"
        ) VALUES (
          ${randomUUID()},
          ${data.decisionRunId},
          ${data.searchProfileId ?? null},
          ${data.profileName},
          ${data.profileJson},
          ${data.filtersJson},
          ${data.rankingInputsJson},
          ${data.candidateExplorerJson},
          ${data.statsJson}
        )
      `,
    );
  } catch {
    /* optional */
  }
}

async function hourlyMarketAgentPipeline(
  userId: string,
  runId: string,
  settings: AppSettings,
  incomingSymbols: SymbolRow[],
  starting: number,
  useMock: boolean,
  apiKey: string,
): Promise<void> {
  const cashBeforeRun = await getCurrentCash(userId, starting);
  const strategyMode = ((readOptionalString(settings, "strategyMode") ?? "rules_v1") as StrategyMode);
  const strategyModelVersion =
    strategyMode === "alpha_v1"
      ? "alpha-v1"
      : strategyMode === "regression_v1"
        ? "regression-v1"
        : "rules-v1";
  const audit = createRunAuditRecord({
    strategyMode,
    modelVersion: strategyModelVersion,
    dataSource: useMock ? "mock" : "twelvedata",
    settings: buildSettingsSnapshot({
      ...settings,
      strategyMode,
      agentPaused: (settings as { agentPaused?: boolean }).agentPaused === true,
    }),
  });
  const barsBySymbol = new Map<string, OhlcvBar[]>();
  const positions = await prisma.paperPosition.findMany({
    where: { userId, isOpen: true },
    include: { symbol: true },
  });

  const heldIds = new Set(positions.map((p) => p.symbolId));
  const prep = useMock
    ? {
        symbols: orderUniverseHoldingsFirst(incomingSymbols, heldIds),
        detail:
          heldIds.size > 0
            ? `Scan order: ${heldIds.size} open holding(s) first (mock data).`
            : null,
      }
    : prepareUniverseForFreeTier(incomingSymbols, heldIds);
  const symbols = prep.symbols;

  await prisma.decisionRun.update({
    where: { id: runId },
    data: { universeSize: symbols.length },
  });

  await appendRunProgress(
    runId,
    "portfolio",
    `Loaded portfolio: $${cashBeforeRun.toFixed(2)} cash, ${positions.length} open position(s)`,
  );

  let portfolioValueBefore = cashBeforeRun;
  const priceBySymbol = new Map<string, number>();
  let realizedPnlThisRun = 0;

  try {
    if (prep.detail) {
      await appendRunProgress(runId, "universe", prep.detail);
    }
    await appendRunProgress(runId, "ingest", `Ingesting & scoring ${symbols.length} symbols…`);

    const trendBySymbolId = new Map<string, SymbolTrends>();
    const explorer = new Map<string, ExplorerRow>();
    let ingested = 0;
    for (const s of symbols) {
      const tdSymbol = s.dataProviderSymbol ?? s.ticker;
      try {
        const bars = useMock ? mockBars(s.ticker) : await fetchDailySeries(tdSymbol, apiKey, 120);
        const quality = evaluateBars(bars);
        if (!quality.ok) {
          await persistQualitySkip({
            runId,
            symbolId: s.id,
            ticker: s.ticker,
            segmentKey: s.segmentKey ?? null,
            result: quality,
            explorer,
            audit,
          });
          continue;
        }
        const last = bars[bars.length - 1];
        if (!last) {
          await persistQualitySkip({
            runId,
            symbolId: s.id,
            ticker: s.ticker,
            segmentKey: s.segmentKey ?? null,
            result: { ok: false, reason: "MISSING_BARS", detail: "Validated series had no last bar." },
            explorer,
            audit,
          });
          continue;
        }
        priceBySymbol.set(s.id, last.close);
        barsBySymbol.set(s.id, bars);

        const { features, completeness } = computeFeatures(bars);
        trendBySymbolId.set(s.id, {
          ret1d: features.ret1d,
          ret5d: features.ret5d,
          ret20d: features.ret20d,
        });
        const scores = strategyScores(strategyMode, features);
        audit.featureInputs = audit.featureInputs ?? {};
        audit.featureInputs[s.ticker] = {
          ...features,
          completeness,
          source: useMock ? "mock" : "twelvedata",
          barAsOf: last.time instanceof Date ? last.time.toISOString() : String(last.time),
        };

        await prisma.marketSnapshot.create({
          data: {
            symbolId: s.id,
            timestamp: last?.time ?? new Date(),
            open: last?.open ?? 0,
            high: last?.high ?? 0,
            low: last?.low ?? 0,
            close: last?.close ?? 0,
            volume: last.volume,
            source: useMock ? "mock" : "twelvedata",
            interval: "1day",
          },
        });

        const featRow = await prisma.featureSnapshot.create({
          data: {
            symbolId: s.id,
            timestamp: new Date(),
            featuresJson: JSON.stringify({ ...features, ticker: s.ticker }),
            dataCompletenessScore: completeness,
          },
        });

        await prisma.modelScore.create({
          data: {
            symbolId: s.id,
            timestamp: new Date(),
            buyScore: scores.buyScore,
            sellRiskScore: scores.sellRiskScore,
            expectedReturn5d: scores.expectedReturn5d,
            expectedDrawdownRisk5d: scores.expectedDrawdownRisk5d,
            confidenceScore: scores.confidenceScore,
            modelVersion: strategyModelVersion,
            featureSnapshotId: featRow.id,
          },
        });
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "scored",
          currentPrice: last.close,
          ret1d: features.ret1d,
          ret5d: features.ret5d,
          volatility20d: features.vol20,
          buyScore: scores.buyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          buyRank: null,
          rejectionReason: null,
        });
        ingested++;
        await appendRunProgress(
          runId,
          "ingest",
          `${s.ticker}: buy ${scores.buyScore}, sellRisk ${scores.sellRiskScore}, conf ${scores.confidenceScore}`,
          scores.breakdown.featureSummary,
        );
      } catch {
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "ingest_failed",
          currentPrice: null,
          ret1d: null,
          ret5d: null,
          volatility20d: null,
          buyScore: null,
          sellRiskScore: null,
          confidenceScore: null,
          buyRank: null,
          rejectionReason: "data_fetch_failed",
        });
        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: s.id,
            actionRecommendation: "skip",
            blocked: true,
            blockedReason: "data_fetch_failed",
            rationaleShort: `Failed to load ${tdSymbol}`,
          },
        });
        await appendRunProgress(runId, "ingest", `${s.ticker}: failed to load data`, tdSymbol);
      }
    }

    await appendRunProgress(
      runId,
      "ingest",
      `Universe ingest finished (${ingested}/${symbols.length} OK)`,
    );

    for (const pos of positions) {
      await ensureHeldSymbolPricing(pos, priceBySymbol, trendBySymbolId, useMock, apiKey, barsBySymbol);
    }

    const quoteFreshPre = await applyLiveQuotesForHoldings(
      positions,
      priceBySymbol,
      useMock,
      apiKey,
      runId,
      userId,
      true,
    );
    await syncPaperQuoteFields(userId, positions, quoteFreshPre);
    await persistPositionValuationRound(userId, runId, positions, priceBySymbol, quoteFreshPre);

    for (const pos of positions) {
      const px = priceBySymbol.get(pos.symbolId);
      if (px == null) continue;
      portfolioValueBefore += signedExposureMarketValue(toNum(pos.quantity), px, pos.isShort);
    }

    await prisma.decisionRun.update({
      where: { id: runId },
      data: { portfolioValueBefore, candidatesCount: symbols.length },
    });

    await appendRunProgress(
      runId,
      "valuation",
      `Mark-to-market portfolio before trades: ~$${portfolioValueBefore.toFixed(2)}`,
    );

    const beforeHoldings = buildHoldingsMarkPayload(positions, priceBySymbol, trendBySymbolId);
    await appendHoldingsReview(
      runId,
      "before",
      positions.length === 0
        ? "Holdings: no open positions at start"
        : `Holdings (${positions.length}): value, unrealized P&L, and price trends (1d / 5d / 20d)`,
      positions.length === 0
        ? [{ message: "No open positions — portfolio is all cash.", detail: null }]
        : beforeHoldings.lines,
      beforeHoldings.entries,
    );

    const slippage = toNum(settings.defaultSlippagePct);
    const stopLoss = toNum(settings.stopLossPct);
    const takeProfit = toNum(settings.takeProfitPct);
    const sellRiskTh = toNum(settings.sellRiskThreshold);
    const maxNew = settings.maxNewPositionsPerRun;
    const maxPosPct = toNum(settings.maxPositionPct);
    const reservePct = toNum(settings.cashReservePct);
    const minConf = toNum(settings.minConfidence);
    const buyTh = toNum(settings.buyScoreThreshold);
    const buyScoreMargin = toNum(settings.buyScoreMargin);
    const confidenceMarginForBuy = toNum(settings.confidenceMarginForBuy);
    const maxBuyAnnualVolRaw = toNum(settings.maxBuyAnnualVol);
    const maxBuyAnnualVol = maxBuyAnnualVolRaw > 0 ? maxBuyAnnualVolRaw : 0.6;
    const bearScoreThreshold = toNum(settings.bearScoreThreshold);
    const confidenceMarginForShort = toNum(settings.confidenceMarginForShort);
    const maxShortPositionsPerRun = settings.maxShortPositionsPerRun;
    const shortOnlyInBearRegime = settings.shortOnlyInBearRegime;
    const buyScoreCoverShortThreshold = toNum(settings.buyScoreCoverShortThreshold);
    const cooldownHrs = settings.cooldownHours;
    // New tunables (defaults preserve current behavior when unset).
    const trailingGiveBackPct = readOptionalNumber(settings, "trailingGiveBackPct");
    const minDollarVolume = readOptionalNumber(settings, "minDollarVolume") ?? 0;
    const volTargetAnnualized = readOptionalNumber(settings, "volTargetAnnualized") ?? 0;
    const regimeFilterMode = readOptionalString(settings, "regimeFilterMode");
    const rotationMinBuyScoreEdge = readOptionalNumber(settings, "rotationMinBuyScoreEdge") ?? 8;
    const rotationWeakHoldMaxBuyScore = readOptionalNumber(settings, "rotationWeakHoldMaxBuyScore") ?? Math.max(buyTh + 5, 55);
    const rotationMinHeldSellRisk = readOptionalNumber(settings, "rotationMinHeldSellRisk") ?? Math.max(sellRiskTh - 20, 45);
    const rotationMaxReplacementsPerRun = Math.max(
      0,
      Math.floor(readOptionalNumber(settings, "rotationMaxReplacementsPerRun") ?? 1),
    );
    const rotationMaxCandidateSellRiskSpread =
      readOptionalNumber(settings, "rotationMaxCandidateSellRiskSpread") ?? 5;

    let cash = cashBeforeRun;
    const rotationPool: RotationHolding[] = [];

    await appendRunProgress(runId, "sells", `Evaluating sells for ${positions.length} holding(s)…`);

    for (const pos of positions) {
      if (quoteFreshPre.get(pos.symbolId) === "stale" && !settings.staleQuoteAllowSells) {
        mergeExplorer(explorer, pos.symbolId, {
          ticker: pos.symbol.ticker,
          segmentKey: pos.symbol.segmentKey ?? null,
          status: "stale_hold",
          rejectionReason: "STALE_DATA_HOLD",
        });
        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: pos.symbolId,
            actionRecommendation: "hold",
            blocked: true,
            blockedReason: "STALE_DATA_HOLD",
            rationaleShort:
              "Fresh quote unavailable (STALE_DATA_HOLD). Enable “Allow sells when quote is stale” in app settings to override.",
          },
        });
        await appendRunProgress(
          runId,
          "sells",
          `Hold ${pos.symbol.ticker} — stale quote; sell blocked`,
          "Quote refresh failed for this symbol this run.",
        );
        continue;
      }
      const px = priceBySymbol.get(pos.symbolId);
      if (px == null) {
        mergeExplorer(explorer, pos.symbolId, {
          ticker: pos.symbol.ticker,
          segmentKey: pos.symbol.segmentKey ?? null,
          status: "skipped_sell",
          rejectionReason: "missing_price",
        });
        continue;
      }
      const qty = toNum(pos.quantity);
      const avg = toNum(pos.avgCost);
      const posBars = barsBySymbol.get(pos.symbolId) ?? (useMock
        ? mockBars(pos.symbol.ticker)
        : await fetchDailySeries(pos.symbol.dataProviderSymbol ?? pos.symbol.ticker, apiKey, 120));
      const posQuality = evaluateBars(posBars);
      if (!posQuality.ok) {
        await persistQualitySkip({
          runId,
          symbolId: pos.symbolId,
          ticker: pos.symbol.ticker,
          segmentKey: pos.symbol.segmentKey ?? null,
          result: posQuality,
          explorer,
          audit,
          phase: "sells",
          status: "skipped_sell",
        });
        continue;
      }
      barsBySymbol.set(pos.symbolId, posBars);
      const feat = computeFeatures(posBars).features;

      const recentSlice = posBars.slice(-30);
      const recentHigh =
        recentSlice.length > 0
          ? recentSlice.reduce((m, b) => {
              const v = Number(b.high) || Number(b.close);
              return v > m ? v : m;
            }, 0)
          : undefined;
      const recentLowCand =
        recentSlice.length > 0
          ? recentSlice.reduce((m, b) => {
              const v = Number(b.low) || Number(b.close);
              return v < m ? v : m;
            }, Number.POSITIVE_INFINITY)
          : undefined;
      const recentLow =
        recentLowCand != null && Number.isFinite(recentLowCand) ? recentLowCand : undefined;

      const scores = strategyScores(strategyMode, feat);

      if (pos.isShort) {
        const coverDecision = shouldCoverShort({
          currentPrice: px,
          avgCostShort: avg,
          stopLossPct: stopLoss,
          takeProfitPct: takeProfit,
          buyScore: scores.buyScore,
          buyScoreCoverThreshold: buyScoreCoverShortThreshold,
          ret5d: feat.ret5d,
          rsi: feat.rsi14,
          recentLow: recentLow != null && recentLow > 0 ? recentLow : undefined,
          trailingGiveBackPct,
        });

        if (!coverDecision.cover) {
          mergeExplorer(explorer, pos.symbolId, {
            ticker: pos.symbol.ticker,
            segmentKey: pos.symbol.segmentKey ?? null,
            status: "held_short",
            buyScore: scores.buyScore,
            sellRiskScore: scores.sellRiskScore,
            confidenceScore: scores.confidenceScore,
            rejectionReason: null,
          });
          await prisma.decisionRunItem.create({
            data: {
              decisionRunId: runId,
              symbolId: pos.symbolId,
              actionRecommendation: "hold",
              blocked: false,
              buyScore: scores.buyScore,
              sellRiskScore: scores.sellRiskScore,
              confidenceScore: scores.confidenceScore,
              rationaleShort: `Hold short — ${scores.breakdown.featureSummary}`,
            },
          });
          continue;
        }

        const exec = applySlippage(px, "BUY", slippage);
        const gross = qty * exec;
        const fees = 0;
        realizedPnlThisRun += realizedPnlCoverShort(qty, avg, exec);
        const cashBefore = cash;
        cash = cashBefore - gross - fees;

        const coverReasonText = `${coverDecision.detail}. Signals: ${scores.breakdown.featureSummary}`;
        await prisma.paperTrade.create({
          data: {
            userId,
            symbolId: pos.symbolId,
            decisionRunId: runId,
            action: "COVER",
            quantity: qty,
            price: exec,
            slippagePct: slippage,
            fees,
            grossAmount: gross,
            reasonCode: coverDecision.code,
            reasonText: coverReasonText,
            modelVersion: strategyModelVersion,
            confidenceScore: scores.confidenceScore,
            cashBefore,
            cashAfter: cash,
            expectedHorizon: "5d",
          },
        });
        recordAuditFill(audit, {
          action: "COVER",
          ticker: pos.symbol.ticker,
          quantity: qty,
          rawPrice: px,
          fillPrice: exec,
          slippagePct: slippage,
          cashBefore,
          cashAfter: cash,
          reasonCode: coverDecision.code,
          reasonText: coverReasonText,
        });

        await prisma.paperPosition.update({
          where: { id: pos.id },
          data: { isOpen: false, quantity: 0, isShort: false, lastUpdatedAt: new Date() },
        });

        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: pos.symbolId,
            actionRecommendation: "cover",
            blocked: false,
            buyScore: scores.buyScore,
            sellRiskScore: scores.sellRiskScore,
            confidenceScore: scores.confidenceScore,
            rationaleShort: `${coverDecision.detail}. ${scores.breakdown.featureSummary}`,
          },
        });

        mergeExplorer(explorer, pos.symbolId, {
          ticker: pos.symbol.ticker,
          segmentKey: pos.symbol.segmentKey ?? null,
          status: "covered",
          buyScore: scores.buyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          rejectionReason: null,
        });

        await appendRunProgress(
          runId,
          "sell",
          `COVER ${pos.symbol.ticker} × ${qty} @ ${exec.toFixed(4)} — ${coverDecision.detail}`,
          scores.breakdown.featureSummary,
        );
        continue;
      }

      const sellDecision = shouldSell({
        currentPrice: px,
        avgCost: avg,
        stopLossPct: stopLoss,
        takeProfitPct: takeProfit,
        sellRiskScore: scores.sellRiskScore,
        sellRiskThreshold: sellRiskTh,
        ret5d: feat.ret5d,
        rsi: feat.rsi14,
        recentHigh: recentHigh && recentHigh > 0 ? recentHigh : undefined,
        trailingGiveBackPct,
      });

      if (!sellDecision.sell) {
        rotationPool.push({
          positionId: pos.id,
          symbolId: pos.symbolId,
          ticker: pos.symbol.ticker,
          segmentKey: pos.symbol.segmentKey ?? null,
          quantity: qty,
          avgCost: avg,
          currentPrice: px,
          buyScore: scores.buyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          breakdown: scores.breakdown,
        });
        mergeExplorer(explorer, pos.symbolId, {
          ticker: pos.symbol.ticker,
          segmentKey: pos.symbol.segmentKey ?? null,
          status: "held",
          buyScore: scores.buyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          rejectionReason: null,
        });
        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: pos.symbolId,
            actionRecommendation: "hold",
            blocked: false,
            buyScore: scores.buyScore,
            sellRiskScore: scores.sellRiskScore,
            confidenceScore: scores.confidenceScore,
            rationaleShort: `Hold — ${scores.breakdown.featureSummary}. Sell risk factors: ${scores.breakdown.sellRiskFactors.join("; ")}`,
          },
        });
        continue;
      }

      const exec = applySlippage(px, "SELL", slippage);
      const gross = qty * exec;
      const fees = 0;
      realizedPnlThisRun += qty * (exec - avg);
      const cashBefore = cash;
      cash = cashBefore + gross - fees;

      const sellReasonText = `${sellDecision.detail}. Signals: ${scores.breakdown.featureSummary}. Sell risk factors: ${scores.breakdown.sellRiskFactors.join("; ")}`;
      await prisma.paperTrade.create({
        data: {
          userId,
          symbolId: pos.symbolId,
          decisionRunId: runId,
            action: "SELL",
            quantity: qty,
            price: exec,
            slippagePct: slippage,
            fees,
            grossAmount: gross,
            reasonCode: sellDecision.code,
            reasonText: sellReasonText,
            modelVersion: strategyModelVersion,
            confidenceScore: scores.confidenceScore,
            cashBefore,
            cashAfter: cash,
            expectedHorizon: "5d",
          },
        });
        recordAuditFill(audit, {
          action: "SELL",
          ticker: pos.symbol.ticker,
          quantity: qty,
          rawPrice: px,
          fillPrice: exec,
          slippagePct: slippage,
          cashBefore,
          cashAfter: cash,
          reasonCode: sellDecision.code,
          reasonText: sellReasonText,
        });

      await prisma.paperPosition.update({
        where: { id: pos.id },
        data: { isOpen: false, quantity: 0, isShort: false, lastUpdatedAt: new Date() },
      });

      await prisma.decisionRun.update({
        where: { id: runId },
        data: { sellsCount: { increment: 1 } },
      });

      await prisma.decisionRunItem.create({
        data: {
          decisionRunId: runId,
          symbolId: pos.symbolId,
          actionRecommendation: "sell",
          blocked: false,
          buyScore: scores.buyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          rationaleShort: `${sellDecision.detail}. ${scores.breakdown.featureSummary}`,
        },
      });

      mergeExplorer(explorer, pos.symbolId, {
        ticker: pos.symbol.ticker,
        segmentKey: pos.symbol.segmentKey ?? null,
        status: "sold",
        buyScore: scores.buyScore,
        sellRiskScore: scores.sellRiskScore,
        confidenceScore: scores.confidenceScore,
        rejectionReason: null,
      });

      await appendRunProgress(
        runId,
        "sell",
        `SELL ${pos.symbol.ticker} × ${qty} @ ${exec.toFixed(4)} — ${sellDecision.detail}`,
        `${scores.breakdown.featureSummary} | Sell risk: ${scores.breakdown.sellRiskFactors.join("; ")}`,
      );
    }

    // Market regime check (soft buy throttle). SPY bars are also reused for benchmark later.
    // SMA200 needs 200 closes; a shorter series must not fall through as "neutral" and allow full buys.
    let spyBars: OhlcvBar[] = [];
    let spyQuality = evaluateBars(spyBars, { minBars: MIN_BARS_FOR_REGIME_SMA200 });
    try {
      spyBars = useMock ? mockBars("SPY", 260) : await fetchDailySeries("SPY", apiKey, 260);
      spyQuality = evaluateBars(spyBars, { minBars: MIN_BARS_FOR_REGIME_SMA200 });
      if (!spyQuality.ok) {
        recordDataQualitySkip(audit, { ticker: "SPY", reason: spyQuality.reason, detail: spyQuality.detail });
        await appendRunProgress(runId, "regime", `SPY data invalid — new buys blocked (${spyQuality.reason})`, spyQuality.detail);
      }
    } catch (e) {
      const detail = e instanceof Error ? e.message : String(e);
      spyQuality = { ok: false, reason: "MISSING_BARS", detail };
      recordDataQualitySkip(audit, { ticker: "SPY", reason: "MISSING_BARS", detail });
      await appendRunProgress(runId, "regime", "SPY data missing — new buys blocked", detail);
      spyBars = [];
    }
    const regime = assessMarketRegime(spyQuality.ok ? spyBars.map((b) => b.close) : []);
    const spyAllowsNewBuys = canOpenNewBuysFromBenchmark({ barQuality: spyQuality, sma200: regime.sma200 });
    const regimeAllowsShort = spyAllowsNewBuys && (!shortOnlyInBearRegime || regime.regime === "bearish");
    const regimeAdj = spyAllowsNewBuys
      ? regimeAdjustedMaxNew(maxNew, regime.regime, regimeFilterMode)
      : { adjusted: 0, throttled: maxNew > 0, mode: "strict" as const };
    const effectiveMaxNew = regimeAdj.adjusted;
    await appendRunProgress(
      runId,
      "regime",
      `${regime.summary} · filter=${regimeAdj.mode}`,
      regimeAdj.throttled
        ? `Throttling new buys this run (${maxNew} → ${effectiveMaxNew}) due to ${regime.regime} regime in ${regimeAdj.mode} mode. Adjust in Settings → Regime filter mode.`
        : null,
    );

    const prevSnap = await findPreviousPortfolioSnapshotForPnl(userId);
    const realizedPnlTotal =
      toNum(prevSnap?.realizedPnl as Parameters<typeof toNum>[0] | undefined) + realizedPnlThisRun;

    const openAfterSell = await prisma.paperPosition.findMany({
      where: { userId, isOpen: true },
    });
    const heldIds = new Set(openAfterSell.map((p) => p.symbolId));

    let invested = 0;
    for (const p of openAfterSell) {
      const px = priceBySymbol.get(p.symbolId) ?? 0;
      invested += signedExposureMarketValue(toNum(p.quantity), px, p.isShort);
    }
    const portVal = cash + invested;

    await appendRunProgress(
      runId,
      "buys",
      `After sells: cash $${cash.toFixed(2)} · evaluating buys (reserve ${reservePct}%)…`,
    );

    const candidates: {
      symbolId: string;
      ticker: string;
      segmentKey: string | null;
      buyScore: number;
      sellRiskScore: number;
      confidence: number;
      price: number;
      vol20: number;
      breakdown: ScoreBreakdown;
      policyNote: string | null;
    }[] = [];
    let skippedBuy = 0;

    for (const s of symbols) {
      if (heldIds.has(s.id)) {
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "skipped_buy",
          rejectionReason: "already_held",
        });
        continue;
      }
      const px = priceBySymbol.get(s.id);
      if (px == null) {
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "skipped_buy",
          rejectionReason: "missing_price",
        });
        continue;
      }
      const bars = barsBySymbol.get(s.id);
      if (!bars) {
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "skipped_buy",
          rejectionReason: "MISSING_BARS",
        });
        continue;
      }
      const { features } = computeFeatures(bars);
      const scores = strategyScores(strategyMode, features);
      const universePolicy = applyLongUniversePolicy({
        ticker: s.ticker,
        segmentKey: s.segmentKey ?? null,
        regime: regime.regime,
        buyScore: scores.buyScore,
      });

      const cooldownCutoff = new Date(Date.now() - cooldownHrs * 3600000);
      const recentSell = await findRecentSellInCooldownWindow(userId, s.id, cooldownCutoff);

      const avgDollarVolume = computeAvgDollarVolume(bars, 20);

      const avail = cash - (portVal * reservePct) / 100;
      if (universePolicy.blocked) {
        skippedBuy++;
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "skipped_buy",
          buyScore: universePolicy.adjustedBuyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          rejectionReason: universePolicy.blockedReason,
        });
        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: s.id,
            actionRecommendation: "skip",
            blocked: true,
            blockedReason: universePolicy.blockedReason,
            buyScore: universePolicy.adjustedBuyScore,
            sellRiskScore: scores.sellRiskScore,
            confidenceScore: scores.confidenceScore,
            rationaleShort: `${universePolicy.note ?? "Blocked by universe policy"}. ${scores.breakdown.featureSummary}`,
          },
        });
        continue;
      }
      const block = evaluateBuyBlock({
        cash,
        portfolioValue: portVal,
        availableForTrade: avail,
        cashReservePct: reservePct,
        minConfidence: minConf + confidenceMarginForBuy,
        buyScore: universePolicy.adjustedBuyScore,
        buyScoreThreshold: buyTh + buyScoreMargin,
        confidenceScore: scores.confidenceScore,
        alreadyHeld: false,
        features,
        maxVolatility: maxBuyAnnualVol,
        maxDistFromMean: 0.15,
        onCooldown: recentSell != null,
        avgDollarVolume,
        minDollarVolume,
        requirePositiveMomentum: settings.requireMomentumForBuy,
      });

      if (block.blocked) {
        skippedBuy++;
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "skipped_buy",
          buyScore: universePolicy.adjustedBuyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          rejectionReason: block.reason,
        });
        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: s.id,
            actionRecommendation: "skip",
            blocked: true,
            blockedReason: block.reason,
            buyScore: universePolicy.adjustedBuyScore,
            sellRiskScore: scores.sellRiskScore,
            confidenceScore: scores.confidenceScore,
            rationaleShort: `${block.detail}. ${scores.breakdown.featureSummary}${universePolicy.note ? ` | Policy: ${universePolicy.note}` : ""}`,
          },
        });
        continue;
      }

      candidates.push({
        symbolId: s.id,
        ticker: s.ticker,
        segmentKey: s.segmentKey ?? null,
        buyScore: universePolicy.adjustedBuyScore,
        sellRiskScore: scores.sellRiskScore,
        confidence: scores.confidenceScore,
        price: px,
        vol20: features.vol20,
        breakdown: scores.breakdown,
        policyNote: universePolicy.note,
      });
    }

    await appendRunProgress(
      runId,
      "buys",
      `${candidates.length} symbol(s) passed buy filter · ${skippedBuy} skipped (rules)`,
    );

    candidates.sort((a, b) => b.buyScore - a.buyScore);
    const rankedBuyCandidates = candidates.length;
    let buysThisRun = 0;
    let replacementsThisRun = 0;
    const targetCount = settings.targetHoldings;
    const boughtIds = new Set<string>();
    const rotatedOutIds = new Set<string>();
    let buyLoopExit: { reason: string; startIdx: number } | null = null;

    for (let ri = 0; ri < candidates.length; ri++) {
      const c = candidates[ri];
      const buyRank = ri + 1;

      if (buysThisRun >= effectiveMaxNew) {
        buyLoopExit = { reason: "max_new_positions", startIdx: ri };
        break;
      }
      const openCount = await prisma.paperPosition.count({ where: { userId, isOpen: true } });
      if (openCount >= targetCount) {
        if (replacementsThisRun >= rotationMaxReplacementsPerRun) {
          buyLoopExit = { reason: "target_holdings_cap", startIdx: ri };
          break;
        }

        const rotationTarget = pickRotationTarget({
          candidate: {
            symbolId: c.symbolId,
            ticker: c.ticker,
            segmentKey: c.segmentKey,
            buyScore: c.buyScore,
            sellRiskScore: c.sellRiskScore,
            confidenceScore: c.confidence,
          },
          holdings: rotationPool.filter((h) => !rotatedOutIds.has(h.symbolId)),
          minBuyScoreEdge: rotationMinBuyScoreEdge,
          weakHoldMaxBuyScore: rotationWeakHoldMaxBuyScore,
          minHeldSellRisk: rotationMinHeldSellRisk,
          maxCandidateSellRiskSpread: rotationMaxCandidateSellRiskSpread,
        });

        if (!rotationTarget) {
          buyLoopExit = { reason: "target_holdings_cap", startIdx: ri };
          break;
        }

        const rotationExec = applySlippage(rotationTarget.currentPrice, "SELL", slippage);
        const rotationGross = rotationTarget.quantity * rotationExec;
        const rotationFees = 0;
        realizedPnlThisRun += rotationTarget.quantity * (rotationExec - rotationTarget.avgCost);
        const rotationCashBefore = cash;
        cash = rotationCashBefore + rotationGross - rotationFees;

        const rotationReasonText =
          `Rotation: replace ${rotationTarget.ticker} with ${c.ticker}. ` +
          `Held buy ${rotationTarget.buyScore}/sellRisk ${rotationTarget.sellRiskScore}; ` +
          `candidate buy ${c.buyScore}/sellRisk ${c.sellRiskScore}.`;
        await prisma.paperTrade.create({
          data: {
            userId,
            symbolId: rotationTarget.symbolId,
            decisionRunId: runId,
            action: "SELL",
            quantity: rotationTarget.quantity,
            price: rotationExec,
            slippagePct: slippage,
            fees: rotationFees,
            grossAmount: rotationGross,
            reasonCode: "rebalance",
            reasonText: rotationReasonText,
            modelVersion: strategyModelVersion,
            confidenceScore: rotationTarget.confidenceScore,
            cashBefore: rotationCashBefore,
            cashAfter: cash,
            expectedHorizon: "5d",
          },
        });
        recordAuditFill(audit, {
          action: "SELL",
          ticker: rotationTarget.ticker,
          quantity: rotationTarget.quantity,
          rawPrice: rotationTarget.currentPrice,
          fillPrice: rotationExec,
          slippagePct: slippage,
          cashBefore: rotationCashBefore,
          cashAfter: cash,
          reasonCode: "rebalance",
          reasonText: rotationReasonText,
        });

        await prisma.paperPosition.update({
          where: { id: rotationTarget.positionId },
          data: { isOpen: false, quantity: 0, isShort: false, lastUpdatedAt: new Date() },
        });

        await prisma.decisionRunItem.deleteMany({
          where: {
            decisionRunId: runId,
            symbolId: rotationTarget.symbolId,
            actionRecommendation: "hold",
          },
        });
        await prisma.decisionRun.update({
          where: { id: runId },
          data: { sellsCount: { increment: 1 } },
        });
        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: rotationTarget.symbolId,
            actionRecommendation: "sell",
            blocked: false,
            buyScore: rotationTarget.buyScore,
            sellRiskScore: rotationTarget.sellRiskScore,
            confidenceScore: rotationTarget.confidenceScore,
            rationaleShort:
              `${rotationReasonText} ${rotationTarget.breakdown.featureSummary}. ` +
              `Sell risk: ${rotationTarget.breakdown.sellRiskFactors.join("; ")}`,
          },
        });
        mergeExplorer(explorer, rotationTarget.symbolId, {
          ticker: rotationTarget.ticker,
          segmentKey: rotationTarget.segmentKey,
          status: "rotated_out",
          buyScore: rotationTarget.buyScore,
          sellRiskScore: rotationTarget.sellRiskScore,
          confidenceScore: rotationTarget.confidenceScore,
          currentPrice: rotationTarget.currentPrice,
          rejectionReason: "rotation_replaced",
        });
        await appendRunProgress(
          runId,
          "sell",
          `ROTATE OUT ${rotationTarget.ticker} × ${rotationTarget.quantity} @ ${rotationExec.toFixed(4)}`,
          `Replaced by ${c.ticker} (buy ${c.buyScore} vs held ${rotationTarget.buyScore}).`,
        );
        rotatedOutIds.add(rotationTarget.symbolId);
        replacementsThisRun++;
      }

      const execPx = applySlippage(c.price, "BUY", slippage);
      const maxPositionDollars = (portVal * maxPosPct) / 100;
      const baseTarget = Math.min(portVal * 0.08, cash * 0.33);
      const sizeMult = volTargetSizeMultiplier(c.vol20, volTargetAnnualized);
      const targetFromFormula = baseTarget * sizeMult;
      const minCashReserve = (portVal * reservePct) / 100;
      const dollars = Math.min(maxPositionDollars, targetFromFormula, Math.max(0, cash - minCashReserve));
      const qty = wholeShares(dollars, execPx);
      if (qty <= 0) {
        buyLoopExit = { reason: "position_below_min_lot", startIdx: ri };
        break;
      }

      const gross = qty * execPx;
      const fees = 0;
      if (gross > cash - minCashReserve) {
        mergeExplorer(explorer, c.symbolId, {
          ticker: c.ticker,
          segmentKey: c.segmentKey,
          status: "skipped_buy",
          buyRank,
          buyScore: c.buyScore,
          sellRiskScore: c.sellRiskScore,
          confidenceScore: c.confidence,
          currentPrice: c.price,
          rejectionReason: "insufficient_cash",
        });
        continue;
      }

      const cashBefore = cash;
      cash = cashBefore - gross - fees;

      const buyReasonText = `Buy score ${c.buyScore}/100 (conf ${c.confidence}). ${c.breakdown.featureSummary}. Factors: ${c.breakdown.buyFactors.join("; ")}${c.policyNote ? `. Policy: ${c.policyNote}` : ""}`;
      await prisma.paperTrade.create({
        data: {
          userId,
          symbolId: c.symbolId,
          decisionRunId: runId,
          action: "BUY",
          quantity: qty,
          price: execPx,
          slippagePct: slippage,
          fees,
          grossAmount: gross,
          reasonCode: "buy_rank",
          reasonText: buyReasonText,
          modelVersion: strategyModelVersion,
          confidenceScore: c.confidence,
          cashBefore,
          cashAfter: cash,
          expectedHorizon: "5d",
        },
      });
      recordAuditFill(audit, {
        action: "BUY",
        ticker: c.ticker,
        quantity: qty,
        rawPrice: c.price,
        fillPrice: execPx,
        slippagePct: slippage,
        cashBefore,
        cashAfter: cash,
        reasonCode: "buy_rank",
        reasonText: buyReasonText,
      });

      const posNote = `buy=${c.buyScore} conf=${c.confidence} | ${c.breakdown.featureSummary}`;
      const existingPos = await prisma.paperPosition.findUnique({
        where: { userId_symbolId: { userId, symbolId: c.symbolId } },
      });
      if (existingPos?.isOpen) {
        /* already held — should not occur */
      } else if (existingPos && !existingPos.isOpen) {
        await prisma.paperPosition.update({
          where: { id: existingPos.id },
          data: {
            quantity: qty,
            avgCost: execPx,
            isOpen: true,
            isShort: false,
            openedAt: new Date(),
            lastAgentNote: posNote,
          },
        });
      } else {
        await prisma.paperPosition.create({
          data: {
            userId,
            symbolId: c.symbolId,
            quantity: qty,
            avgCost: execPx,
            isOpen: true,
            isShort: false,
            lastAgentNote: posNote,
          },
        });
      }

      buysThisRun++;
      boughtIds.add(c.symbolId);
      mergeExplorer(explorer, c.symbolId, {
        ticker: c.ticker,
        segmentKey: c.segmentKey,
        status: "bought",
        buyRank,
        buyScore: c.buyScore,
        sellRiskScore: c.sellRiskScore,
        confidenceScore: c.confidence,
        currentPrice: c.price,
        rejectionReason: null,
      });

      await prisma.decisionRun.update({
        where: { id: runId },
        data: { buysCount: { increment: 1 } },
      });

      const buyRationale = `${c.breakdown.featureSummary}. Buy: ${c.breakdown.buyFactors.join("; ")}. Conf: ${c.breakdown.confidenceFactors.join("; ")}${c.policyNote ? `. Policy: ${c.policyNote}` : ""}`;
      await prisma.decisionRunItem.create({
        data: {
          decisionRunId: runId,
          symbolId: c.symbolId,
          actionRecommendation: "buy",
          rank: buysThisRun,
          blocked: false,
          buyScore: c.buyScore,
          confidenceScore: c.confidence,
          rationaleShort: buyRationale,
        },
      });

      await appendRunProgress(
        runId,
        "buy",
        `BUY ${c.ticker} × ${qty} @ ${execPx.toFixed(4)} — score ${c.buyScore}, conf ${c.confidence}`,
        `${c.breakdown.featureSummary} | ${c.breakdown.buyFactors.filter(f => !f.startsWith("+0")).join("; ")}${c.policyNote ? ` | ${c.policyNote}` : ""}`,
      );
    }

    if (buyLoopExit) {
      for (let j = buyLoopExit.startIdx; j < candidates.length; j++) {
        const c = candidates[j];
        if (boughtIds.has(c.symbolId)) continue;
        mergeExplorer(explorer, c.symbolId, {
          ticker: c.ticker,
          segmentKey: c.segmentKey,
          status: "skipped_buy",
          buyRank: j + 1,
          buyScore: c.buyScore,
          sellRiskScore: c.sellRiskScore,
          confidenceScore: c.confidence,
          currentPrice: c.price,
          rejectionReason: buyLoopExit.reason,
        });
      }
    }

    await appendRunProgress(
      runId,
      "shorts",
      settings.shortingEnabled
        ? `Shorting on · regime gate=${shortOnlyInBearRegime ? "bearish SPY only" : "off"} · max ${maxShortPositionsPerRun}/run`
        : "Shorting disabled (settings)",
    );

    const openForShortPhase = await prisma.paperPosition.findMany({
      where: { userId, isOpen: true },
    });
    const heldShortIds = new Set(openForShortPhase.map((p) => p.symbolId));

    let netExposureShortPhase = 0;
    for (const p of openForShortPhase) {
      const px = priceBySymbol.get(p.symbolId) ?? toNum(p.avgCost);
      netExposureShortPhase += signedExposureMarketValue(toNum(p.quantity), px, p.isShort);
    }
    let portValShortPhase = cash + netExposureShortPhase;

    const shortCandidates: {
      symbolId: string;
      ticker: string;
      segmentKey: string | null;
      bearScore: number;
      confidence: number;
      sellRiskScore: number;
      price: number;
      vol20: number;
      bearBreakdown: BearScoreBreakdown;
      scoreBreakdown: ScoreBreakdown;
    }[] = [];
    let skippedShortRules = 0;

    for (const s of symbols) {
      if (heldShortIds.has(s.id)) continue;
      const px = priceBySymbol.get(s.id);
      if (px == null) continue;

      const bars = barsBySymbol.get(s.id);
      if (!bars) continue;
      const { features } = computeFeatures(bars);
      const scores = strategyScores(strategyMode, features);
      const bs = bearScores(features);

      const cooldownCutoffShort = new Date(Date.now() - cooldownHrs * 3600000);
      const recentCover = await findRecentCoverInCooldownWindow(userId, s.id, cooldownCutoffShort);
      const avgDollarVolumeS = computeAvgDollarVolume(bars, 20);

      const sb = evaluateShortBlock({
        shortingEnabled: settings.shortingEnabled,
        regimeAllowsShort,
        bearScore: bs.bearScore,
        bearScoreThreshold,
        confidenceScore: scores.confidenceScore,
        minConfidenceEffective: minConf + confidenceMarginForShort,
        features,
        maxVolatility: maxBuyAnnualVol,
        minDistSma20Floor: -0.14,
        maxDistSma20Ceiling: 0.18,
        onCooldown: recentCover != null,
        avgDollarVolume: avgDollarVolumeS,
        minDollarVolume,
      });

      if (sb.blocked) {
        skippedShortRules++;
        mergeExplorer(explorer, s.id, {
          ticker: s.ticker,
          segmentKey: s.segmentKey ?? null,
          status: "skipped_short",
          buyScore: scores.buyScore,
          sellRiskScore: scores.sellRiskScore,
          confidenceScore: scores.confidenceScore,
          rejectionReason: sb.reason,
        });
        await prisma.decisionRunItem.create({
          data: {
            decisionRunId: runId,
            symbolId: s.id,
            actionRecommendation: "skip",
            blocked: true,
            blockedReason: sb.reason,
            buyScore: scores.buyScore,
            sellRiskScore: scores.sellRiskScore,
            confidenceScore: scores.confidenceScore,
            rationaleShort: `${sb.detail}. ${bs.breakdown.featureSummary}`,
          },
        });
        continue;
      }

      shortCandidates.push({
        symbolId: s.id,
        ticker: s.ticker,
        segmentKey: s.segmentKey ?? null,
        bearScore: bs.bearScore,
        confidence: scores.confidenceScore,
        sellRiskScore: scores.sellRiskScore,
        price: px,
        vol20: features.vol20,
        bearBreakdown: bs.breakdown,
        scoreBreakdown: scores.breakdown,
      });
    }

    shortCandidates.sort((a, b) => b.bearScore - a.bearScore);
    let shortsThisRun = 0;
    const shortedIds = new Set<string>();

    for (let si = 0; si < shortCandidates.length; si++) {
      const c = shortCandidates[si];
      const shortRank = si + 1;

      if (shortsThisRun >= maxShortPositionsPerRun) break;

      const clashOpen = await prisma.paperPosition.findFirst({
        where: { userId, symbolId: c.symbolId, isOpen: true },
      });
      if (clashOpen) continue;

      const openCtShort = await prisma.paperPosition.count({ where: { userId, isOpen: true } });
      if (openCtShort >= targetCount) break;

      const execPx = applySlippage(c.price, "SELL", slippage);
      const maxPositionDollars = (portValShortPhase * maxPosPct) / 100;
      const baseTarget = Math.min(portValShortPhase * 0.06, cash * 0.25);
      const sizeMult = volTargetSizeMultiplier(c.vol20, volTargetAnnualized);
      const targetFromFormula = baseTarget * sizeMult;
      const minCashReserve = (portValShortPhase * reservePct) / 100;
      const dollars = Math.min(maxPositionDollars, targetFromFormula, Math.max(0, cash - minCashReserve));
      const qty = wholeShares(dollars, execPx);
      if (qty <= 0) break;

      const gross = qty * execPx;
      const fees = 0;
      const cashBefore = cash;
      cash = cashBefore + gross - fees;

      const shortReasonText = `Bear score ${c.bearScore}/100 (conf ${c.confidence}). ${c.bearBreakdown.featureSummary}. Factors: ${c.bearBreakdown.bearFactors.join("; ")}`;
      await prisma.paperTrade.create({
        data: {
          userId,
          symbolId: c.symbolId,
          decisionRunId: runId,
          action: "SHORT",
          quantity: qty,
          price: execPx,
          slippagePct: slippage,
          fees,
          grossAmount: gross,
          reasonCode: "bear_rank",
          reasonText: shortReasonText,
          modelVersion: strategyModelVersion,
          confidenceScore: c.confidence,
          cashBefore,
          cashAfter: cash,
          expectedHorizon: "5d",
        },
      });
      recordAuditFill(audit, {
        action: "SHORT",
        ticker: c.ticker,
        quantity: qty,
        rawPrice: c.price,
        fillPrice: execPx,
        slippagePct: slippage,
        cashBefore,
        cashAfter: cash,
        reasonCode: "bear_rank",
        reasonText: shortReasonText,
      });

      const posNoteShort = `short bear=${c.bearScore} conf=${c.confidence} | ${c.scoreBreakdown.featureSummary}`;
      const existingPosS = await prisma.paperPosition.findUnique({
        where: { userId_symbolId: { userId, symbolId: c.symbolId } },
      });
      if (existingPosS && !existingPosS.isOpen) {
        await prisma.paperPosition.update({
          where: { id: existingPosS.id },
          data: {
            quantity: qty,
            avgCost: execPx,
            isOpen: true,
            isShort: true,
            openedAt: new Date(),
            lastAgentNote: posNoteShort,
          },
        });
      } else if (!existingPosS) {
        await prisma.paperPosition.create({
          data: {
            userId,
            symbolId: c.symbolId,
            quantity: qty,
            avgCost: execPx,
            isOpen: true,
            isShort: true,
            lastAgentNote: posNoteShort,
          },
        });
      }

      shortsThisRun++;
      shortedIds.add(c.symbolId);
      heldShortIds.add(c.symbolId);

      netExposureShortPhase += signedExposureMarketValue(qty, c.price, true);
      portValShortPhase = cash + netExposureShortPhase;

      mergeExplorer(explorer, c.symbolId, {
        ticker: c.ticker,
        segmentKey: c.segmentKey,
        status: "shorted",
        buyRank: shortRank,
        buyScore: null,
        sellRiskScore: c.sellRiskScore,
        confidenceScore: c.confidence,
        currentPrice: c.price,
        rejectionReason: null,
      });

      await prisma.decisionRunItem.create({
        data: {
          decisionRunId: runId,
          symbolId: c.symbolId,
          actionRecommendation: "short",
          rank: shortsThisRun,
          blocked: false,
          buyScore: null,
          sellRiskScore: c.sellRiskScore,
          confidenceScore: c.confidence,
          rationaleShort: `${c.bearBreakdown.featureSummary}. Short: ${c.bearBreakdown.bearFactors.join("; ")}`,
        },
      });

      await appendRunProgress(
        runId,
        "short",
        `SHORT ${c.ticker} × ${qty} @ ${execPx.toFixed(4)} — bear ${c.bearScore}, conf ${c.confidence}`,
        `${c.bearBreakdown.bearFactors.filter((f) => !f.startsWith("+0")).join("; ")}`,
      );
    }

    await appendRunProgress(
      runId,
      "shorts",
      `${shortCandidates.length} passed short filter · ${skippedShortRules} skipped · opened ${shortsThisRun}`,
    );

    for (let sj = 0; sj < shortCandidates.length; sj++) {
      const c = shortCandidates[sj];
      if (shortedIds.has(c.symbolId)) continue;
      const row = explorer.get(c.symbolId);
      if (row?.status === "skipped_short") continue;
      mergeExplorer(explorer, c.symbolId, {
        ticker: c.ticker,
        segmentKey: c.segmentKey,
        status: "skipped_short",
        buyRank: sj + 1,
        buyScore: null,
        sellRiskScore: c.sellRiskScore,
        confidenceScore: c.confidence,
        currentPrice: c.price,
        rejectionReason: "ranked_not_executed",
      });
    }

    const candidateIdSet = new Set(candidates.map((c) => c.symbolId));

    for (let ci = 0; ci < candidates.length; ci++) {
      const c = candidates[ci];
      if (boughtIds.has(c.symbolId)) continue;
      const row = explorer.get(c.symbolId);
      if (row?.status === "skipped_buy" && row.rejectionReason) continue;
      mergeExplorer(explorer, c.symbolId, {
        ticker: c.ticker,
        segmentKey: c.segmentKey,
        status: "skipped_buy",
        buyRank: ci + 1,
        buyScore: c.buyScore,
        sellRiskScore: c.sellRiskScore,
        confidenceScore: c.confidence,
        currentPrice: c.price,
        rejectionReason: "ranked_not_executed",
      });
    }

    for (const [symId, row] of explorer) {
      if (row.status !== "scored") continue;
      if (candidateIdSet.has(symId)) continue;
      mergeExplorer(explorer, symId, {
        ticker: row.ticker,
        segmentKey: row.segmentKey,
        status: "skipped_buy",
        rejectionReason: "not_evaluated",
      });
    }

    const finalPositions = await prisma.paperPosition.findMany({
      where: { userId, isOpen: true },
      include: { symbol: true },
    });
    for (const p of finalPositions) {
      await ensureHeldSymbolPricing(p, priceBySymbol, trendBySymbolId, useMock, apiKey, barsBySymbol);
    }
    const quoteFreshPost = await applyLiveQuotesForHoldings(
      finalPositions,
      priceBySymbol,
      useMock,
      apiKey,
      runId,
      userId,
      true,
    );
    await syncPaperQuoteFields(userId, finalPositions, quoteFreshPost);
    await persistPositionValuationRound(userId, runId, finalPositions, priceBySymbol, quoteFreshPost);

    const quoteMarkAt = new Date();
    if (!useMock && finalPositions.length > 0) {
      const quoteRows = finalPositions
        .map((p) => {
          const px = priceBySymbol.get(p.symbolId);
          if (px == null || !Number.isFinite(px)) return null;
          return {
            symbolId: p.symbolId,
            timestamp: quoteMarkAt,
            open: px,
            high: px,
            low: px,
            close: px,
            volume: null as null,
            source: "twelvedata-quote",
            interval: "quote",
          };
        })
        .filter((r): r is NonNullable<typeof r> => r != null);
      if (quoteRows.length > 0) {
        await createMarketSnapshotsMany(quoteRows);
      }
    }

    let investedAfter = 0;
    let unrealized = 0;
    let netExposureAfter = 0;
    for (const p of finalPositions) {
      const px = priceBySymbol.get(p.symbolId) ?? toNum(p.avgCost);
      const qty = toNum(p.quantity);
      const avg = toNum(p.avgCost);
      investedAfter += grossNotional(qty, px);
      netExposureAfter += signedExposureMarketValue(qty, px, p.isShort);
      unrealized += unrealizedPnlPosition(qty, avg, px, p.isShort);
    }
    const totalAfter = cash + netExposureAfter;

    const spyStart = spyBars[0]?.close ?? 1;
    const spyEnd = spyBars[spyBars.length - 1]?.close ?? 1;
    const benchVal = starting * (spyEnd / spyStart);

    const afterHoldings = buildHoldingsMarkPayload(finalPositions, priceBySymbol, trendBySymbolId);
    await appendHoldingsReview(
      runId,
      "after",
      finalPositions.length === 0
        ? "Holdings after run: no open positions"
        : `Holdings (${finalPositions.length}) after this run: value, unrealized P&L, and price trends`,
      finalPositions.length === 0
        ? [{ message: "All cash — no positions held.", detail: null }]
        : afterHoldings.lines,
      afterHoldings.entries,
    );

    const recordedAt = new Date();
    if (afterHoldings.entries.length > 0) {
      await prisma.$executeRaw`
        INSERT INTO "HoldingValueLog" (id, "userId", "symbolId", "decisionRunId", "recordedAt", quantity, price, "marketValue")
        VALUES ${Prisma.join(
          afterHoldings.entries.map((e) =>
            Prisma.sql`(${randomUUID()}, ${userId}, ${e.symbolId}, ${runId}, ${recordedAt}, ${e.quantity}, ${e.lastPrice}, ${e.marketValue})`,
          ),
          ", ",
        )}
      `;
    }

    const uSign = unrealized >= 0 ? "+" : "";
    await appendRunProgress(
      runId,
      "snapshot",
      `Portfolio snapshot · total ~$${totalAfter.toFixed(2)} · invested ~$${investedAfter.toFixed(2)} · unrealized P&L ${uSign}$${Math.abs(unrealized).toFixed(2)} · SPY benchmark ~$${benchVal.toFixed(2)}`,
    );

    await prisma.portfolioSnapshot.create({
      data: {
        userId,
        cash,
        investedValue: investedAfter,
        totalValue: totalAfter,
        unrealizedPnl: unrealized,
        realizedPnl: realizedPnlTotal,
        benchmarkValue: benchVal,
      },
    });

    await persistExplorerRows(runId, explorer);

    const segmentsMeta = await fetchEnabledSegmentsMeta();
    const defaultProfile = await fetchDefaultSearchProfile(userId);
    await insertDecisionSearchSnapshotRow({
      decisionRunId: runId,
      searchProfileId: defaultProfile?.id,
      profileName: defaultProfile?.name ?? "Default",
      profileJson: defaultProfile?.profileJson ?? null,
      statsJson: JSON.stringify({
        segmentsEnabled: segmentsMeta.map((s) => s.key),
        symbolsScanned: symbols.length,
        ingested,
        skippedBuy,
        rankedBuyCandidates,
        staleQuotesPreTrade: [...quoteFreshPre.values()].filter((v) => v === "stale").length,
        staleQuotesPostTrade: [...quoteFreshPost.values()].filter((v) => v === "stale").length,
        pipeline: ["discovery", "valuation", "action", "explanation"],
      }),
      filtersJson: JSON.stringify({
        buyScoreThreshold: toNum(settings.buyScoreThreshold),
        buyScoreMargin: toNum(settings.buyScoreMargin),
        confidenceMarginForBuy: toNum(settings.confidenceMarginForBuy),
        requireMomentumForBuy: settings.requireMomentumForBuy,
        maxBuyAnnualVol: toNum(settings.maxBuyAnnualVol),
        sellRiskThreshold: toNum(settings.sellRiskThreshold),
        minConfidence: toNum(settings.minConfidence),
        staleQuoteAllowSells: settings.staleQuoteAllowSells,
        shortingEnabled: settings.shortingEnabled,
        bearScoreThreshold: toNum(settings.bearScoreThreshold),
        confidenceMarginForShort: toNum(settings.confidenceMarginForShort),
        shortOnlyInBearRegime: settings.shortOnlyInBearRegime,
        maxShortPositionsPerRun: settings.maxShortPositionsPerRun,
        buyScoreCoverShortThreshold: toNum(settings.buyScoreCoverShortThreshold),
      }),
      rankingInputsJson: JSON.stringify({
        modelVersion: strategyModelVersion,
        strategyMode,
        settingsVersion: audit.settingsVersion,
        executionMode: "paper",
      }),
      candidateExplorerJson: JSON.stringify({
        note: "Full per-symbol grid: Decisions page + decision_run_item; export planned.",
      }),
    });

    const notesRow = await prisma.decisionRun.findUnique({
      where: { id: runId },
      select: { notesJson: true },
    });
    const doneNotes = parseRunNotes(notesRow?.notesJson);
    doneNotes.useMock = useMock;
    doneNotes.symbols = symbols.length;
    audit.portfolioAfter = {
      cash,
      investedValue: investedAfter,
      totalValue: totalAfter,
      unrealizedPnl: unrealized,
      realizedPnl: realizedPnlTotal,
    };
    doneNotes.audit = audit;

    await prisma.decisionRun.update({
      where: { id: runId },
      data: {
        status: "completed",
        finishedAt: new Date(),
        portfolioValueAfter: totalAfter,
        notesJson: JSON.stringify(doneNotes),
      },
    });

    await appendRunProgress(runId, "done", "Run completed — generating summary…");

    await writeDecisionExplainerSummary(runId).catch(() => {
      /* explainer is best-effort */
    });

    await appendRunProgress(runId, "done", "All steps finished.");
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    await appendRunProgress(runId, "error", "Run failed", msg);
    const failRow = await prisma.decisionRun.findUnique({
      where: { id: runId },
      select: { notesJson: true },
    });
    const failNotes = parseRunNotes(failRow?.notesJson);
    failNotes.error = String(e);
    await prisma.decisionRun.update({
      where: { id: runId },
      data: {
        status: "failed",
        finishedAt: new Date(),
        notesJson: JSON.stringify(failNotes),
      },
    });
    throw e;
  }
}

export async function runHourlyMarketAgent(
  userId: string,
  options?: {
    trigger?: RunAgentTrigger;
    wait?: boolean;
    /**
     * When `wait` is false, run the pipeline after the HTTP response is sent (e.g. Next.js `after`
     * from `next/server`). Without this, serverless hosts often freeze the isolate as soon as the
     * route returns and the agent never finishes—no progress, no trades, no holding marks.
     */
    scheduleAfter?: (task: () => void | Promise<void>) => void;
    /**
     * Strategy Upgrade §3.3 — persisted on `DecisionRun.triggerSource`. The legacy
     * `trigger` arg ("manual" | "hourly") still drives idempotency-key bucketing, but the
     * persisted column carries richer source info (manual / scheduled / retry / research / shadow / backtest).
     */
    triggerSource?: string;
    runMode?: string;
    scheduleId?: string | null;
    lockId?: string | null;
    strategyVersionId?: string | null;
    searchProfileId?: string | null;
    /** Override the idempotency key (e.g. scheduler-tick uses `${userId}:${scheduleId}:${hourBucket}`). */
    idempotencyKey?: string;
    /** Notify the caller as soon as a DecisionRun row exists (used by the lock to record runId). */
    onRunCreated?: (runId: string) => void | Promise<void>;
  },
): Promise<{ runId: string; status: string }> {
  const trigger = options?.trigger ?? "hourly";
  const wait = options?.wait ?? true;
  const triggerSource = options?.triggerSource ?? (trigger === "manual" ? "manual" : "scheduled");
  const runMode = options?.runMode ?? "paper_trade";

  const settings = await prisma.appSettings.findUnique({ where: { userId } });
  if (!settings) throw new Error("No app settings for user");

  const admission = admitPaperAgentRun({ env: process.env, settings });
  if (!admission.allowed) {
    const blockedNotes = JSON.stringify({
      progress: [],
      error: admission.detail,
      admission: { reason: admission.reason, status: admission.status },
    });
    const existingBlocked = options?.idempotencyKey
      ? await prisma.decisionRun.findUnique({ where: { idempotencyKey: options.idempotencyKey } })
      : null;
    if (existingBlocked) {
      await prisma.decisionRun.update({
        where: { id: existingBlocked.id },
        data: {
          status: admission.status === "blocked_execution_mode" ? "failed" : "skipped",
          finishedAt: new Date(),
          notesJson: blockedNotes,
        },
      });
      return { runId: existingBlocked.id, status: admission.status };
    }
    const created = await prisma.decisionRun.create({
      data: {
        userId,
        status: admission.status === "blocked_execution_mode" ? "failed" : "skipped",
        universeSize: 0,
        triggerSource,
        runMode,
        notesJson: blockedNotes,
      },
    });
    return { runId: created.id, status: admission.status };
  }

  const defaultIdemKey =
    trigger === "manual"
      ? `manual-${userId}-${Date.now()}`
      : options?.scheduleId
        ? `${userId}:${options.scheduleId}:${hourBucketKey(new Date())}`
        : `${userId}-${hourBucketKey(new Date())}`;
  const idempotencyKey = options?.idempotencyKey ?? defaultIdemKey;

  {
    const existing = await prisma.decisionRun.findUnique({ where: { idempotencyKey } });
    if (shouldSkipDuplicateHourlyRun(existing, trigger)) {
      return { runId: existing!.id, status: "skipped_duplicate" };
    }
  }

  const apiKey = process.env.TWELVE_DATA_API_KEY ?? "";
  const useMock = process.env.USE_MOCK_MARKET_DATA === "true" || !apiKey;
  const symbols = await getTradableSymbols();
  const starting = toNum(settings.startingCash);

  let run = await prisma.decisionRun.findUnique({ where: { idempotencyKey } });
  if (!run) {
    run = await prisma.decisionRun.create({
      data: {
        userId,
        idempotencyKey,
        status: "running",
        universeSize: symbols.length,
        notesJson: JSON.stringify({ progress: [] }),
        triggerSource,
        runMode,
        scheduleId: options?.scheduleId ?? null,
        lockId: options?.lockId ?? null,
        strategyVersionId: options?.strategyVersionId ?? null,
        searchProfileId: options?.searchProfileId ?? null,
      },
    });
  } else {
    run = await prisma.decisionRun.update({
      where: { id: run.id },
      data: {
        status: "running",
        startedAt: new Date(),
        notesJson: JSON.stringify({ progress: [] }),
        triggerSource,
        runMode,
        scheduleId: options?.scheduleId ?? run.scheduleId ?? null,
        lockId: options?.lockId ?? run.lockId ?? null,
        strategyVersionId: options?.strategyVersionId ?? run.strategyVersionId ?? null,
        searchProfileId: options?.searchProfileId ?? run.searchProfileId ?? null,
      },
    });
  }

  if (options?.onRunCreated) {
    await Promise.resolve(options.onRunCreated(run.id)).catch(() => {
      /* lock-id update is best-effort. */
    });
  }

  await appendRunProgress(
    run.id,
    "start",
    trigger === "manual" ? "Manual run started" : "Scheduled hourly run started",
    useMock
      ? "Mock/synthetic data (set TWELVE_DATA_API_KEY for live prices). Without it, holdings use deterministic fake bars — the same notional price every run, so marks and per-run chart points stay flat."
      : "Twelve Data (free-tier friendly): ~7.5s between API calls by default, universe capped at 28 symbols (holdings scanned first). Set TWELVE_DATA_MIN_GAP_MS=0 and INVESTBEST_MAX_UNIVERSE_SYMBOLS=0 if your plan allows higher throughput.",
  );

  const pipeline = () =>
    hourlyMarketAgentPipeline(userId, run!.id, settings, symbols, starting, useMock, apiKey);

  if (!wait) {
    const runPipeline = () => pipeline().catch((err) => console.error("[hourlyMarketAgent]", err));
    if (options?.scheduleAfter) {
      options.scheduleAfter(runPipeline);
    } else {
      void runPipeline();
    }
    return { runId: run.id, status: "started" };
  }

  await pipeline();
  return { runId: run.id, status: "completed" };
}
