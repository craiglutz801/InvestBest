import { jsonError, jsonOk } from "@/lib/api/http";
import { buildDashboardPayload } from "@/lib/server/dashboardPayload";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export async function GET() {
  try {
    const user = await requireDefaultUser();
    const data = await buildDashboardPayload(user.id);
    return jsonOk(data);
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
