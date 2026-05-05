import { describe, expect, it } from "vitest";
import { evaluateShortBlock, shouldCoverShort } from "./shortRules";

const featBase = {
  ret1d: 0,
  ret5d: -0.03,
  ret20d: -0.06,
  distSma20: -0.03,
  distSma50: -0.05,
  rsi14: 58,
  vol20: 0.22,
  volSpike: false,
};

describe("short rules", () => {
  it("evaluateShortBlock disables when flag off", () => {
    const r = evaluateShortBlock({
      shortingEnabled: false,
      regimeAllowsShort: true,
      bearScore: 90,
      bearScoreThreshold: 82,
      confidenceScore: 80,
      minConfidenceEffective: 55,
      features: featBase,
      maxVolatility: 0.6,
      minDistSma20Floor: -0.14,
      maxDistSma20Ceiling: 0.18,
      onCooldown: false,
    });
    expect(r).toMatchObject({ blocked: true, reason: "shorting_disabled" });
  });

  it("evaluateShortBlock blocks in wrong regime", () => {
    const r = evaluateShortBlock({
      shortingEnabled: true,
      regimeAllowsShort: false,
      bearScore: 90,
      bearScoreThreshold: 82,
      confidenceScore: 80,
      minConfidenceEffective: 55,
      features: featBase,
      maxVolatility: 0.6,
      minDistSma20Floor: -0.14,
      maxDistSma20Ceiling: 0.18,
      onCooldown: false,
    });
    expect(r).toMatchObject({ blocked: true, reason: "bear_regime" });
  });

  it("shouldCoverShort triggers stop when price rallies vs short entry", () => {
    const r = shouldCoverShort({
      currentPrice: 110,
      avgCostShort: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      buyScore: 40,
      buyScoreCoverThreshold: 78,
      ret5d: 0,
      rsi: 50,
    });
    expect(r).toMatchObject({ cover: true, code: "stop_loss" });
  });

  it("shouldCoverShort takes profit when price drops enough", () => {
    const r = shouldCoverShort({
      currentPrice: 84,
      avgCostShort: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      buyScore: 40,
      buyScoreCoverThreshold: 78,
      ret5d: 0,
      rsi: 50,
    });
    expect(r).toMatchObject({ cover: true, code: "take_profit" });
  });
});
