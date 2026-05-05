import { jsonError, jsonOk } from "@/lib/api/http";
import { internalAuthorized } from "@/lib/server/internalAuth";
import type { NextRequest } from "next/server";

export async function POST(req: NextRequest) {
  if (!internalAuthorized(req)) {
    return jsonError("Unauthorized", 401);
  }
  return jsonOk(
    {
      status: "not_implemented",
      message: "Offline rebuild pipeline not wired in MVP web bundle. Use hourly agent or ml-service batch.",
    },
    { status: 501 },
  );
}
