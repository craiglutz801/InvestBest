/**
 * Compute the next allowed run time for a schedule.
 *
 * Strategy Upgrade §2.1 / §4.4 — the UI uses this both for `nextRunAt` and to
 * decide "is a run due now?" inside the scheduler tick (`isDueNow`).
 *
 * Sprint 1 covers the named presets exactly. `custom` cron expressions are
 * accepted and stored, but evaluated as a flat `frequencyMinutes` cadence
 * because we don't ship a full cron parser yet — the spec calls this out as
 * acceptable for the database-driven scheduler design.
 */

import type { ScheduleSettings, SchedulePreset } from "./types";

const NY_TZ = "America/New_York";

const PRESET_MINUTES: Partial<Record<SchedulePreset, number>> = {
  every_15_min: 15,
  every_30_min: 30,
  hourly: 60,
  every_2h: 120,
  every_4h: 240,
};

/** Effective cadence in minutes (or null when the preset is anchored to a time of day). */
export function effectiveFrequencyMinutes(s: Pick<ScheduleSettings, "schedulePreset" | "frequencyMinutes">): number | null {
  const pm = PRESET_MINUTES[s.schedulePreset];
  if (pm) return pm;
  if (s.schedulePreset === "daily_after_close" || s.schedulePreset === "daily_before_open") return null;
  // custom or anything unknown — fall back to stored frequency.
  return Math.max(1, s.frequencyMinutes);
}

function nyParts(at: Date): { hour: number; minute: number; weekday: string; year: number; month: number; day: number } {
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: NY_TZ,
    weekday: "short",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "numeric",
    minute: "numeric",
    hour12: false,
  });
  const parts = fmt.formatToParts(at);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return {
    hour: Number(get("hour")) || 0,
    minute: Number(get("minute")) || 0,
    weekday: get("weekday"),
    year: Number(get("year")) || 0,
    month: Number(get("month")) || 0,
    day: Number(get("day")) || 0,
  };
}

/** Return the next instant >= `from` whose ET wall clock is `targetHourEt:targetMinuteEt`, on a weekday if requested. */
function nextEtTimeOfDay(
  from: Date,
  targetHourEt: number,
  targetMinuteEt: number,
  weekdaysOnly: boolean,
): Date {
  // Probe forward in 30-minute steps; cheap and avoids timezone math edge cases.
  const probe = new Date(from);
  for (let i = 0; i < 24 * 14 * 2; i++) {
    const p = nyParts(probe);
    const isWeekday = p.weekday !== "Sat" && p.weekday !== "Sun";
    if ((!weekdaysOnly || isWeekday) && p.hour === targetHourEt && p.minute === targetMinuteEt) {
      return probe;
    }
    probe.setUTCMinutes(probe.getUTCMinutes() + 30);
  }
  return probe;
}

/** Next run time given current time, the schedule, and the last run timestamp. */
export function calculateNextRun(
  s: Pick<
    ScheduleSettings,
    "enabled" | "schedulePreset" | "frequencyMinutes" | "runOnMarketDaysOnly" | "lastRunAt"
  >,
  now: Date = new Date(),
): Date | null {
  if (!s.enabled) return null;

  if (s.schedulePreset === "daily_after_close") {
    // 16:15 ET — 15 minutes after the regular session close.
    return nextEtTimeOfDay(now, 16, 15, s.runOnMarketDaysOnly);
  }
  if (s.schedulePreset === "daily_before_open") {
    // 09:00 ET — 30 minutes before regular session open.
    return nextEtTimeOfDay(now, 9, 0, s.runOnMarketDaysOnly);
  }

  const minutes = effectiveFrequencyMinutes(s) ?? Math.max(1, s.frequencyMinutes);
  const baseline = s.lastRunAt && s.lastRunAt.getTime() > 0 ? s.lastRunAt.getTime() : now.getTime();
  let next = baseline + minutes * 60_000;
  if (next < now.getTime()) next = now.getTime();
  return new Date(next);
}

/** Has the scheduler tick reached or passed the configured next-run? */
export function isDueNow(
  s: Pick<
    ScheduleSettings,
    "enabled" | "schedulePreset" | "frequencyMinutes" | "runOnMarketDaysOnly" | "nextRunAt" | "lastRunAt"
  >,
  now: Date = new Date(),
): boolean {
  if (!s.enabled) return false;
  if (s.nextRunAt) return s.nextRunAt.getTime() <= now.getTime();
  // No nextRunAt yet — first ever tick. Allow it.
  return true;
}

/** Friendly description of the cadence for the Settings UI. */
export function describeSchedule(
  s: Pick<ScheduleSettings, "schedulePreset" | "frequencyMinutes" | "customCronExpression" | "timezone">,
): string {
  switch (s.schedulePreset) {
    case "every_15_min":
      return "Every 15 minutes";
    case "every_30_min":
      return "Every 30 minutes";
    case "hourly":
      return "Every hour";
    case "every_2h":
      return "Every 2 hours";
    case "every_4h":
      return "Every 4 hours";
    case "daily_after_close":
      return `Daily after market close (16:15 ${NY_TZ})`;
    case "daily_before_open":
      return `Daily before market open (09:00 ${NY_TZ})`;
    case "custom":
      return s.customCronExpression
        ? `Custom: ${s.customCronExpression} (treated as every ${s.frequencyMinutes}m until cron parser ships)`
        : `Custom (every ${s.frequencyMinutes} minutes)`;
    default:
      return `Every ${s.frequencyMinutes} minutes`;
  }
}
