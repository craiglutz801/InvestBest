/**
 * Reproducibility snapshot for a paper decision run.
 *
 * Persisted on DecisionRun.notesJson.audit so a sampled decision can be
 * reconstructed from inputs + versioned settings without re-fetching live data.
 */

export const SETTINGS_AUDIT_VERSION = "paper-safety-v1";

export type PaperSettingsSnapshot = {
  startingCash: number;
  maxPositionPct: number;
  maxNewPositionsPerRun: number;
  targetHoldings: number;
  stopLossPct: number;
  takeProfitPct: number;
  minConfidence: number;
  cashReservePct: number;
  defaultSlippagePct: number;
  strategyMode: string;
  buyScoreThreshold: number;
  sellRiskThreshold: number;
  cooldownHours: number;
  staleQuoteAllowSells: boolean;
  agentPaused?: boolean;
};

export type SimulatedFillAudit = {
  action: string;
  ticker?: string;
  quantity: number;
  rawPrice: number;
  fillPrice: number;
  slippagePct: number;
  cashBefore: number;
  cashAfter: number;
  reasonCode: string;
  reasonText?: string;
};

export type RunAuditRecord = {
  executionMode: "paper";
  settingsVersion: string;
  strategyMode: string;
  modelVersion: string;
  dataSource: string;
  asOf: string;
  settings: PaperSettingsSnapshot;
  featureInputs?: Record<string, unknown>;
  reasonCodes: string[];
  fills: SimulatedFillAudit[];
  portfolioAfter?: {
    cash: number;
    investedValue: number;
    totalValue: number;
    unrealizedPnl: number;
    realizedPnl: number;
  };
  dataQualitySkips: Array<{ ticker?: string; reason: string; detail: string }>;
};

export type AuditCompleteness = {
  complete: boolean;
  missing: string[];
};

export function buildSettingsSnapshot(settings: {
  startingCash: { toString(): string } | number;
  maxPositionPct: { toString(): string } | number;
  maxNewPositionsPerRun: number;
  targetHoldings: number;
  stopLossPct: { toString(): string } | number;
  takeProfitPct: { toString(): string } | number;
  minConfidence: { toString(): string } | number;
  cashReservePct: { toString(): string } | number;
  defaultSlippagePct: { toString(): string } | number;
  strategyMode: string;
  buyScoreThreshold: { toString(): string } | number;
  sellRiskThreshold: { toString(): string } | number;
  cooldownHours: number;
  staleQuoteAllowSells: boolean;
  agentPaused?: boolean;
}): PaperSettingsSnapshot {
  const n = (v: { toString(): string } | number) => (typeof v === "number" ? v : Number(v.toString()));
  return {
    startingCash: n(settings.startingCash),
    maxPositionPct: n(settings.maxPositionPct),
    maxNewPositionsPerRun: settings.maxNewPositionsPerRun,
    targetHoldings: settings.targetHoldings,
    stopLossPct: n(settings.stopLossPct),
    takeProfitPct: n(settings.takeProfitPct),
    minConfidence: n(settings.minConfidence),
    cashReservePct: n(settings.cashReservePct),
    defaultSlippagePct: n(settings.defaultSlippagePct),
    strategyMode: settings.strategyMode,
    buyScoreThreshold: n(settings.buyScoreThreshold),
    sellRiskThreshold: n(settings.sellRiskThreshold),
    cooldownHours: settings.cooldownHours,
    staleQuoteAllowSells: settings.staleQuoteAllowSells,
    agentPaused: settings.agentPaused === true,
  };
}

export function createRunAuditRecord(input: {
  strategyMode: string;
  modelVersion: string;
  dataSource: string;
  asOf?: Date;
  settings: PaperSettingsSnapshot;
  featureInputs?: Record<string, unknown>;
}): RunAuditRecord {
  return {
    executionMode: "paper",
    settingsVersion: SETTINGS_AUDIT_VERSION,
    strategyMode: input.strategyMode,
    modelVersion: input.modelVersion,
    dataSource: input.dataSource,
    asOf: (input.asOf ?? new Date()).toISOString(),
    settings: input.settings,
    featureInputs: input.featureInputs,
    reasonCodes: [],
    fills: [],
    dataQualitySkips: [],
  };
}

export function recordAuditReason(audit: RunAuditRecord, code: string): void {
  if (!audit.reasonCodes.includes(code)) audit.reasonCodes.push(code);
}

export function recordAuditFill(audit: RunAuditRecord, fill: SimulatedFillAudit): void {
  audit.fills.push(fill);
  recordAuditReason(audit, fill.reasonCode);
}

export function recordDataQualitySkip(
  audit: RunAuditRecord,
  skip: { ticker?: string; reason: string; detail: string },
): void {
  audit.dataQualitySkips.push(skip);
  recordAuditReason(audit, skip.reason);
}

export function evaluateAuditCompleteness(audit: Partial<RunAuditRecord> | null | undefined): AuditCompleteness {
  const missing: string[] = [];
  if (!audit) return { complete: false, missing: ["audit"] };
  if (audit.executionMode !== "paper") missing.push("executionMode");
  if (!audit.settingsVersion) missing.push("settingsVersion");
  if (!audit.strategyMode) missing.push("strategyMode");
  if (!audit.modelVersion) missing.push("modelVersion");
  if (!audit.dataSource) missing.push("dataSource");
  if (!audit.asOf) missing.push("asOf");
  if (!audit.settings) missing.push("settings");
  else {
    for (const key of [
      "stopLossPct",
      "takeProfitPct",
      "cashReservePct",
      "maxPositionPct",
      "cooldownHours",
      "defaultSlippagePct",
      "buyScoreThreshold",
      "sellRiskThreshold",
    ] as const) {
      if (audit.settings[key] == null) missing.push(`settings.${key}`);
    }
  }
  if (!Array.isArray(audit.reasonCodes)) missing.push("reasonCodes");
  if (!Array.isArray(audit.fills)) missing.push("fills");
  if (!Array.isArray(audit.dataQualitySkips)) missing.push("dataQualitySkips");
  return { complete: missing.length === 0, missing };
}

/** True when a sampled fill can be reconstructed from persisted audit fields. */
export function canReconstructFill(fill: Partial<SimulatedFillAudit> | null | undefined): boolean {
  if (!fill) return false;
  return (
    typeof fill.action === "string" &&
    Number.isFinite(fill.quantity) &&
    Number.isFinite(fill.rawPrice) &&
    Number.isFinite(fill.fillPrice) &&
    Number.isFinite(fill.slippagePct) &&
    Number.isFinite(fill.cashBefore) &&
    Number.isFinite(fill.cashAfter) &&
    typeof fill.reasonCode === "string" &&
    fill.reasonCode.length > 0
  );
}
