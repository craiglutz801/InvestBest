import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export const dynamic = "force-dynamic";

/** List configured universe segments and symbol counts (addendum §13). */
export async function GET() {
  try {
    await requireDefaultUser();
    const segments = await prisma.universeSegment.findMany({
      orderBy: { sortOrder: "asc" },
      include: {
        _count: { select: { segmentSymbols: true } },
      },
    });
    return jsonOk({
      segments: segments.map((s) => ({
        id: s.id,
        key: s.key,
        name: s.name,
        description: s.description,
        isEnabled: s.isEnabled,
        segmentWeight: Number(s.segmentWeight),
        maxPositions: s.maxPositions,
        symbolCount: s._count.segmentSymbols,
      })),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
