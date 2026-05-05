/**
 * Read / write `AgentScheduleSettings` rows.
 *
 * Strategy Upgrade §2 / §3.1 — this is the per-user source of truth for whether
 * scheduled runs are on, the cadence, market-hours rules, retry behavior, and
 * last/next run bookkeeping. The legacy `AppSettings.runFrequencyMinutes` is
 * preserved on the AppSettings table but the scheduler reads `frequencyMinutes`
 * from this table.
 *
 * `loadOrInitScheduleSettings` is intentionally side-effecting: if a user has no
 * row yet (e.g. account predates the migration) we lazy-create one with the same
 * defaults the seed uses. That keeps the scheduler tick robust without forcing
 * an explicit reseed.
 */

import { prisma } from "@/lib/db";
import {
  calculateNextRun,
  effectiveFrequencyMinutes,
} from "./calculateNextRun";
import type {
  ScheduleRunStatus,
  ScheduleSettings,
  SchedulePreset,
} from "./types";

const DEFAULT_TIMEZONE = process.env.DEFAULT_SCHEDULE_TIMEZONE ?? "America/Denver";
const DEFAULT_FREQUENCY = Math.max(
  1,
  Number(process.env.DEFAULT_AGENT_RUN_FREQUENCY_MINUTES) || 60,
);
const DEFAULT_LOCK_TIMEOUT = Math.max(
  1,
  Number(process.env.AGENT_RUN_LOCK_TIMEOUT_MINUTES) || 30,
);
const DEFAULT_ENABLED = process.env.ENABLE_AGENT_SCHEDULER !== "false";

const VALID_PRESETS: ReadonlySet<SchedulePreset> = new Set([
  "every_15_min",
  "every_30_min",
  "hourly",
  "every_2h",
  "every_4h",
  "daily_after_close",
  "daily_before_open",
  "custom",
]);

function normalizePreset(p: string | null | undefined): SchedulePreset {
  if (p && (VALID_PRESETS as Set<string>).has(p)) return p as SchedulePreset;
  return "hourly";
}

function normalizeStatus(s: string | null | undefined): ScheduleRunStatus | null {
  if (!s) return null;
  if (s === "success" || s === "failed" || s === "skipped" || s === "running" || s === "timeout") return s;
  return null;
}

function rowToSettings(row: {
  id: string;
  userId: string;
  enabled: boolean;
  schedulePreset: string;
  frequencyMinutes: number;
  customCronExpression: string | null;
  timezone: string;
  runOnlyDuringMarketHours: boolean;
  runOnMarketDaysOnly: boolean;
  skipIfRunAlreadyActive: boolean;
  maxRunDurationMinutes: number;
  retryFailedRuns: boolean;
  maxRetries: number;
  nextRunAt: Date | null;
  lastRunAt: Date | null;
  lastRunStatus: string | null;
  lastRunError: string | null;
  lastRunId: string | null;
}): ScheduleSettings {
  return {
    id: row.id,
    userId: row.userId,
    enabled: row.enabled,
    schedulePreset: normalizePreset(row.schedulePreset),
    frequencyMinutes: row.frequencyMinutes,
    customCronExpression: row.customCronExpression,
    timezone: row.timezone,
    runOnlyDuringMarketHours: row.runOnlyDuringMarketHours,
    runOnMarketDaysOnly: row.runOnMarketDaysOnly,
    skipIfRunAlreadyActive: row.skipIfRunAlreadyActive,
    maxRunDurationMinutes: row.maxRunDurationMinutes,
    retryFailedRuns: row.retryFailedRuns,
    maxRetries: row.maxRetries,
    nextRunAt: row.nextRunAt,
    lastRunAt: row.lastRunAt,
    lastRunStatus: normalizeStatus(row.lastRunStatus),
    lastRunError: row.lastRunError,
    lastRunId: row.lastRunId,
  };
}

export async function loadOrInitScheduleSettings(userId: string): Promise<ScheduleSettings> {
  const existing = await prisma.agentScheduleSettings.findUnique({ where: { userId } });
  if (existing) return rowToSettings(existing);

  // Lazy create with sane defaults. Mirrors AppSettings.runFrequencyMinutes when present.
  const app = await prisma.appSettings.findUnique({ where: { userId }, select: { runFrequencyMinutes: true } });
  const created = await prisma.agentScheduleSettings.create({
    data: {
      userId,
      enabled: DEFAULT_ENABLED,
      schedulePreset: "hourly",
      frequencyMinutes: app?.runFrequencyMinutes ?? DEFAULT_FREQUENCY,
      timezone: DEFAULT_TIMEZONE,
      runOnlyDuringMarketHours: process.env.ENABLE_MARKET_HOURS_ONLY === "true",
      runOnMarketDaysOnly: true,
      skipIfRunAlreadyActive: true,
      maxRunDurationMinutes: DEFAULT_LOCK_TIMEOUT,
      retryFailedRuns: false,
      maxRetries: 0,
    },
  });
  return rowToSettings(created);
}

