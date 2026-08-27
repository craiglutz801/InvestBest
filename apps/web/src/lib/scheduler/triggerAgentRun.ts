/**
 * Shared agent-run orchestrator.
 *
 * Strategy Upgrade §1.5 — every trigger source (manual button, scheduler tick,
 * future retry / research / shadow / backtest paths) MUST flow through this
 * single function so we can:
 *
 *   1. Acquire the per-user run lock (prevents overlapping runs across triggers).
 *   2. Persist `triggerSource` + `runMode` + `scheduleId` + `lockId` on the
 *      resulting `DecisionRun` row.
 *   3. Update `AgentScheduleSettings` bookkeeping (lastRunAt / lastRunStatus /
 *      lastRunError / nextRunAt) so the UI tells the truth.
 *   4. Release the lock on success / failure / timeout.
 *
 * The legacy `runHourlyMarketAgent` orchestrator stays — this wrapper just adds
 * the lock + bookkeeping around it.
 */

import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { runHourlyMarketAgent } from "@/lib/jobs/hourlyMarketAgent";
import { admitPaperAgentRun } from "@/lib/safety/runAdmission";
import { defaultIdempotencyKey } from "./idempotency";
import {
  acquireRunLock,
  attachRunIdToLock,
  expireStaleLocks,
  releaseRunLock,
} from "./runLock";
import {
  loadOrInitScheduleSettings,
  recordScheduleRunResult,
} from "./scheduleSettings";
import type { RunOutcome, TriggerSource, RunMode } from "./types";

async function loadAppSettingsForAdmission(userId: string): Promise<object | null> {
  try {
    return await prisma.appSettings.findUnique({ where: { userId } });
  } catch {
    return null;
  }
}

async function persistAdmissionSkip(args: {
  userId: string;
  triggerSource: TriggerSource;
  status: "blocked_execution_mode" | "skipped_paused";
  reason: string;
  detail: string;
}): Promise<string | null> {
  try {
    const row = await prisma.decisionRun.create({
      data: {
        userId: args.userId,
        status: args.status === "blocked_execution_mode" ? "failed" : "skipped",
        universeSize: 0,
        triggerSource: args.triggerSource,
        runMode: "paper_trade",
        notesJson: JSON.stringify({
          progress: [],
          error: args.detail,
          admission: { reason: args.reason, status: args.status },
        }),
      },
    });
    return row.id;
  } catch {
    return null;
  }
}

/**
 * Pre-create the DecisionRun row so the wrapper can return a real `runId` to
 * the caller *before* the background pipeline starts. The pipeline itself
 * (`runHourlyMarketAgent`, called with the same idempotencyKey) will find this
 * row and update it to `running` instead of creating a new one.
 */
async function preCreateDecisionRun(args: {
  userId: string;
  triggerSource: TriggerSource;
  runMode: RunMode;
  scheduleId: string | null;
  lockId: string | null;
  strategyVersionId: string | null;
  searchProfileId: string | null;
  idempotencyKey: string;
}): Promise<string> {
  const existing = await prisma.decisionRun.findUnique({ where: { idempotencyKey: args.idempotencyKey } });
  if (existing) return existing.id;
  try {
    const created = await prisma.decisionRun.create({
      data: {
        userId: args.userId,
        idempotencyKey: args.idempotencyKey,
        status: "queued",
        universeSize: 0,
        triggerSource: args.triggerSource,
        runMode: args.runMode,
        scheduleId: args.scheduleId,
        lockId: args.lockId,
        strategyVersionId: args.strategyVersionId,
        searchProfileId: args.searchProfileId,
        notesJson: JSON.stringify({ progress: [] }),
      },
    });
    return created.id;
  } catch (e) {
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2002") {
      const raced = await prisma.decisionRun.findUnique({ where: { idempotencyKey: args.idempotencyKey } });
      if (raced) return raced.id;
    }
    throw e;
  }
}

export type TriggerAgentRunInput = {
  userId: string;
  triggerSource: TriggerSource;
  runMode?: RunMode;
  scheduleId?: string | null;
  /** Optional override for idempotency key (scheduler-tick uses `${userId}:${scheduleId}:${hourBucket}`). */
  idempotencyKey?: string;
  /**
   * `true` (default) means start the pipeline asynchronously and return immediately.
   * `false` means await the entire pipeline before returning (useful for the internal
   * cron route which has a longer maxDuration budget and wants accurate status).
   */
  background?: boolean;
  /**
   * Pass Next.js `after` from `next/server` so the lock is held across the whole
   * deferred pipeline (not released the moment the HTTP response is sent).
   */
  scheduleAfter?: (task: () => void | Promise<void>) => void;
  strategyVersionId?: string | null;
  searchProfileId?: string | null;
  /** When true, ignore an existing lock and force-acquire (manual force button). */
  force?: boolean;
};

