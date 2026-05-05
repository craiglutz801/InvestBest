import { jsonError, jsonOk } from "@/lib/api/http";
import { buildDiagnosticsPayload } from "@/lib/diagnostics/buildDiagnosticsPayload";
import { DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS } from "@/lib/diagnostics/constants";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export const dynamic = "force-dynamic";

/** Lightweight KPI strip for dashboards / widgets — Sprint 2 §37. */
export async function GET(req: Request) {
  try {
    const user = await requireDefaultUser();
    const url = new URL(req.url);
    const all = url.searchParams.get("all") === "1";
    const wdRaw = url.searchParams.get("windowDays");
    const parsed = Number(wdRaw ?? String(DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS));
    const windowDays = all
      ? null
      : Math.min(
          Math.max(Number.isFinite(parsed) ? parsed : DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS, 1),
          3650,
        );

    const p = await buildDiagnosticsPayload(user.id, { windowDays });
    return jsonOk({
      generatedAt: p.generatedAt,
      windowStart: p.windowStart,
      windowEnd: p.windowEnd,
      windowDays,
      closedTradeCount: p.metrics.closedTradeCount,
      totalReturnPct: p.metrics.totalReturnPct,
      benchmarkReturnPct: p.metrics.benchmarkReturnPct,
      excessReturnPct: p.metrics.excessReturnPct,
      maxDrawdownPct: p.metrics.maxDrawdownPct,
      sharpeAnnualized: p.metrics.sharpeAnnualized,
      sortinoAnnualized: p.metrics.sortinoAnnualized,
      winRatePct: p.metrics.winRatePct,
      profitFactor: p.metrics.profitFactor,
      expectancyPerTrade: p.metrics.expectancyPerTrade,
      warningCount: p.warnings.length,
      warningsBySeverity: {
        critical: p.warnings.filter((w) => w.severity === "critical").length,
        warning: p.warnings.filter((w) => w.severity === "warning").length,
        info: p.warnings.filter((w) => w.severity === "info").length,
      },
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
