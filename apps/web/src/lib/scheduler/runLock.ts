/**
 * Per-user run lock for the InvestBest agent.
 *
 * Strategy Upgrade §3.2 / §12.2 — guarantees only one agent run is active per
 * user at a time, regardless of trigger source (manual button, hourly cron tick,
 * Trigger.dev job, retry, etc). The lock auto-expires after `expiresAt` so a
 * crashed run can't wedge the system.
 *
 * Implementation: `AgentRunLock.lockKey` is a unique column. We try to insert
 * with `lockKey = "agent:user:<userId>"`. If insert succeeds the caller holds
 * the lock. If it fails because of the unique constraint we look at the existing
 * row: if it's already expired or released we steal it; otherwise we report the
 * lock as already held.
 */

import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";
import { isLockStillHeld } from "./idempotency";
import type { RunLock, TriggerSource } from "./types";

const DEFAULT_TIMEOUT_MIN = Math.max(
  1,
  Number(process.env.AGENT_RUN_LOCK_TIMEOUT_MINUTES) || 30,
);

export function lockKeyForUser(userId: string): string {
  return `agent:user:${userId}`;
}

function rowToLock(row: {
  id: string;
  userId: string;
  lockKey: string;
  acquiredAt: Date;
  expiresAt: Date;
  releasedAt: Date | null;
  runId: string | null;
  status: string;
  triggerSource: string | null;
}): RunLock {
  const status: RunLock["status"] =
    row.status === "released" || row.status === "expired" || row.status === "timeout"
      ? row.status
      : "active";
  return { ...row, status };
}

export type AcquireLockResult =
  | { acquired: true; lock: RunLock }
  | { acquired: false; existing: RunLock; reason: "already_active" };

export async function acquireRunLock(
  userId: string,
  options?: {
    triggerSource?: TriggerSource | string;
    timeoutMinutes?: number;
    runId?: string | null;
  },
): Promise<AcquireLockResult> {
  const lockKey = lockKeyForUser(userId);
  const timeoutMinutes = Math.max(1, options?.timeoutMinutes ?? DEFAULT_TIMEOUT_MIN);
  const now = new Date();
  const expiresAt = new Date(now.getTime() + timeoutMinutes * 60_000);

  try {
    const created = await prisma.agentRunLock.create({
      data: {
        userId,
        lockKey,
        acquiredAt: now,
        expiresAt,
        runId: options?.runId ?? null,
        status: "active",
        triggerSource: options?.triggerSource ?? null,
      },
    });
    return { acquired: true, lock: rowToLock(created) };
  } catch (e) {
    // P2002 = unique constraint violation. Anything else propagates.
    if (!(e instanceof Prisma.PrismaClientKnownRequestError) || e.code !== "P2002") {
      throw e;
    }
  }

  const existing = await prisma.agentRunLock.findUnique({ where: { lockKey } });
  if (!existing) {
    // Lost the race; try one more time.
    const retry = await prisma.agentRunLock.create({
      data: {
        userId,
        lockKey,
        acquiredAt: now,
        expiresAt,
        runId: options?.runId ?? null,
        status: "active",
        triggerSource: options?.triggerSource ?? null,
      },
    });
    return { acquired: true, lock: rowToLock(retry) };
  }

  if (isLockStillHeld(existing, now)) {
    return { acquired: false, existing: rowToLock(existing), reason: "already_active" };
  }

  // Stale — steal atomically so two concurrent recoveries cannot both win.
  const stolenCount = await prisma.agentRunLock.updateMany({
    where: {
      lockKey,
      OR: [{ status: { not: "active" } }, { expiresAt: { lte: now } }],
    },
    data: {
      acquiredAt: now,
      expiresAt,
      releasedAt: null,
      runId: options?.runId ?? null,
      status: "active",
      triggerSource: options?.triggerSource ?? null,
    },
  });
  if (stolenCount.count === 0) {
    const current = await prisma.agentRunLock.findUnique({ where: { lockKey } });
    if (current) {
      return { acquired: false, existing: rowToLock(current), reason: "already_active" };
    }
    const retryAfterSteal = await prisma.agentRunLock.create({
      data: {
        userId,
        lockKey,
        acquiredAt: now,
        expiresAt,
        runId: options?.runId ?? null,
        status: "active",
        triggerSource: options?.triggerSource ?? null,
      },
    });
    return { acquired: true, lock: rowToLock(retryAfterSteal) };
  }
  const stolen = await prisma.agentRunLock.findUnique({ where: { lockKey } });
  if (!stolen) {
    return { acquired: false, existing: rowToLock(existing), reason: "already_active" };
  }
  return { acquired: true, lock: rowToLock(stolen) };
}

export async function releaseRunLock(
  lockId: string,
  options?: { runId?: string | null; status?: "released" | "timeout" },
): Promise<void> {
  await prisma.agentRunLock
    .update({
      where: { id: lockId },
      data: {
        status: options?.status ?? "released",
        releasedAt: new Date(),
        runId: options?.runId ?? undefined,
      },
    })
    .catch(() => {
      /* lock may already be gone — release is best-effort. */
    });
}

export async function attachRunIdToLock(lockId: string, runId: string): Promise<void> {
  await prisma.agentRunLock
    .update({ where: { id: lockId }, data: { runId } })
    .catch(() => {
      /* best-effort. */
    });
}

/**
 * Periodic housekeeping helper called from the scheduler tick — marks any
 * still-"active" locks past their expiry as `expired`. Without this, the
 * dashboard would show a phantom "running" forever for a crashed run.
 */
export async function expireStaleLocks(now: Date = new Date()): Promise<number> {
  const staleLocks = await prisma.agentRunLock.findMany({
    where: { status: "active", expiresAt: { lt: now } },
    select: { id: true, runId: true },
  });
  if (staleLocks.length === 0) return 0;

  await prisma.agentRunLock.updateMany({
    where: { id: { in: staleLocks.map((lock) => lock.id) } },
    data: { status: "expired", releasedAt: now },
  });

  const staleRunIds = staleLocks.map((lock) => lock.runId).filter((runId): runId is string => Boolean(runId));
  if (staleRunIds.length > 0) {
    await prisma.decisionRun.updateMany({
      where: { id: { in: staleRunIds }, status: "running" },
      data: {
        status: "failed",
        finishedAt: now,
      },
    });
  }

  return staleLocks.length;
}
