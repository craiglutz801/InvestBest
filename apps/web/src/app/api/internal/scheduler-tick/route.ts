import { jsonError, jsonOk } from "@/lib/api/http";
import { runSchedulerTick } from "@/lib/jobs/hourlyAgentScheduler";
import { internalAuthorized } from "@/lib/server/internalAuth";
import type { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
/** The route returns fast — agent pipelines kicked off here run via Next.js `after`. */
export const maxDuration = 300;

/**
 * Scheduler tick endpoint (Strategy Upgrade §4 / §7).
 *
 * Should be hit by a static external cron (Vercel Cron, Trigger.dev, GitHub Actions,
 * a tiny cronjob box, …) on a fixed cadence (default: every hour at :00). The route
 * itself contains zero strategy logic — it just authenticates the caller and asks
 * `runSchedulerTick()` to:
 *
 *   - expire stale per-user run locks,
 *   - check each user's `AgentScheduleSettings` for "is a run due?",
 *   - skip when disabled / outside market hours / not yet due,
 *   - call `triggerAgentRun` (which acquires the lock and persists the DecisionRun).
 *
 * Auth: same secret rules as the legacy `/api/internal/hourly-run`, see `internalAuthorized`.
 */
async function handle(_req: NextRequest) {
  return jsonOk(await runSchedulerTick({ background: false }));
}

export async function GET(req: NextRequest) {
  if (!internalAuthorized(req)) return jsonError("Unauthorized", 401);
  try {
    return await handle(req);
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Tick failed", 500);
  }
}

export async function POST(req: NextRequest) {
  if (!internalAuthorized(req)) return jsonError("Unauthorized", 401);
  try {
    return await handle(req);
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Tick failed", 500);
  }
}
