import { jsonError, jsonOk } from "@/lib/api/http";
import { buildHoldingsPayload } from "@/lib/server/holdingsPayload";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export async function GET() {
  try {
    const user = await requireDefaultUser();
    const rows = await buildHoldingsPayload(user.id);
    return jsonOk({ holdings: rows });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
