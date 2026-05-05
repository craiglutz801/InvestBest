import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";

/**
 * Latest mark price per symbol for UI (holdings, dashboard).
 * Prefers the **newest timestamp** across `MarketSnapshot` (daily ingest) and `QuoteSnapshot`
 * (live quote from the last agent run). Previously we only read `MarketSnapshot`, so the UI
 * often showed a stale daily close even after a run had stored fresh quotes — charts looked "flat"
 * or out of date relative to what the agent just used.
 */
export async function getLatestClosesMap(symbolIds: string[]): Promise<Map<string, number>> {
  const map = new Map<string, number>();
  if (symbolIds.length === 0) return map;

  try {
    const rows = await prisma.$queryRaw<{ symbolId: string; px: unknown }[]>(
      Prisma.sql`
        SELECT DISTINCT ON (u."symbolId") u."symbolId", u.px
        FROM (
          SELECT "symbolId", "close" AS px, "timestamp" AS ts
          FROM "MarketSnapshot"
          WHERE "symbolId" IN (${Prisma.join(symbolIds.map((id) => Prisma.sql`${id}`))})
          UNION ALL
          SELECT "symbolId", "price" AS px, "timestamp" AS ts
          FROM "QuoteSnapshot"
          WHERE "symbolId" IN (${Prisma.join(symbolIds.map((id) => Prisma.sql`${id}`))})
        ) AS u
        ORDER BY u."symbolId", u.ts DESC
      `,
    );
    for (const r of rows) {
      map.set(r.symbolId, toNum(r.px as { toString(): string }));
    }
    return map;
  } catch {
    await Promise.all(
      symbolIds.map(async (symbolId) => {
        const row = await prisma.marketSnapshot.findFirst({
          where: { symbolId },
          orderBy: { timestamp: "desc" },
          select: { close: true },
        });
        if (row) map.set(symbolId, toNum(row.close));
      }),
    );
    return map;
  }
}

/** Latest model score per symbol for this run window (approx: last 2h). */
export async function getLatestModelScoresMap(symbolIds: string[], since: Date) {
  const map = new Map<
    string,
    { buy: number; sellRisk: number; conf: number; expectedReturn5d: number | null }
  >();
  await Promise.all(
    symbolIds.map(async (symbolId) => {
      const row = await prisma.modelScore.findFirst({
        where: { symbolId, timestamp: { gte: since } },
        orderBy: { timestamp: "desc" },
      });
      if (row) {
        map.set(symbolId, {
          buy: toNum(row.buyScore),
          sellRisk: toNum(row.sellRiskScore),
          conf: toNum(row.confidenceScore),
          expectedReturn5d: row.expectedReturn5d != null ? toNum(row.expectedReturn5d) : null,
        });
      }
    }),
  );
  return map;
}
