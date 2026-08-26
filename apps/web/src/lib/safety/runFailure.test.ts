import { describe, expect, it } from "vitest";

/** Pure helper mirroring hourlyMarketAgent failure bookkeeping. */
export function buildFailedRunPatch(error: unknown, now = new Date()) {
  const msg = error instanceof Error ? error.message : String(error);
  return {
    status: "failed" as const,
    finishedAt: now,
    error: msg,
    mutatePositions: false as const,
  };
}

describe("run failure bookkeeping", () => {
  it("marks the run failed without authorizing position mutation", () => {
    const patch = buildFailedRunPatch(new Error("ingest exploded"), new Date("2026-08-26T15:00:00Z"));
    expect(patch.status).toBe("failed");
    expect(patch.mutatePositions).toBe(false);
    expect(patch.error).toBe("ingest exploded");
    expect(patch.finishedAt.toISOString()).toBe("2026-08-26T15:00:00.000Z");
  });
});
