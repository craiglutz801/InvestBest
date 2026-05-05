import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { requireDefaultUser } from "@/lib/server/defaultUser";
import type { Prisma } from "@prisma/client";

export const dynamic = "force-dynamic";

function escapeCsvCell(value: string): string {
  if (/[",\r\n]/.test(value)) return `"${value.replace(/"/g, '""')}"`;
  return value;
}

function csvRow(cells: (string | number | null | undefined)[]): string {
  return cells
    .map((c) => {
      if (c == null || c === "") return "";
      const s = typeof c === "number" ? String(c) : String(c);
      return escapeCsvCell(s);
    })
    .join(",");
}

function num(d: { toString(): string } | null | undefined): number | null {
  return d != null ? toNum(d) : null;
}

const SORT_FIELDS = ["ticker", "status", "buyScore", "buyRank", "segmentKey"] as const;
type SortField = (typeof SORT_FIELDS)[number];

function orderByFromQuery(sort: string | null, dir: string | null): Prisma.DecisionRunCandidateOrderByWithRelationInput {
  const d = dir === "desc" ? "desc" : "asc";
  const s = SORT_FIELDS.includes(sort as SortField) ? (sort as SortField) : "ticker";
  if (s === "buyRank") return { buyRank: d };
  return { [s]: d };
}

export async function GET(req: Request, ctx: { params: Promise<{ id: string }> }) {
  try {
    const user = await requireDefaultUser();
    const { id: runId } = await ctx.params;
    const url = new URL(req.url);
    const format = url.searchParams.get("format");
    const sort = url.searchParams.get("sort");
    const dir = url.searchParams.get("dir");

    const run = await prisma.decisionRun.findFirst({
      where: { id: runId, userId: user.id },
      select: { id: true },
    });
    if (!run) return jsonError("Not found", 404);

    const rows = await prisma.decisionRunCandidate.findMany({
      where: { decisionRunId: runId },
      orderBy: orderByFromQuery(sort, dir),
    });

    const payload = rows.map((r) => ({
      symbolId: r.symbolId,
      ticker: r.ticker,
      segmentKey: r.segmentKey,
      status: r.status,
      currentPrice: num(r.currentPrice),
      ret1d: num(r.ret1d),
      ret5d: num(r.ret5d),
      volatility20d: num(r.volatility20d),
      buyScore: num(r.buyScore),
      sellRiskScore: num(r.sellRiskScore),
      confidenceScore: num(r.confidenceScore),
      buyRank: r.buyRank,
      rejectionReason: r.rejectionReason,
    }));

    if (format === "csv") {
      const header = csvRow([
        "ticker",
        "segmentKey",
        "status",
        "currentPrice",
        "ret1d",
        "ret5d",
        "volatility20d",
        "buyScore",
        "sellRiskScore",
        "confidenceScore",
        "buyRank",
        "rejectionReason",
      ]);
      const lines = payload.map((p) =>
        csvRow([
          p.ticker,
          p.segmentKey,
          p.status,
          p.currentPrice,
          p.ret1d,
          p.ret5d,
          p.volatility20d,
          p.buyScore,
          p.sellRiskScore,
          p.confidenceScore,
          p.buyRank,
          p.rejectionReason,
        ]),
      );
      const body = [header, ...lines].join("\r\n");
      return new Response(body, {
        status: 200,
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": `attachment; filename="run-${runId}-candidates.csv"`,
        },
      });
    }

    return jsonOk({ runId, count: payload.length, candidates: payload });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
