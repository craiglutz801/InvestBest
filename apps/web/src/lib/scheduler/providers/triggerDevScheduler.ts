/**
 * Trigger.dev provider stub (Strategy Upgrade §6.1 / §9).
 *
 * Sprint 1 scope: typed adapter only — the actual Trigger.dev SDK wiring belongs
 * to a dedicated sprint where we set up `@trigger.dev/sdk`, register a scheduled
 * task that calls `/api/internal/scheduler-tick`, configure concurrency, and
 * forward retries / logging into our `DecisionRun` records.
 *
 * Until then, this provider acknowledges configuration calls and points operators
 * at the scheduler-tick endpoint they should configure their Trigger.dev task to
 * call. The database-driven scheduler still works — Trigger.dev just becomes the
 * external heartbeat.
 */

import type {
  DisableScheduleInput,
  GetScheduleStatusInput,
  RegisterScheduleInput,
  RegisterScheduleResult,
  ScheduleStatus,
  SchedulerProvider,
  UpdateScheduleInput,
  UpdateScheduleResult,
} from "../provider";

const NOTE = [
  "Trigger.dev provider not yet wired in Sprint 1.",
  "Configure your Trigger.dev project's hourly scheduled task to POST",
  "/api/internal/scheduler-tick with header x-investbest-secret = INVESTBEST_INTERNAL_SECRET.",
].join(" ");

export const triggerDevScheduler: SchedulerProvider = {
  name: "triggerdev",

  async registerSchedule(_input: RegisterScheduleInput): Promise<RegisterScheduleResult> {
    if (process.env.NODE_ENV !== "production") console.warn(`[triggerdev] ${NOTE}`);
    return { providerScheduleId: null, registeredAt: new Date() };
  },

  async updateSchedule(_input: UpdateScheduleInput): Promise<UpdateScheduleResult> {
    if (process.env.NODE_ENV !== "production") console.warn(`[triggerdev] ${NOTE}`);
    return { providerScheduleId: null, registeredAt: new Date() };
  },

  async disableSchedule(_input: DisableScheduleInput): Promise<void> {
    /* deferred */
  },

  async getScheduleStatus(_input: GetScheduleStatusInput): Promise<ScheduleStatus> {
    return {
      enabled: false,
      lastInvocationAt: null,
      nextInvocationAt: null,
      description: NOTE,
    };
  },
};