export type ScheduleSettingsUpdate = Partial<{
  enabled: boolean;
  schedulePreset: SchedulePreset;
  frequencyMinutes: number;
  customCronExpression: string | null;
  timezone: string;
  runOnlyDuringMarketHours: boolean;
  runOnMarketDaysOnly: boolean;
  skipIfRunAlreadyActive: boolean;
  maxRunDurationMinutes: number;
  retryFailedRuns: boolean;
  maxRetries: number;
}>;

/**
 * Update schedule settings and recompute `nextRunAt` from the new cadence.
 * The scheduler tick reads `nextRunAt` to decide whether a run is due, so any
 * UI change must keep that field consistent.
 */
export async function updateScheduleSettings(
  userId: string,
  patch: ScheduleSettingsUpdate,
): Promise<ScheduleSettings> {
  const before = await loadOrInitScheduleSettings(userId);
  const merged = { ...before, ...patch } as ScheduleSettings;

  // Defensive bounds.
  if (typeof patch.frequencyMinutes === "number") {
    merged.frequencyMinutes = Math.max(1, Math.min(60 * 24 * 7, patch.frequencyMinutes));
  }
  if (typeof patch.maxRunDurationMinutes === "number") {
    merged.maxRunDurationMinutes = Math.max(1, Math.min(180, patch.maxRunDurationMinutes));
  }
  if (typeof patch.maxRetries === "number") {
    merged.maxRetries = Math.max(0, Math.min(10, patch.maxRetries));
  }
  if (patch.schedulePreset) merged.schedulePreset = normalizePreset(patch.schedulePreset);

  // Keep frequencyMinutes consistent with the preset so the UI stays honest.
  const presetCadence = effectiveFrequencyMinutes({
    schedulePreset: merged.schedulePreset,
    frequencyMinutes: merged.frequencyMinutes,
  });
  if (presetCadence != null && merged.schedulePreset !== "custom") {
    merged.frequencyMinutes = presetCadence;
  }

  const nextRunAt = calculateNextRun({
    enabled: merged.enabled,
    schedulePreset: merged.schedulePreset,
    frequencyMinutes: merged.frequencyMinutes,
    runOnMarketDaysOnly: merged.runOnMarketDaysOnly,
    lastRunAt: merged.lastRunAt,
  });

  const updated = await prisma.agentScheduleSettings.update({
    where: { userId },
    data: {
      enabled: merged.enabled,
      schedulePreset: merged.schedulePreset,
      frequencyMinutes: merged.frequencyMinutes,
      customCronExpression: merged.customCronExpression ?? null,
      timezone: merged.timezone,
      runOnlyDuringMarketHours: merged.runOnlyDuringMarketHours,
      runOnMarketDaysOnly: merged.runOnMarketDaysOnly,
      skipIfRunAlreadyActive: merged.skipIfRunAlreadyActive,
      maxRunDurationMinutes: merged.maxRunDurationMinutes,
      retryFailedRuns: merged.retryFailedRuns,
      maxRetries: merged.maxRetries,
      nextRunAt,
    },
  });
  return rowToSettings(updated);
}

/**
 * After a run completes (or is skipped) the scheduler must update bookkeeping
 * fields atomically so the UI shows truthful "last run" / "next run" state.
 */
export async function recordScheduleRunResult(
  userId: string,
  result: {
    runId: string | null;
    status: ScheduleRunStatus;
    error?: string | null;
    completedAt?: Date;
  },
): Promise<ScheduleSettings> {
  const before = await loadOrInitScheduleSettings(userId);
  const completedAt = result.completedAt ?? new Date();
  const nextRunAt = calculateNextRun(
    {
      enabled: before.enabled,
      schedulePreset: before.schedulePreset,
      frequencyMinutes: before.frequencyMinutes,
      runOnMarketDaysOnly: before.runOnMarketDaysOnly,
      lastRunAt: completedAt,
    },
    completedAt,
  );

  const updated = await prisma.agentScheduleSettings.update({
    where: { userId },
    data: {
      lastRunAt: completedAt,
      lastRunStatus: result.status,
      lastRunError: result.error ?? null,
      lastRunId: result.runId,
      nextRunAt,
    },
  });
  return rowToSettings(updated);
}
