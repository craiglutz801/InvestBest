/**
 * Database-driven scheduler provider (Strategy Upgrade §6.3 / §7.1).
 *
 * "Static external heartbeat + dynamic database schedule": some external cron
 * (Vercel Cron, Trigger.dev, GitHub Actions, etc) hits `/api/internal/scheduler-tick`
 * on a fixed cadence; that route reads `AgentScheduleSettings` from the database
 * and decides whether the run is actually due. This lets the user change cadence
 * from the UI without redeploying.
 *
 * The provider object itself is mostly informational — there is no remote API to
 * call because the schedule lives in our own database.
 */

import { loadOrInitScheduleSettings } from "../scheduleSettings";
import { describeSchedule } from "../calculateNextRun";
import type {
  RegisterScheduleInput,
  RegisterScheduleResult,
  ScheduleStatus,
  SchedulerProvider,
  GetScheduleStatusInput,
  DisableScheduleInput,
  UpdateScheduleInput,
  UpdateScheduleResult,
} from "../provider";

export const databaseScheduler: SchedulerProvider = {
  name: "database",

  async registerSchedule(_input: RegisterScheduleInput): Promise<RegisterScheduleResult> {
    return { providerScheduleId: null, registeredAt: new Date() };
  },

  async updateSchedule(_input: UpdateScheduleInput): Promise<UpdateScheduleResult> {
    return { providerScheduleId: null, registeredAt: new Date() };
  },

  async disableSchedule(_input: DisableScheduleInput): Promise<void> {
    /* DB-driven scheduler has nothing external to disable. */
  },

  async getScheduleStatus(input: GetScheduleStatusInput): Promise<ScheduleStatus> {
    // For Sprint 1 we only have one schedule per user; treat scheduleId as userId.
    const s = await loadOrInitScheduleSettings(input.scheduleId);
    return {
      enabled: s.enabled,
      lastInvocationAt: s.lastRunAt,
      nextInvocationAt: s.nextRunAt,
      description: describeSchedule(s),
    };
  },
};
