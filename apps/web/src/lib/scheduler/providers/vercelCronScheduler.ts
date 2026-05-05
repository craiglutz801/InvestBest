/**
 * Vercel Cron provider (Strategy Upgrade §6.2 / §8).
 *
 * Vercel Cron is configured statically in `vercel.json` and cannot be reprogrammed
 * from the Settings UI — that limitation is exactly why §7.1 of the spec recommends
 * the "static external heartbeat + dynamic database schedule" pattern. The cron
 * fires hourly (or whatever you set in `vercel.json`) at `/api/internal/scheduler-tick`,
 * which then reads `AgentScheduleSettings` and decides whether each user's run is due.
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
  "Vercel Cron is configured at deploy time in apps/web/vercel.json (path = /api/internal/scheduler-tick).",
  "Per-user cadence is read live from AgentScheduleSettings; the cron entry is just the heartbeat.",
  "If you need sub-hourly cadence, ensure your Vercel plan supports it or switch SCHEDULER_PROVIDER to triggerdev.",
].join(" ");

export const vercelCronScheduler: SchedulerProvider = {
  name: "vercel-cron",

  async registerSchedule(_input: RegisterScheduleInput): Promise<RegisterScheduleResult> {
    if (process.env.NODE_ENV !== "production") console.warn(`[vercel-cron] ${NOTE}`);
    return { providerScheduleId: null, registeredAt: new Date() };
  },

  async updateSchedule(_input: UpdateScheduleInput): Promise<UpdateScheduleResult> {
    if (process.env.NODE_ENV !== "production") console.warn(`[vercel-cron] ${NOTE}`);
    return { providerScheduleId: null, registeredAt: new Date() };
  },

  async disableSchedule(_input: DisableScheduleInput): Promise<void> {
    /* Disable by removing the entry from vercel.json and redeploying. */
  },

  async getScheduleStatus(_input: GetScheduleStatusInput): Promise<ScheduleStatus> {
    return {
      enabled: true,
      lastInvocationAt: null,
      nextInvocationAt: null,
      description: NOTE,
    };
  },
};
