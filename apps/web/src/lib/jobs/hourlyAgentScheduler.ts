/**
 * Scheduler tick driver — called by `/api/internal/scheduler-tick`.
 *
 * Strategy Upgrade §7 — the route's only job is auth + JSON. The actual logic
 * lives here so it can be reused (Trigger.dev task, local CLI, tests).
 *
 * Flow:
 *   1. Expire stale locks so a crashed previous run doesn't permanently block.
 *   2. For each enabled schedule, decide whether the run is due right now.
 *   3. Apply market-hours / market-day filters if configured.
 *   4. Hand off to `triggerAgentRun` (which acquires the run-lock and persists
 *      a DecisionRun with `triggerSource = "scheduled"`).
 *
 * Sprint 1 supports a single per-user schedule (one row per user). When we add
 * multi-user / multi-schedule support a `findMany` over enabled schedules drops
 * in here without changing the contract.
 */

import { prisma } from "@/lib/db";
import { isDueNow } from "@/lib/scheduler/calculateNextRun";
import {
  describeMarketWindow,
  isMarketDayET,
  isWithinMarketHoursET,
} from "@/lib/scheduler/marketHours";
import { expireStaleLocks } from "@/lib/scheduler/runLock";
import { loadOrInitScheduleSettings } from "@/lib/scheduler/scheduleSettings";
import { triggerAgentRun } from "@/lib/scheduler/triggerAgentRun";
import type { RunOutcome } from "@/lib/scheduler/types";

export type SchedulerTickResult = {
  ranAt: string;
  expiredLocks: number;
  decisions: Array<{
    userId: string;
    scheduleId: string;
    outcome: RunOutcome | { status: "skipped_disabled" | "skipped_not_due" | "skipped_market_closed"; reason: string };
  }>;
};

export async function runSchedulerTick(options?: {
  /** Restrict tick to one user (default: all users with schedules). */
  userId?: string;
  /** When true, kick off the agent pipeline asynchronously (cron heartbeat); default is synchronous. */
  background?: boolean;
  /** Pass Next.js `after` so background pipelines run after the response is sent. */
  scheduleAfter?: (task: () => void | Promise<void>) => void;
}): Promise<SchedulerTickResult> {
  const ranAt = new Date();
  const expiredLocks = await expireStaleLocks(ranAt);

  const userIds = options?.userId
    ? [options.userId]
    : (await prisma.agentScheduleSettings.findMany({ select: { userId: true } })).map((r) => r.userId);

  const decisions: SchedulerTickResult["decisions"] = [];

  for (const userId of userIds) {
    const schedule = await loadOrInitScheduleSettings(userId);

    if (!schedule.enabled) {
      decisions.push({
        userId,
        scheduleId: schedule.id,
        outcome: { status: "skipped_disabled", reason: "Scheduled runs are disabled in Settings → Agent Automation." },
      });
      continue;
    }

    if (schedule.runOnMarketDaysOnly && !isMarketDayET(ranAt)) {
      decisions.push({
        userId,
        scheduleId: schedule.id,
        outcome: {
          status: "skipped_market_closed",
          reason: `Skipped — runOnMarketDaysOnly is on. ${describeMarketWindow(ranAt)}`,
        },
      });
      continue;
    }
    if (schedule.runOnlyDuringMarketHours && !isWithinMarketHoursET(ranAt)) {
      decisions.push({
        userId,
        scheduleId: schedule.id,
        outcome: {
          status: "skipped_market_closed",
          reason: `Skipped — runOnlyDuringMarketHours is on. ${describeMarketWindow(ranAt)}`,
        },
      });
      continue;
    }

    if (!isDueNow(schedule, ranAt)) {
      decisions.push({
        userId,
        scheduleId: schedule.id,
        outcome: {
          status: "skipped_not_due",
          reason: schedule.nextRunAt
            ? `Next run ${schedule.nextRunAt.toISOString()} (cadence ${schedule.frequencyMinutes}m).`
            : `Schedule recently created; will run on next tick.`,
        },
      });
      continue;
    }

    const outcome = await triggerAgentRun({
      userId,
      triggerSource: "scheduled",
      scheduleId: schedule.id,
      background: options?.background ?? false,
      scheduleAfter: options?.scheduleAfter,
    });
    decisions.push({ userId, scheduleId: schedule.id, outcome });
  }

  return {
    ranAt: ranAt.toISOString(),
    expiredLocks,
    decisions,
  };
}
