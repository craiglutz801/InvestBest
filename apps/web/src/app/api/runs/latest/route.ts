import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";

/**
 * `GET /api/runs/latest` — Strategy Upgrade §4.5.
 *
 * Returns metadata for the most recent DecisionRun (any trigger source) so the
 * dashboard can show "Last agent run", run status, and a quick link.
 *
 * Optional `?triggerSource=manual|scheduled|...` filter.
 */
export async function GET(req: Request) {
  try {
    const user = await requireDefaultUser();
    const url = new URL(req.url);
    const triggerSource = url.searchParams.get("triggerSource");

    const row = await prisma.decisionRun.findFirst({
      where: {
        userId: user.id,
        ...(triggerSource ? { triggerSource } : {}),
      },
      orderBy: { startedAt: "desc" },
      select: {
        id: true,
        startedAt: true,
        finishedAt: true,
        status: true,
        triggerSource: true,
        runMode: true,
        scheduleId: true,
        lockId: true,
        buysCount: true,
        sellsCount: true,
        candidatesCount: true,
        portfolioValueBefore: true,
        portfolioValueAfter: true,
      },
    });
    if (!row) return jsonOk({ run: null });

    return jsonOk({
      run: {
        id: row.id,
        startedAt: row.startedAt.toISOString(),
        finishedAt: row.finishedAt?.toISOString() ?? null,
        status: row.status,
        triggerSource: row.triggerSource,
        runMode: row.runMode,
        scheduleId: row.scheduleId,
        lockId: row.lockId,
        buysCount: row.buysCount,
        sellsCount: row.sellsCount,
        candidatesCount: row.candidatesCount,
        portfolioValueBefore: row.portfolioValueBefore?.toString() ?? null,
        portfolioValueAfter: row.portfolioValueAfter?.toString() ?? null,
      },
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
