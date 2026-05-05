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
      message: "Walk-forward backtests belong in ml-service/backtests (Milestone 4).",
    },
    { status: 501 },
  );
}