export async function triggerAgentRun(input: TriggerAgentRunInput): Promise<RunOutcome> {
  const {
    userId,
    triggerSource,
    runMode = "paper_trade",
    scheduleId = null,
    idempotencyKey: providedIdempotencyKey,
    background = true,
    scheduleAfter,
    strategyVersionId = null,
    searchProfileId = null,
    force = false,
  } = input;

  const schedule = await loadOrInitScheduleSettings(userId);
  const idempotencyKey =
    providedIdempotencyKey ??
    defaultIdempotencyKey({ triggerSource, userId, scheduleId, now: new Date() });

  const admission = admitPaperAgentRun({
    env: process.env,
    settings: await loadAppSettingsForAdmission(userId),
  });
  if (!admission.allowed) {
    const skipRunId = await persistAdmissionSkip({
      userId,
      triggerSource,
      status: admission.status,
      reason: admission.reason,
      detail: admission.detail,
    });
    await recordScheduleRunResult(userId, {
      runId: skipRunId,
      status: "skipped",
      error: admission.detail,
    }).catch(() => undefined);
    return {
      runId: skipRunId,
      status: admission.status,
      error: admission.detail,
      triggerSource,
      scheduleId,
      lockId: null,
    };
  }

  // Expire any stale "active" locks past their expiry before trying to acquire.
  // Without this, a crashed/aborted run (e.g. a `pm2 restart` mid-pipeline) wedges
  // every subsequent manual click until expiresAt is reached.
  await expireStaleLocks().catch(() => undefined);

  // 1) Acquire per-user lock unless caller is forcing.
  let lockId: string | null = null;
  if (!force) {
    const lock = await acquireRunLock(userId, {
      triggerSource,
      timeoutMinutes: schedule.maxRunDurationMinutes,
    });
    if (!lock.acquired) {
      // Lock held by an in-flight run. Mirror "skipped" status on the schedule
      // so the dashboard shows what happened.
      await recordScheduleRunResult(userId, {
        runId: null,
        status: "skipped",
        error: `Skipped: another run is already active (lock acquired ${lock.existing.acquiredAt.toISOString()}, expires ${lock.existing.expiresAt.toISOString()}).`,
      }).catch(() => undefined);
      return {
        runId: lock.existing.runId ?? null,
        status: "skipped_in_progress",
        triggerSource,
        scheduleId,
        lockId: lock.existing.id,
        error: `Another run is already in progress (started ${lock.existing.acquiredAt.toISOString()}). It will release automatically by ${lock.existing.expiresAt.toISOString()}.`,
      };
    }
    lockId = lock.lock.id;
  }

  const trigger = triggerSource === "manual" ? "manual" : "hourly";

  // Pre-create the DecisionRun row so we can return a real runId synchronously
  // (the legacy AgentRunMonitor and dashboard cards both poll on it). The
  // pipeline itself will find this row by idempotencyKey and update it.
  let preCreatedRunId: string | null = null;
  try {
    preCreatedRunId = await preCreateDecisionRun({
      userId,
      triggerSource,
      runMode,
      scheduleId,
      lockId,
      strategyVersionId,
      searchProfileId,
      idempotencyKey,
    });
    if (lockId && preCreatedRunId) {
      await attachRunIdToLock(lockId, preCreatedRunId).catch(() => undefined);
    }
  } catch (e) {
    // If we couldn't pre-create, release the lock and bail — better than a stuck UI.
    if (lockId) {
      await releaseRunLock(lockId, { runId: null, status: "released" }).catch(() => undefined);
    }
    const msg = e instanceof Error ? e.message : String(e);
    await recordScheduleRunResult(userId, { runId: null, status: "failed", error: msg }).catch(() => undefined);
    return {
      runId: null,
      status: "failed",
      error: msg,
      triggerSource,
      scheduleId,
      lockId: null,
    };
  }

  const finalize = async (
    runId: string | null,
    status: "success" | "failed" | "timeout" | "skipped",
    error?: string,
  ) => {
    if (lockId) {
      await releaseRunLock(lockId, {
        runId,
        status: status === "timeout" ? "timeout" : "released",
      });
    }
    await recordScheduleRunResult(userId, { runId, status, error: error ?? null }).catch(() => undefined);
  };

  if (!background) {
    try {
      const r = await runHourlyMarketAgent(userId, {
        trigger,
        wait: true,
        triggerSource,
        runMode,
        scheduleId,
        lockId,
        strategyVersionId,
        searchProfileId,
        idempotencyKey,
      });
      await finalize(r.runId, "success");
      return {
        runId: r.runId,
        status: "completed",
        triggerSource,
        scheduleId,
        lockId,
      };
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      await finalize(preCreatedRunId, "failed", msg);
      return {
        runId: preCreatedRunId,
        status: "failed",
        error: msg,
        triggerSource,
        scheduleId,
        lockId,
      };
    }
  }

  // background = true: kick off the pipeline after the response is sent.
  const deferred = async () => {
    try {
      const r = await runHourlyMarketAgent(userId, {
        trigger,
        wait: true,
        triggerSource,
        runMode,
        scheduleId,
        lockId,
        strategyVersionId,
        searchProfileId,
        idempotencyKey,
      });
      await finalize(r.runId, "success");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      await finalize(preCreatedRunId, "failed", msg);
      console.error("[triggerAgentRun] background pipeline failed", e);
    }
  };

  if (scheduleAfter) {
    scheduleAfter(deferred);
  } else {
    void deferred();
  }

  return {
    runId: preCreatedRunId,
    status: "started",
    triggerSource,
    scheduleId,
    lockId,
  };
}
