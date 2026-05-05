import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export async function GET(req: Request) {
  try {
    const user = await requireDefaultUser();
    const { searchParams } = new URL(req.url);
    const limit = Math.min(Number(searchParams.get("limit") ?? "200") || 200, 500);
    const trades = await prisma.paperTrade.findMany({
      where: { userId: user.id },
      orderBy: { executedAt: "desc" },
      take: limit,
      include: { symbol: true },
    });
    return jsonOk({
      trades: trades.map((t) => ({
        id: t.id,
        executedAt: t.executedAt.toISOString(),
        ticker: t.symbol.ticker,
        action: t.action,
        quantity: toNum(t.quantity),
        price: toNum(t.price),
        slippagePct: toNum(t.slippagePct),
        fees: toNum(t.fees),
        grossAmount: toNum(t.grossAmount),
        reasonCode: t.reasonCode,
        reasonText: t.reasonText,
        modelVersion: t.modelVersion,
        confidenceScore: t.confidenceScore != null ? toNum(t.confidenceScore) : null,
        cashBefore: t.cashBefore != null ? toNum(t.cashBefore) : null,
        cashAfter: t.cashAfter != null ? toNum(t.cashAfter) : null,
        expectedHorizon: t.expectedHorizon,
        decisionRunId: t.decisionRunId,
      })),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
