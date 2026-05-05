/**
 * SchedulerProvider abstraction (Strategy Upgrade §6).
 *
 * The InvestBest scheduler can be driven by Trigger.dev, Vercel Cron, an external
 * cron, or simple database polling. Routes never talk to a provider directly —
 * they call `runInvestBestAgent` / `triggerAgentRun` and read schedule state from
 * the database. Providers only register the *external heartbeat* that pings
 * `/api/internal/scheduler-tick` (or equivalent).
 *
 * Sprint 1 ships:
 *   - `databaseScheduler` (always available; relies on whatever external cron is
 *     configured to call `/api/internal/scheduler-tick`).
 *   - `triggerDevScheduler` (typed adapter — implementation deferred to a Trigger.dev
 *     wiring sprint).
 *   - `vercelCronScheduler` (typed adapter — `vercel.json` is the config surface).
 */

export type RegisterScheduleInput = {
  scheduleId: string;
  cadenceMinutes: number;
  webhookPath: string;
  metadata?: Record<string, unknown>;
};

export type RegisterScheduleResult = {
  providerScheduleId: string | null;
  registeredAt: Date;
};

export type UpdateScheduleInput = RegisterScheduleInput;
export type UpdateScheduleResult = RegisterScheduleResult;

export type DisableScheduleInput = { scheduleId: string };

export type GetScheduleStatusInput = { scheduleId: string };
export type ScheduleStatus = {
  enabled: boolean;
  lastInvocationAt: Date | null;
  nextInvocationAt: Date | null;
  description: string;
};

export interface SchedulerProvider {
  name: string;
  registerSchedule(input: RegisterScheduleInput): Promise<RegisterScheduleResult>;
  updateSchedule(input: UpdateScheduleInput): Promise<UpdateScheduleResult>;
  disableSchedule(input: DisableScheduleInput): Promise<void>;
  getScheduleStatus(input: GetScheduleStatusInput): Promise<ScheduleStatus>;
}

export type ProviderName = "database" | "triggerdev" | "vercel-cron";

/**
 * Active provider — read once at module load. Defaults to "database" because that
 * works in any deployment that can reach `/api/internal/scheduler-tick`.
 */
export function activeProviderName(): ProviderName {
  const raw = (process.env.SCHEDULER_PROVIDER ?? "").toLowerCase();
  if (raw === "triggerdev" || raw === "trigger.dev") return "triggerdev";
  if (raw === "vercel" || raw === "vercel-cron" || raw === "vercelcron") return "vercel-cron";
  return "database";
}
