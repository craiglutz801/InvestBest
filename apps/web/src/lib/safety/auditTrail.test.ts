import { describe, expect, it } from "vitest";
import {
  SETTINGS_AUDIT_VERSION,
  buildSettingsSnapshot,
  canReconstructFill,
  createRunAuditRecord,
  evaluateAuditCompleteness,
  recordAuditFill,
  recordDataQualitySkip,
} from "./auditTrail";

const settings = {
  startingCash: 100_000,
  maxPositionPct: 10,
  maxNewPositionsPerRun: 3,
  targetHoldings: 12,
  stopLossPct: 8,
  takeProfitPct: 15,
  minConfidence: 40,
  cashReservePct: 10,
  defaultSlippagePct: 0.05,
  strategyMode: "rules_v1",
  buyScoreThreshold: 45,
  sellRiskThreshold: 65,
  cooldownHours: 24,
  staleQuoteAllowSells: false,
};

describe("audit trail reproducibility", () => {
  it("snapshots versioned settings", () => {
    const snap = buildSettingsSnapshot(settings);
    expect(snap.stopLossPct).toBe(8);
    expect(snap.cooldownHours).toBe(24);
    expect(snap.maxPositionPct).toBe(10);
  });

  it("records enough fields to reconstruct a sampled fill", () => {
    const audit = createRunAuditRecord({
      strategyMode: "rules_v1",
      modelVersion: "rules-v1",
      dataSource: "mock",
      asOf: new Date("2026-08-26T15:00:00Z"),
      settings: buildSettingsSnapshot(settings),
      featureInputs: { AAPL: { ret5d: 0.02, rsi14: 55 } },
    });
    recordAuditFill(audit, {
      action: "BUY",
      ticker: "AAPL",
      quantity: 10,
      rawPrice: 100,
      fillPrice: 100.05,
      slippagePct: 0.05,
      cashBefore: 100_000,
      cashAfter: 98_999.5,
      reasonCode: "buy_rank",
    });
    expect(audit.settingsVersion).toBe(SETTINGS_AUDIT_VERSION);
    expect(evaluateAuditCompleteness(audit)).toEqual({ complete: true, missing: [] });
    expect(canReconstructFill(audit.fills[0])).toBe(true);
    expect(audit.fills[0].fillPrice).toBeCloseTo(audit.fills[0].rawPrice * (1 + 0.05 / 100));
  });

  it("flags incomplete audit records", () => {
    expect(evaluateAuditCompleteness({}).complete).toBe(false);
    expect(canReconstructFill({ action: "BUY" })).toBe(false);
  });

  it("records data-quality skips as reason codes", () => {
    const audit = createRunAuditRecord({
      strategyMode: "rules_v1",
      modelVersion: "rules-v1",
      dataSource: "twelvedata",
      settings: buildSettingsSnapshot(settings),
    });
    recordDataQualitySkip(audit, { ticker: "XYZ", reason: "STALE_BARS", detail: "too old" });
    expect(audit.reasonCodes).toContain("STALE_BARS");
    expect(audit.dataQualitySkips).toHaveLength(1);
  });
});
