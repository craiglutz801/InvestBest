import { jsonError, jsonOk } from "@/lib/api/http";
import {
  buildDiagnosticsPayload,
  diagnosticsPayloadFromSnapshotRow,
} from "@/lib/diagnostics/buildDiagnosticsPayload";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export const dynamic = "force-dynamic";

/**
 * Full Strategy Diagnostics payload — Sprint 2 §4 / §18.
 * Query: `windowDays` (default 365), `all=1` for full history, `cached=1` for last snapshot row.
 */
export async function GET(req: Request) {
  try {
    const user = await requireDefaultUser();
    const url = new URL(req.url);
    if (url.searchParams.get("cached") === "1") {
      const row = await prisma.tradeAttributionSnapshot.findFirst({
        where: { userId: user.id },
        orderBy: { generatedAt: "desc" },
      });
      if (!row) {
        return jsonOk({ source: "snapshot" as const, payload: null });
      }
      return jsonOk({
        source: "snapshot" as const,
        payload: diagnosticsPayloadFromSnapshotRow(row),
      });
    }

    const all = url.searchParams.get("all") === "1";
    const wdRaw = url.searchParams.get("windowDays");
    const parsed = Number(wdRaw ?? "365");
    const windowDays = all ? null : Math.min(Math.max(Number.isFinite(parsed) ? parsed : 365, 1), 3650);

    const payload = await buildDiagnosticsPayload(user.id, { windowDays });
    return jsonOk({ source: "live" as const, payload });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
