import { jsonError, jsonOk } from "@/lib/api/http";
import { runSchedulerTick } from "@/lib/jobs/hourlyAgentScheduler";
import { internalAuthorized } from "@/lib/server/internalAuth";
import type { NextRequest } from "next/server";

/**
 * Legacy hourly-run cron endpoint.
 *
 * Strategy Upgrade §1.5 / §7 — historically `vercel.json` pointed here. After the
 * scheduler upgrade the canonical path is `/api/internal/scheduler-tick`. This
 * endpoint stays as a thin alias so existing cron entries / Trigger.dev jobs
 * keep working: it just delegates to the scheduler tick driver, which decides
 * which schedules are due and respects per-user enable / market-hours / lock state.
 */
async function tick() {
  return runSchedulerTick();
}

export async function GET(req: NextRequest) {
  if (!internalAuthorized(req)) return jsonError("Unauthorized", 401);
  try {
    return jsonOk(await tick());
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Run failed", 500);
  }
}

export async function POST(req: NextRequest) {
  if (!internalAuthorized(req)) return jsonError("Unauthorized", 401);
  try {
    return jsonOk(await tick());
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Run failed", 500);
  }
}
