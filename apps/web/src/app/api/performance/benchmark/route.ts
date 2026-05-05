import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { totalReturnPct } from "@/lib/performance/metrics";
import { requireDefaultUser } from "@/lib/server/defaultUser";

/** SPY buy-and-hold value from snapshots' benchmarkValue vs portfolio totalValue */
export async function GET() {
  try {
    const user = await requireDefaultUser();
    const settings = await prisma.appSettings.findUnique({ where: { userId: user.id } });
    const starting = settings ? toNum(settings.startingCash) : 100_000;

    const latest = await prisma.portfolioSnapshot.findFirst({
      where: { userId: user.id },
      orderBy: { timestamp: "desc" },
    });

    if (!latest) {
      return jsonOk({
        startingCash: starting,
        portfolioValue: starting,
        benchmarkValue: starting,
        portfolioReturnPct: 0,
        benchmarkReturnPct: 0,
      });
    }

    const port = toNum(latest.totalValue);
    const bench = latest.benchmarkValue != null ? toNum(latest.benchmarkValue) : starting;

    return jsonOk({
      startingCash: starting,
      portfolioValue: port,
      benchmarkValue: bench,
      portfolioReturnPct: totalReturnPct(starting, port),
      benchmarkReturnPct: totalReturnPct(starting, bench),
      asOf: latest.timestamp.toISOString(),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
