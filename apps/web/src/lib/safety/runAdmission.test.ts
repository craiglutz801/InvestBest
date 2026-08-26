import { describe, expect, it } from "vitest";
import { admitPaperAgentRun } from "./runAdmission";

describe("paper agent admission", () => {
  it("allows a paper run when pause is off", () => {
    const r = admitPaperAgentRun({ env: { EXECUTION_MODE: "paper" }, settings: { agentPaused: false } });
    expect(r).toEqual({ allowed: true, executionMode: "paper" });
  });

  it("blocks missing execution mode before pause is considered", () => {
    const r = admitPaperAgentRun({ env: {}, settings: { agentPaused: true } });
    expect(r.allowed).toBe(false);
    if (!r.allowed) {
      expect(r.status).toBe("blocked_execution_mode");
      expect(r.mutatePositions).toBe(false);
      expect(r.reason).toBe("EXECUTION_MODE_MISSING");
    }
  });

  it("blocks live mode even if the operator did not pause", () => {
    const r = admitPaperAgentRun({ env: { EXECUTION_MODE: "live" }, settings: { agentPaused: false } });
    expect(r.allowed).toBe(false);
    if (!r.allowed) {
      expect(r.status).toBe("blocked_execution_mode");
      expect(r.mutatePositions).toBe(false);
    }
  });

  it("skips when paused after paper mode is confirmed", () => {
    const r = admitPaperAgentRun({ env: { EXECUTION_MODE: "paper" }, settings: { agentPaused: true } });
    expect(r.allowed).toBe(false);
    if (!r.allowed) {
      expect(r.status).toBe("skipped_paused");
      expect(r.mutatePositions).toBe(false);
      expect(r.pauseSource).toBe("settings");
    }
  });
});
