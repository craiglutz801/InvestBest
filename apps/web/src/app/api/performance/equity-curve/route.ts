import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { snapshotsToEquitySeries } from "@/lib/performance/metrics";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export async function GET(req: Request) {
  try {
    const user = await requireDefaultUser();
    const { searchParams } = new URL(req.url);
    const limit = Math.min(Number(searchParams.get("limit") ?? "500") || 500, 2000);

    const snaps = await prisma.portfolioSnapshot.findMany({
      where: { userId: user.id },
      orderBy: { timestamp: "asc" },
      take: limit,
    });

    const { points, maxDrawdown } = snapshotsToEquitySeries(snaps);

    return jsonOk({
      points: points.map((p) => ({
        t: p.t,
        totalValue: p.value,
        benchmark: p.benchmark ?? null,
      })),
      maxDrawdownPct: maxDrawdown * 100,
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
