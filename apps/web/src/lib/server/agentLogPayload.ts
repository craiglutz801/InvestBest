import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";

type RunRow = {
  id: string;
  startedAt: Date;
  finishedAt: Date | null;
  status: string;
  triggerSource: string | null;
  buysCount: number;
  sellsCount: number;
  portfolioValueBefore: { toString(): string } | null;
  portfolioValueAfter: { toString(): string } | null;
};

type SnapshotRow = {
  timestamp: Date;
  cash: { toString(): string };
};

type TradeCashRow = {
  decisionRunId: string | null;
  executedAt: Date;
  cashBefore: { toString(): string } | null;
  cashAfter: { toString(): string } | null;
};

function fmtMoneyValue(v: { toString(): string } | null | undefined): number | null {
  return v == null ? null : toNum(v);
}

export async function buildAgentLogPayload(userId: string) {
  const [settings, runs, snapshots, trades] = await Promise.all([
    prisma.appSettings.findUnique({
      where: { userId },
      select: { startingCash: true },
    }),
    prisma.decisionRun.findMany({
      where: { userId },
      orderBy: { startedAt: "desc" },
      take: 200,
      select: {
        id: true,
        startedAt: true,
        finishedAt: true,
        status: true,
        triggerSource: true,
        buysCount: true,
        sellsCount: true,
        portfolioValueBefore: true,
        portfolioValueAfter: true,
      },
    }),
    prisma.portfolioSnapshot.findMany({
      where: { userId },
      orderBy: { timestamp: "asc" },
      select: {
        timestamp: true,
        cash: true,
      },
    }),
    prisma.paperTrade.findMany({
      where: { userId, decisionRunId: { not: null } },
      orderBy: { executedAt: "asc" },
      select: {
        decisionRunId: true,
        executedAt: true,
        cashBefore: true,
        cashAfter: true,
      },
    }),
  ]);

  const startingCash = fmtMoneyValue(settings?.startingCash) ?? 100_000;

  const tradesByRun = new Map<
    string,
    {
      firstCashBefore: number | null;
      lastCashAfter: number | null;
    }
  >();

  for (const trade of trades as TradeCashRow[]) {
    if (!trade.decisionRunId) continue;
    const existing = tradesByRun.get(trade.decisionRunId);
    if (!existing) {
      tradesByRun.set(trade.decisionRunId, {
        firstCashBefore: fmtMoneyValue(trade.cashBefore),
        lastCashAfter: fmtMoneyValue(trade.cashAfter),
      });
      continue;
    }
    if (existing.firstCashBefore == null) existing.firstCashBefore = fmtMoneyValue(trade.cashBefore);
    if (fmtMoneyValue(trade.cashAfter) != null) existing.lastCashAfter = fmtMoneyValue(trade.cashAfter);
  }

  const snapshotsAsc = snapshots as SnapshotRow[];
  const runsAsc = [...(runs as RunRow[])].reverse();
  let snapshotIndex = 0;
  let previousCash = startingCash;

  const cashByRun = new Map<string, { cashBefore: number | null; cashAfter: number | null }>();

  for (const run of runsAsc) {
    while (
      snapshotIndex < snapshotsAsc.length &&
      snapshotsAsc[snapshotIndex]!.timestamp < run.startedAt
    ) {
      previousCash = toNum(snapshotsAsc[snapshotIndex]!.cash);
      snapshotIndex++;
    }

    const tradeCash = tradesByRun.get(run.id);
    const cashBefore = tradeCash?.firstCashBefore ?? previousCash;

    let cashAfter = tradeCash?.lastCashAfter ?? null;
    if (cashAfter == null && run.finishedAt) {
      while (
        snapshotIndex < snapshotsAsc.length &&
        snapshotsAsc[snapshotIndex]!.timestamp <= run.finishedAt
      ) {
        previousCash = toNum(snapshotsAsc[snapshotIndex]!.cash);
        cashAfter = previousCash;
        snapshotIndex++;
      }
    }

    if (cashAfter == null) cashAfter = cashBefore;
    previousCash = cashAfter;
    cashByRun.set(run.id, { cashBefore, cashAfter });
  }

  const rows = (runs as RunRow[]).map((run) => {
    const before = fmtMoneyValue(run.portfolioValueBefore);
    const after = fmtMoneyValue(run.portfolioValueAfter);
    const cash = cashByRun.get(run.id) ?? { cashBefore: null, cashAfter: null };
    return {
      id: run.id,
      startedAt: run.startedAt,
      finishedAt: run.finishedAt,
      status: run.status,
      triggerSource: run.triggerSource ?? "unknown",
      buysCount: run.buysCount,
      sellsCount: run.sellsCount,
      cashBefore: cash.cashBefore,
      cashAfter: cash.cashAfter,
      portfolioValueBefore: before,
      portfolioValueAfter: after,
      moneyMade: before != null && after != null ? after - before : null,
    };
  });

  const completed = rows.filter((row) => row.status === "completed");
  const netMoneyMade = completed.reduce((sum, row) => sum + (row.moneyMade ?? 0), 0);
  const scheduledRuns = rows.filter((row) => row.triggerSource === "scheduled").length;

  return {
    rows,
    summary: {
      totalRuns: rows.length,
      scheduledRuns,
      completedRuns: completed.length,
      netMoneyMade,
    },
  };
}
