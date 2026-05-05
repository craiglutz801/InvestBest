import { jsonError, jsonOk } from "@/lib/api/http";
import {
  calculateNextRun,
  describeSchedule,
} from "@/lib/scheduler/calculateNextRun";
import { describeMarketWindow } from "@/lib/scheduler/marketHours";
import { loadOrInitScheduleSettings } from "@/lib/scheduler/scheduleSettings";
import { requireDefaultUser } from "@/lib/server/defaultUser";

/**
 * `GET /api/settings/agent-schedule/next-run` — Strategy Upgrade §4.4.
 *
 * Returns the same fields the dashboard / Settings page need to show "next run"
 * + status without each component recomputing the cadence math.
 */
export async function GET() {
  try {
    const user = await requireDefaultUser();
    const s = await loadOrInitScheduleSettings(user.id);
    const now = new Date();
    const computed = calculateNextRun(s, now);
    const warnings: string[] = [];
    if (s.runOnlyDuringMarketHours) {
      warnings.push("runOnlyDuringMarketHours is on — runs are skipped outside ET 09:30–16:00.");
    }
    if (s.runOnMarketDaysOnly) {
      warnings.push("runOnMarketDaysOnly is on — Sat/Sun ticks are skipped (US holiday calendar not yet enforced).");
    }
    if (s.schedulePreset === "every_15_min" || s.schedulePreset === "every_30_min") {
      warnings.push(
        "Sub-hourly cadences require an external cron that ticks at least that often (Vercel hobby plan is 1/h).",
      );
    }
    return jsonOk({
      enabled: s.enabled,
      nextRunAt: computed?.toISOString() ?? null,
      lastRunAt: s.lastRunAt?.toISOString() ?? null,
      lastRunStatus: s.lastRunStatus,
      lastRunError: s.lastRunError,
      lastRunId: s.lastRunId,
      schedulePreset: s.schedulePreset,
      frequencyMinutes: s.frequencyMinutes,
      timezone: s.timezone,
      description: describeSchedule(s),
      marketWindowNow: describeMarketWindow(now),
      warnings,
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
