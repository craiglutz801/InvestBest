import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export async function GET(req: Request) {
  try {
    const user = await requireDefaultUser();
    const { searchParams } = new URL(req.url);
    const limit = Math.min(Number(searchParams.get("limit") ?? "30") || 30, 100);
    const runs = await prisma.decisionRun.findMany({
      where: { userId: user.id },
      orderBy: { startedAt: "desc" },
      take: limit,
      include: {
        items: { include: { symbol: true }, take: 80 },
      },
    });

    return jsonOk({
      runs: runs.map((r) => ({
        id: r.id,
        startedAt: r.startedAt.toISOString(),
        finishedAt: r.finishedAt?.toISOString() ?? null,
        status: r.status,
        universeSize: r.universeSize,
        candidatesCount: r.candidatesCount,
        buysCount: r.buysCount,
        sellsCount: r.sellsCount,
        portfolioValueBefore: r.portfolioValueBefore != null ? toNum(r.portfolioValueBefore) : null,
        portfolioValueAfter: r.portfolioValueAfter != null ? toNum(r.portfolioValueAfter) : null,
        llmSummary: r.llmSummary,
        notesJson: r.notesJson,
        items: r.items.map((i) => ({
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
      })),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
