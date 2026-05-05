import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";

export type PositionValuePoint = { t: string; value: number };

export type PositionHistoryExtras = {
  valueHistory: PositionValuePoint[];
  costBasisValue: number;
  /** vs prior run log if present, else vs last daily bar (null if no history). */
  vsLastSnapshotPct: number | null;
  /** Run-to-run if we have ≥2 logs; else day-over-day from daily bars. */
  dayOverDayPct: number | null;
};

export type HoldingValueLogRow = {
  symbolId: string;
  recordedAt: Date;
  marketValue: number;
};

function utcDayKey(d: Date): string {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

/**
 * Dedupe multiple agent runs per day: keep the latest snapshot per UTC calendar day.
 */
export function dedupeDailyCloses(
  rows: { timestamp: Date; close: number }[],
): { timestamp: Date; close: number }[] {
  const byDay = new Map<string, { timestamp: Date; close: number }>();
  for (const row of rows) {
    const key = utcDayKey(row.timestamp);
    const prev = byDay.get(key);
    if (!prev || row.timestamp.getTime() >= prev.timestamp.getTime()) {
      byDay.set(key, { timestamp: row.timestamp, close: row.close });
    }
  }
  return [...byDay.values()].sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());
}

export function buildPositionValueHistory(
  symbolId: string,
  openedAt: Date,
  quantity: number,
  avgCost: number,
  currentPrice: number,
  runLogs: HoldingValueLogRow[],
  snapshots: { symbolId: string; timestamp: Date; close: { toString(): string } }[],
): PositionHistoryExtras {
  const costBasisValue = quantity * avgCost;
  const currentMv = quantity * currentPrice;

  const logs = runLogs
    .filter((l) => l.symbolId === symbolId && l.recordedAt >= openedAt)
    .sort((a, b) => a.recordedAt.getTime() - b.recordedAt.getTime());

  if (logs.length > 0) {
    const valueHistory: PositionValuePoint[] = [{ t: openedAt.toISOString(), value: costBasisValue }];
    for (const l of logs) {
      valueHistory.push({ t: l.recordedAt.toISOString(), value: l.marketValue });
    }
    valueHistory.push({ t: new Date().toISOString(), value: currentMv });

    const lastLogMv = logs[logs.length - 1]!.marketValue;
    const vsLastSnapshotPct =
      lastLogMv > 0 ? ((currentMv / lastLogMv - 1) * 100) : null;

    let dayOverDayPct: number | null = null;
    if (logs.length >= 2) {
      const a = logs[logs.length - 2]!.marketValue;
      const b = logs[logs.length - 1]!.marketValue;
      if (a > 0) dayOverDayPct = ((b / a - 1) * 100);
    }

    return { valueHistory, costBasisValue, vsLastSnapshotPct, dayOverDayPct };
  }

  const raw = snapshots
    .filter((s) => s.symbolId === symbolId && s.timestamp >= openedAt)
    .map((s) => ({ timestamp: s.timestamp, close: toNum(s.close) }))
    .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

  const daily = dedupeDailyCloses(raw);

  const dailyValues = daily.map((d) => ({
    t: d.timestamp.toISOString(),
    value: quantity * d.close,
  }));

  let vsLastSnapshotPct: number | null = null;
  if (dailyValues.length >= 1) {
    const lastBarMv = dailyValues[dailyValues.length - 1].value;
    if (lastBarMv > 0) vsLastSnapshotPct = ((currentMv / lastBarMv - 1) * 100);
  }

  let dayOverDayPct: number | null = null;
  if (dailyValues.length >= 2) {
    const a = dailyValues[dailyValues.length - 2].value;
    const b = dailyValues[dailyValues.length - 1].value;
    if (a > 0) dayOverDayPct = ((b / a - 1) * 100);
  }

  const valueHistory: PositionValuePoint[] = [{ t: openedAt.toISOString(), value: costBasisValue }];
  for (const dv of dailyValues) {
    valueHistory.push({ t: dv.t, value: dv.value });
  }
  valueHistory.push({ t: new Date().toISOString(), value: currentMv });

  return {
    valueHistory,
    costBasisValue,
    vsLastSnapshotPct,
    dayOverDayPct,
  };
}

export async function fetchMarketSnapshotsSince(symbolIds: string[], since: Date) {
  if (symbolIds.length === 0) return [];
  return prisma.marketSnapshot.findMany({
    where: {
      symbolId: { in: symbolIds },
      timestamp: { gte: since },
    },
    orderBy: { timestamp: "asc" },
    select: { symbolId: true, timestamp: true, close: true },
  });
}

export async function fetchHoldingValueLogs(
  userId: string,
  symbolIds: string[],
  since: Date,
): Promise<HoldingValueLogRow[]> {
  if (symbolIds.length === 0) return [];
  /** Raw SQL: Next.js can serve a cached `@prisma/client` bundle without newer model delegates (`holdingValueLog.findMany` → undefined). `$queryRaw` always exists. */
  try {
    const rows = await prisma.$queryRaw<
      { symbolId: string; recordedAt: Date; marketValue: unknown }[]
    >`
      SELECT "symbolId", "recordedAt", "marketValue"
      FROM "HoldingValueLog"
      WHERE "userId" = ${userId}
        AND "recordedAt" >= ${since}
        AND "symbolId" IN (${Prisma.join(symbolIds)})
      ORDER BY "recordedAt" ASC
    `;
    return rows.map((r) => ({
      symbolId: r.symbolId,
      recordedAt: r.recordedAt,
      marketValue: toNum(r.marketValue as { toString(): string }),
    }));
  } catch {
    return [];
  }
}
