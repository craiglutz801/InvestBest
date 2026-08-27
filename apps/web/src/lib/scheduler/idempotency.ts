import type { TriggerSource } from "./types";

export function hourBucketKey(d: Date): string {
  return `${d.toISOString().slice(0, 13)}`;
}

export function defaultIdempotencyKey(input: {
  triggerSource: TriggerSource;
  userId: string;
  scheduleId: string | null;
  now: Date;
}): string {
  const hourBucket = hourBucketKey(input.now);
  if (input.triggerSource === "manual") return `manual-${input.userId}-${input.now.getTime()}`;
  if (input.scheduleId) return `${input.userId}:${input.scheduleId}:${hourBucket}`;
  return `${input.userId}-${hourBucket}`;
}

export type LockHoldState = {
  status: string;
  expiresAt: Date;
};

/** True when another trigger must not start a second decision run. */
export function isLockStillHeld(existing: LockHoldState, now: Date): boolean {
  return existing.status === "active" && existing.expiresAt.getTime() > now.getTime();
}

export function canStealLock(existing: LockHoldState, now: Date): boolean {
  return !isLockStillHeld(existing, now);
}

/** Hourly/scheduled completed runs must not create a second trade set for the same key. */
export function shouldSkipDuplicateHourlyRun(
  existing: { status: string } | null | undefined,
  trigger: "hourly" | "manual",
): boolean {
  return trigger === "hourly" && existing?.status === "completed";
}
