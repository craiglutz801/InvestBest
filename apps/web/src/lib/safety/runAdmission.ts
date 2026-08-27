import { resolveExecutionMode, type ExecutionModeBlockReason } from "./executionMode";
import { resolveOperatorPause, type PauseSource } from "./operatorPause";

export type AdmissionBlockReason = ExecutionModeBlockReason | "AGENT_PAUSED";

export type RunAdmission =
  | { allowed: true; executionMode: "paper" }
  | {
      allowed: false;
      status: "blocked_execution_mode" | "skipped_paused";
      reason: AdmissionBlockReason;
      pauseSource?: PauseSource;
      detail: string;
      mutatePositions: false;
    };

/**
 * Fail-closed gate evaluated before lock acquisition and before any paper
 * position mutation. Execution mode is checked first so a misconfigured
 * runtime cannot trade even if the operator pause is off.
 */
export function admitPaperAgentRun(input?: {
  env?: NodeJS.Dict<string>;
  settings?: object | null;
}): RunAdmission {
  const env = input?.env ?? process.env;
  const execution = resolveExecutionMode(env);
  if (!execution.ok) {
    return {
      allowed: false,
      status: "blocked_execution_mode",
      reason: execution.reason,
      detail: execution.detail,
      mutatePositions: false,
    };
  }

  const pause = resolveOperatorPause({ settings: input?.settings, env });
  if (pause.paused) {
    return {
      allowed: false,
      status: "skipped_paused",
      reason: "AGENT_PAUSED",
      pauseSource: pause.source,
      detail: pause.detail,
      mutatePositions: false,
    };
  }

  return { allowed: true, executionMode: execution.mode };
}
