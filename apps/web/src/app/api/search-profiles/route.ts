import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export const dynamic = "force-dynamic";

/** List search profiles for the signed-in user (addendum §13). */
export async function GET() {
  try {
    const user = await requireDefaultUser();
    const rows = await prisma.searchProfile.findMany({
      where: { userId: user.id },
      orderBy: [{ isDefault: "desc" }, { name: "asc" }],
    });
    return jsonOk({
      profiles: rows.map((p) => ({
        id: p.id,
        name: p.name,
        isDefault: p.isDefault,
        profile: JSON.parse(p.profileJson || "{}") as Record<string, unknown>,
        updatedAt: p.updatedAt.toISOString(),
      })),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
