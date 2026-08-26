import { describe, expect, it } from "vitest";
import { isEnvKillSwitchOn, readSettingsPaused, resolveOperatorPause } from "./operatorPause";

describe("operator pause / kill switch", () => {
  it("is off by default", () => {
    expect(resolveOperatorPause({ settings: {}, env: {} })).toEqual({ paused: false });
    expect(readSettingsPaused({})).toBe(false);
    expect(isEnvKillSwitchOn({})).toBe(false);
  });

  it("pauses from settings without implying history deletion", () => {
    const r = resolveOperatorPause({ settings: { agentPaused: true }, env: {} });
    expect(r.paused).toBe(true);
    if (r.paused) {
      expect(r.source).toBe("settings");
      expect(r.detail).toMatch(/history is preserved/i);
    }
  });

  it("treats env kill switch as pause", () => {
    expect(isEnvKillSwitchOn({ AGENT_PAUSE: "true" })).toBe(true);
    expect(isEnvKillSwitchOn({ AGENT_KILL_SWITCH: "1" })).toBe(true);
    expect(isEnvKillSwitchOn({ AGENT_PAUSE: "false" })).toBe(false);
    const r = resolveOperatorPause({ settings: { agentPaused: false }, env: { AGENT_KILL_SWITCH: "yes" } });
    expect(r.paused).toBe(true);
    if (r.paused) expect(r.source).toBe("env_kill_switch");
  });

  it("env kill switch wins even if settings pause is off", () => {
    const r = resolveOperatorPause({ settings: { agentPaused: false }, env: { AGENT_PAUSE: "on" } });
    expect(r.paused).toBe(true);
    if (r.paused) expect(r.source).toBe("env_kill_switch");
  });
});
