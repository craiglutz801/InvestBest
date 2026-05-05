import { jsonError, jsonOk } from "@/lib/api/http";
import {
  buildDiagnosticsPayload,
  diagnosticsPayloadToSnapshotParts,
} from "@/lib/diagnostics/buildDiagnosticsPayload";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export const dynamic = "force-dynamic";

/** Persist a point-in-time diagnostics snapshot — Sprint 2 §18.3 / §37. */
export async function POST(req: Request) {
  try {
    const user = await requireDefaultUser();
    const body = (await req.json().catch(() => ({}))) as {
      all?: boolean;
      windowDays?: number;
    };

    const windowDays =
      body.all === true
        ? null
        : Math.min(Math.max(Number(body.windowDays ?? 365) || 365, 1), 3650);

    const payload = await buildDiagnosticsPayload(user.id, { windowDays });
    const row = await prisma.tradeAttributionSnapshot.create({
      data: diagnosticsPayloadToSnapshotParts(user.id, payload),
    });

    return jsonOk({
      ok: true as const,
      snapshotId: row.id,
      generatedAt: row.generatedAt.toISOString(),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
