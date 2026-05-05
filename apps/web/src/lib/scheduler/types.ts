/**
 * Shared types for the InvestBest agent scheduler subsystem.
 * Strategy Upgrade spec — §1, §3, §6.
 *
 * The scheduler is intentionally *additive* on top of the existing
 * `runHourlyMarketAgent` orchestrator: every trigger source (manual button,
 * scheduled tick, future retry/research/shadow/backtest paths) flows through
 * a single shared wrapper (`runInvestBestAgent` / `triggerAgentRun`) that:
 *
 *   1. acquires a per-user run lock,
 *   2. records `triggerSource` + `runMode` on the resulting DecisionRun,
 *   3. updates AgentScheduleSettings bookkeeping on completion,
 *   4. releases the lock on success / failure / timeout.
 */

/** Source of a run as persisted on `DecisionRun.triggerSource`. */
export type TriggerSource =
  | "manual"
  | "scheduled"
  | "retry"
  | "research"
  | "shadow"
  | "backtest";

/** Persisted on `DecisionRun.runMode`. Paper-trade is the default; the others are placeholders for future sprints. */
export type RunMode = "paper_trade" | "dry_run" | "shadow" | "backtest";

/** Persisted on `AgentScheduleSettings.lastRunStatus`. */
export type ScheduleRunStatus = "success" | "failed" | "skipped" | "running" | "timeout";

/**
 * Schedule presets surfaced in the UI. `custom` falls back to `customCronExpression`
 * (currently informational only — `calculateNextRun` does not yet parse arbitrary cron).
 */
export type SchedulePreset =
  | "every_15_min"
  | "every_30_min"
  | "hourly"
  | "every_2h"
  | "every_4h"
  | "daily_after_close"
  | "daily_before_open"
  | "custom";

export type ScheduleSettings = {
  id: string;
  userId: string;
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
  nextRunAt: Date | null;
  lastRunAt: Date | null;
  lastRunStatus: ScheduleRunStatus | null;
  lastRunError: string | null;
  lastRunId: string | null;
};

export type RunLock = {
  id: string;
  userId: string;
  lockKey: string;
  acquiredAt: Date;
  expiresAt: Date;
  releasedAt: Date | null;
  runId: string | null;
  status: "active" | "released" | "expired" | "timeout";
  triggerSource: string | null;
};

export type RunOutcome = {
  runId: string | null;
  status:
    | "started"
    | "completed"
    | "skipped_in_progress"
    | "skipped_not_due"
    | "skipped_market_closed"
    | "skipped_disabled"
    | "skipped_duplicate"
    | "failed";
  error?: string;
  triggerSource: TriggerSource;
  scheduleId?: string | null;
  lockId?: string | null;
};
