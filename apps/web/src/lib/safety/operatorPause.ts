/**
 * Operator pause / kill switch.
 *
 * Pauses new agent runs without deleting DecisionRun / PaperTrade / position
 * history. Either source is sufficient to block:
 *   - AppSettings.agentPaused (operator UI)
 *   - AGENT_PAUSE=true or AGENT_KILL_SWITCH=true (emergency env kill)
 */

export type PauseSource = "settings" | "env_kill_switch";

export type PauseDecision =
  | { paused: false }
  | { paused: true; source: PauseSource; detail: string };

function envFlagTrue(value: string | undefined): boolean {
  if (value == null) return false;
  const v = value.trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "on";
}

export function isEnvKillSwitchOn(env: NodeJS.Dict<string> = process.env): boolean {
  return envFlagTrue(env.AGENT_PAUSE) || envFlagTrue(env.AGENT_KILL_SWITCH);
}

export function readSettingsPaused(settings: object | null | undefined): boolean {
  if (settings == null) return false;
  const raw = (settings as Record<string, unknown>).agentPaused;
  return raw === true;
}

export function resolveOperatorPause(input: {
  settings?: object | null;
  env?: NodeJS.Dict<string>;
}): PauseDecision {
  const env = input.env ?? process.env;
  if (isEnvKillSwitchOn(env)) {
    return {
      paused: true,
      source: "env_kill_switch",
      detail:
        "Agent kill switch is on (AGENT_PAUSE / AGENT_KILL_SWITCH). New runs are blocked; history is preserved.",
    };
  }
  if (readSettingsPaused(input.settings)) {
    return {
      paused: true,
      source: "settings",
      detail: "Operator pause is on (Settings → Pause agent). New runs are blocked; history is preserved.",
    };
  }
  return { paused: false };
}
