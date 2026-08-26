import { describe, expect, it } from "vitest";
import { assertPaperExecutionMode, ExecutionModeError, resolveExecutionMode } from "./executionMode";

describe("EXECUTION_MODE paper boundary", () => {
  it("allows only paper", () => {
    expect(resolveExecutionMode({ EXECUTION_MODE: "paper" })).toEqual({
      ok: true,
      mode: "paper",
      raw: "paper",
    });
    expect(resolveExecutionMode({ EXECUTION_MODE: " PAPER " }).ok).toBe(true);
  });

  it("fails closed when missing", () => {
    const r = resolveExecutionMode({});
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe("EXECUTION_MODE_MISSING");
  });

  it("fails closed when empty", () => {
    const r = resolveExecutionMode({ EXECUTION_MODE: "   " });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.reason).toBe("EXECUTION_MODE_MISSING");
  });

  it.each(["live", "LIVE", "production", "broker", "real-money", "alpaca", "shadow", "dry_run", "true"])(
    "rejects non-paper value %s",
    (value) => {
      const r = resolveExecutionMode({ EXECUTION_MODE: value });
      expect(r.ok).toBe(false);
      if (!r.ok) expect(["EXECUTION_MODE_INVALID", "EXECUTION_MODE_NOT_PAPER"]).toContain(r.reason);
    },
  );

  it("assertPaperExecutionMode throws before mutation", () => {
    expect(() => assertPaperExecutionMode({})).toThrow(ExecutionModeError);
    expect(() => assertPaperExecutionMode({ EXECUTION_MODE: "live" })).toThrow(/not allowed/);
    expect(assertPaperExecutionMode({ EXECUTION_MODE: "paper" })).toBe("paper");
  });
});
