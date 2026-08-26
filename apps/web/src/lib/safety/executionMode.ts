/**
 * Capability boundary for NorthstarAlpha / InvestBest paper trading.
 *
 * The only supported runtime is `EXECUTION_MODE=paper`. Missing, empty, or any
 * other value (including live / broker / production) fails closed before an
 * agent run may mutate simulated positions.
 */

export const PAPER_EXECUTION_MODE = "paper" as const;

export type ExecutionMode = typeof PAPER_EXECUTION_MODE;

export type ExecutionModeDecision =
  | { ok: true; mode: ExecutionMode; raw: string }
  | { ok: false; mode: null; raw: string | undefined; reason: ExecutionModeBlockReason; detail: string };

export type ExecutionModeBlockReason =
  | "EXECUTION_MODE_MISSING"
  | "EXECUTION_MODE_INVALID"
  | "EXECUTION_MODE_NOT_PAPER";

const FORBIDDEN_HINTS = ["live", "prod", "broker", "real", "alpaca", "ibkr"] as const;

export function readExecutionModeRaw(env: NodeJS.Dict<string> = process.env): string | undefined {
  const raw = env.EXECUTION_MODE;
  if (raw == null) return undefined;
  const trimmed = raw.trim();
  return trimmed === "" ? "" : trimmed;
}

export function resolveExecutionMode(env: NodeJS.Dict<string> = process.env): ExecutionModeDecision {
  const raw = readExecutionModeRaw(env);
  if (raw == null) {
    return {
      ok: false,
      mode: null,
      raw,
      reason: "EXECUTION_MODE_MISSING",
      detail: "EXECUTION_MODE is not set. Paper-only runtime requires EXECUTION_MODE=paper.",
    };
  }
  if (raw === "") {
    return {
      ok: false,
      mode: null,
      raw,
      reason: "EXECUTION_MODE_MISSING",
      detail: "EXECUTION_MODE is empty. Paper-only runtime requires EXECUTION_MODE=paper.",
    };
  }

  const normalized = raw.toLowerCase();
  if (normalized === PAPER_EXECUTION_MODE) {
    return { ok: true, mode: PAPER_EXECUTION_MODE, raw };
  }

  const looksForbidden = FORBIDDEN_HINTS.some((h) => normalized.includes(h));
  return {
    ok: false,
    mode: null,
    raw,
    reason: looksForbidden ? "EXECUTION_MODE_NOT_PAPER" : "EXECUTION_MODE_INVALID",
    detail: `EXECUTION_MODE=${JSON.stringify(raw)} is not allowed. Only EXECUTION_MODE=paper can start an agent run.`,
  };
}

export function assertPaperExecutionMode(env: NodeJS.Dict<string> = process.env): ExecutionMode {
  const decision = resolveExecutionMode(env);
  if (!decision.ok) {
    throw new ExecutionModeError(decision.reason, decision.detail);
  }
  return decision.mode;
}

export class ExecutionModeError extends Error {
  readonly reason: ExecutionModeBlockReason;
  readonly code = "EXECUTION_MODE_BLOCKED" as const;

  constructor(reason: ExecutionModeBlockReason, message: string) {
    super(message);
    this.name = "ExecutionModeError";
    this.reason = reason;
  }
}
