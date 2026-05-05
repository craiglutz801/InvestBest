import { describe, expect, it } from "vitest";
import { evaluateBuyBlock } from "./buyRules";

const baseFeatures = {
  ret1d: 0,
  ret5d: 0.02,
  ret20d: 0.05,
  distSma20: 0.02,
  distSma50: 0.01,
  rsi14: 55,
  vol20: 0.2,
  volSpike: false,
};

describe("buy rules", () => {
  it("blocks low buy score", () => {
    const r = evaluateBuyBlock({
      cash: 50_000,
      portfolioValue: 100_000,
      availableForTrade: 20_000,
      cashReservePct: 10,
      minConfidence: 40,
      buyScore: 30,
      buyScoreThreshold: 45,
      confidenceScore: 80,
      alreadyHeld: false,
      features: baseFeatures,
      maxVolatility: 0.6,
      maxDistFromMean: 0.15,
      onCooldown: false,
    });
    expect(r).toMatchObject({ blocked: true, reason: "buy_score" });
  });

  it("blocks cooldown", () => {
    const r = evaluateBuyBlock({
      cash: 50_000,
      portfolioValue: 100_000,
      availableForTrade: 20_000,
      cashReservePct: 10,
      minConfidence: 40,
      buyScore: 70,
      buyScoreThreshold: 45,
      confidenceScore: 80,
      alreadyHeld: false,
      features: baseFeatures,
      maxVolatility: 0.6,
      maxDistFromMean: 0.15,
      onCooldown: true,
    });
    expect(r).toMatchObject({ blocked: true, reason: "cooldown" });
  });

    it("allows when healthy", () => {
      const r = evaluateBuyBlock({
        cash: 50_000,
        portfolioValue: 100_000,
        availableForTrade: 20_000,
        cashReservePct: 10,
        minConfidence: 40,
        buyScore: 70,
        buyScoreThreshold: 45,
        confidenceScore: 80,
        alreadyHeld: false,
        features: baseFeatures,
        maxVolatility: 0.6,
        maxDistFromMean: 0.15,
        onCooldown: false,
      });
      expect(r).toEqual({ blocked: false });
    });

    it("blocks when momentum filter enabled but 20d not positive", () => {
      const r = evaluateBuyBlock({
        cash: 50_000,
        portfolioValue: 100_000,
        availableForTrade: 20_000,
        cashReservePct: 10,
        minConfidence: 40,
        buyScore: 70,
        buyScoreThreshold: 45,
        confidenceScore: 80,
        alreadyHeld: false,
        features: { ...baseFeatures, ret5d: 0.01, ret20d: -0.02 },
        maxVolatility: 0.6,
        maxDistFromMean: 0.15,
        onCooldown: false,
        requirePositiveMomentum: true,
      });
      expect(r).toMatchObject({ blocked: true, reason: "momentum_requirement" });
    });

  describe("liquidity guard", () => {
    const healthy = {
      cash: 50_000,
      portfolioValue: 100_000,
      availableForTrade: 20_000,
      cashReservePct: 10,
      minConfidence: 40,
      buyScore: 70,
      buyScoreThreshold: 45,
      confidenceScore: 80,
      alreadyHeld: false,
      features: baseFeatures,
      maxVolatility: 0.6,
      maxDistFromMean: 0.15,
      onCooldown: false,
    };

    it("blocks when avg dollar volume is below the minimum", () => {
      const r = evaluateBuyBlock({
        ...healthy,
        avgDollarVolume: 200_000,
        minDollarVolume: 1_000_000,
      });
      expect(r).toMatchObject({ blocked: true, reason: "liquidity" });
    });

    it("allows when avg dollar volume meets the minimum", () => {
      const r = evaluateBuyBlock({
        ...healthy,
        avgDollarVolume: 5_000_000,
        minDollarVolume: 1_000_000,
      });
      expect(r).toEqual({ blocked: false });
    });

    it("is back-compat: no min ⇒ no block", () => {
      const r = evaluateBuyBlock({
        ...healthy,
        avgDollarVolume: 1,
      });
      expect(r).toEqual({ blocked: false });
    });

    it("is back-compat: min set but no value provided ⇒ no block", () => {
      const r = evaluateBuyBlock({
        ...healthy,
        minDollarVolume: 1_000_000,
      });
      expect(r).toEqual({ blocked: false });
    });
  });
});
