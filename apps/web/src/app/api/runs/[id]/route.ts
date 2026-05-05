import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { parseRunNotes } from "@/lib/jobs/runProgress";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export const dynamic = "force-dynamic";

export async function GET(_req: Request, ctx: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireDefaultUser();
    const { id } = await ctx.params;
    const run = await prisma.decisionRun.findFirst({
      where: { id, userId: user.id },
      include: { items: { include: { symbol: true }, take: 120 } },
    });
    if (!run) return jsonError("Not found", 404);

    const notes = parseRunNotes(run.notesJson);
    const progressLog = Array.isArray(notes.progress) ? notes.progress : [];
    const holdingsMarkBefore = Array.isArray(notes.holdingsMarkBefore) ? notes.holdingsMarkBefore : [];
    const holdingsMarkAfter = Array.isArray(notes.holdingsMarkAfter) ? notes.holdingsMarkAfter : [];

    return jsonOk({
      id: run.id,
      startedAt: run.startedAt.toISOString(),
      finishedAt: run.finishedAt?.toISOString() ?? null,
      status: run.status,
      universeSize: run.universeSize,
      candidatesCount: run.candidatesCount,
      buysCount: run.buysCount,
      sellsCount: run.sellsCount,
      portfolioValueBefore: run.portfolioValueBefore != null ? toNum(run.portfolioValueBefore) : null,
      portfolioValueAfter: run.portfolioValueAfter != null ? toNum(run.portfolioValueAfter) : null,
      llmSummary: run.llmSummary,
      notesJson: run.notesJson,
      progressLog,
      holdingsMarkBefore,
      holdingsMarkAfter,
      items: run.items.map((i) => ({
        symbol: i.symbol.ticker,
        actionRecommendation: i.actionRecommendation,
        rank: i.rank,
        blocked: i.blocked,
        blockedReason: i.blockedReason,
        buyScore: i.buyScore != null ? toNum(i.buyScore) : null,
        sellRiskScore: i.sellRiskScore != null ? toNum(i.sellRiskScore) : null,
        confidenceScore: i.confidenceScore != null ? toNum(i.confidenceScore) : null,
        rationaleShort: i.rationaleShort,
      })),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
