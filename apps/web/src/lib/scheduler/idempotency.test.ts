import { describe, expect, it } from "vitest";
import {
  canStealLock,
  defaultIdempotencyKey,
  hourBucketKey,
  isLockStillHeld,
  shouldSkipDuplicateHourlyRun,
} from "./idempotency";

describe("run idempotency keys", () => {
  const now = new Date("2026-08-26T15:30:00.000Z");

  it("buckets scheduled triggers to the UTC hour so duplicates collapse", () => {
    const a = defaultIdempotencyKey({
      triggerSource: "scheduled",
      userId: "u1",
      scheduleId: "s1",
      now,
    });
    const laterSameHour = defaultIdempotencyKey({
      triggerSource: "scheduled",
      userId: "u1",
      scheduleId: "s1",
      now: new Date("2026-08-26T15:59:59.000Z"),
    });
    const nextHour = defaultIdempotencyKey({
      triggerSource: "scheduled",
      userId: "u1",
      scheduleId: "s1",
      now: new Date("2026-08-26T16:00:00.000Z"),
    });
    expect(a).toBe("u1:s1:2026-08-26T15");
    expect(laterSameHour).toBe(a);
    expect(nextHour).not.toBe(a);
    expect(hourBucketKey(now)).toBe("2026-08-26T15");
  });

  it("gives concurrent scheduled triggers the same key", () => {
    const keys = Array.from({ length: 8 }, () =>
      defaultIdempotencyKey({ triggerSource: "scheduled", userId: "u1", scheduleId: "s1", now }),
    );
    expect(new Set(keys).size).toBe(1);
  });
});

describe("run lock hold / steal", () => {
  const now = new Date("2026-08-26T15:30:00.000Z");

  it("holds an unexpired active lock so a concurrent trigger cannot duplicate trades", () => {
    expect(
      isLockStillHeld({ status: "active", expiresAt: new Date("2026-08-26T16:00:00.000Z") }, now),
    ).toBe(true);
    expect(
      canStealLock({ status: "active", expiresAt: new Date("2026-08-26T16:00:00.000Z") }, now),
    ).toBe(false);
  });

  it("allows steal of expired or released locks", () => {
    expect(canStealLock({ status: "active", expiresAt: new Date("2026-08-26T15:00:00.000Z") }, now)).toBe(true);
    expect(canStealLock({ status: "released", expiresAt: new Date("2026-08-26T16:00:00.000Z") }, now)).toBe(true);
    expect(canStealLock({ status: "expired", expiresAt: new Date("2026-08-26T16:00:00.000Z") }, now)).toBe(true);
  });
});

describe("duplicate hourly run skip", () => {
  it("skips a completed hourly run with the same idempotency key", () => {
    expect(shouldSkipDuplicateHourlyRun({ status: "completed" }, "hourly")).toBe(true);
    expect(shouldSkipDuplicateHourlyRun({ status: "running" }, "hourly")).toBe(false);
    expect(shouldSkipDuplicateHourlyRun({ status: "completed" }, "manual")).toBe(false);
    expect(shouldSkipDuplicateHourlyRun(null, "hourly")).toBe(false);
  });
});
