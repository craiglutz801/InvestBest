import { describe, expect, it } from "vitest";
import type { OhlcvBar } from "@/lib/data-provider/twelveData";
import { alphaFoundationScores, computeFeatures, rulesScores, strategyScores } from "./features";

function makeBars(closes: number[], volumes?: number[]): OhlcvBar[] {
  const start = new Date("2024-01-01T00:00:00Z");
  return closes.map((c, i) => ({
    time: new Date(start.getTime() + i * 86_400_000),
    open: c,
    high: c * 1.005,
    low: c * 0.995,
    close: c,
    volume: volumes?.[i] ?? 1_000_000,
  }));
}

describe("computeFeatures", () => {
  it("returns neutral defaults when fewer than 22 bars are available", () => {
    const { features, completeness } = computeFeatures(makeBars([100, 101, 102]));
    expect(features.rsi14).toBe(50);
    expect(features.vol20).toBe(0);
    expect(features.volSpike).toBe(false);
    expect(completeness).toBeGreaterThan(0);
    expect(completeness).toBeLessThan(0.1);
  });

  it("computes RSI = 100 when there are no losses in the lookback", () => {
    const closes = Array.from({ length: 30 }, (_, i) => 100 + i);
    const { features } = computeFeatures(makeBars(closes));
    expect(features.rsi14).toBe(100);
    expect(features.ret5d).toBeGreaterThan(0);
    expect(features.distSma20).toBeGreaterThan(0);
  });

  it("flags a volume spike when the latest bar is more than 2x the 20-day average", () => {
    const closes = Array.from({ length: 30 }, () => 100);
    const volumes = Array.from({ length: 30 }, (_, i) => (i === 29 ? 5_000_000 : 1_000_000));
    const { features } = computeFeatures(makeBars(closes, volumes));
    expect(features.volSpike).toBe(true);
  });

  it("does not flag a spike when the latest bar matches the average", () => {
    const closes = Array.from({ length: 30 }, () => 100);
    const { features } = computeFeatures(makeBars(closes));
    expect(features.volSpike).toBe(false);
  });
});

describe("rulesScores", () => {
  const baseFeatures = {
    ret1d: 0.005,
    ret5d: 0.02,
    ret20d: 0.05,
    distSma20: 0.02,
    distSma50: 0.01,
    rsi14: 55,
    vol20: 0.2,
    volSpike: false,
  } as const;

  it("clamps buy and sell-risk scores to [0, 100]", () => {
    const r = rulesScores({ ...baseFeatures, rsi14: 90, vol20: 1.5, volSpike: true, ret5d: -0.2, distSma20: -0.5 });
    expect(r.buyScore).toBeGreaterThanOrEqual(0);
    expect(r.buyScore).toBeLessThanOrEqual(100);
    expect(r.sellRiskScore).toBeGreaterThanOrEqual(0);
    expect(r.sellRiskScore).toBeLessThanOrEqual(100);
  });

  it("penalizes overbought RSI in the buy score", () => {
    const healthy = rulesScores(baseFeatures);
    const overbought = rulesScores({ ...baseFeatures, rsi14: 80 });
    expect(overbought.buyScore).toBeLessThan(healthy.buyScore);
  });

  it("emits human-readable factor strings", () => {
    const r = rulesScores(baseFeatures);
    expect(r.breakdown.buyFactors.length).toBeGreaterThan(0);
    expect(r.breakdown.featureSummary).toMatch(/RSI/);
  });

  it("raises sell risk when the price collapses below SMA20", () => {
    const calm = rulesScores(baseFeatures);
    const collapsing = rulesScores({ ...baseFeatures, distSma20: -0.1, ret5d: -0.05 });
    expect(collapsing.sellRiskScore).toBeGreaterThan(calm.sellRiskScore);
  });

  it("lets alpha mode prefer cleaner trend quality over stretched momentum", () => {
    const balancedTrend = {
      ...baseFeatures,
      ret5d: 0.012,
      ret20d: 0.08,
      distSma20: 0.015,
      distSma50: 0.04,
      rsi14: 57,
      vol20: 0.19,
    };
    const stretchedTrend = {
      ...baseFeatures,
      ret5d: 0.05,
      ret20d: 0.09,
      distSma20: 0.11,
      distSma50: 0.12,
      rsi14: 82,
      vol20: 0.42,
    };

    const balanced = alphaFoundationScores(balancedTrend);
    const stretched = strategyScores("alpha_v1", stretchedTrend);

    expect(balanced.buyScore).toBeGreaterThan(stretched.buyScore);
    expect(balanced.expectedDrawdownRisk5d).toBeLessThan(stretched.expectedDrawdownRisk5d);
  });

  it("rewards steady momentum follow-through that is not yet blow-off extended", () => {
    const steadyLeader = alphaFoundationScores({
      ...baseFeatures,
      ret5d: 0.018,
      ret20d: 0.12,
      distSma20: 0.035,
      distSma50: 0.08,
      rsi14: 61,
      vol20: 0.24,
    });
    const stalledName = alphaFoundationScores({
      ...baseFeatures,
      ret5d: -0.005,
      ret20d: 0.04,
      distSma20: -0.01,
      distSma50: 0.01,
      rsi14: 48,
      vol20: 0.24,
    });

    expect(steadyLeader.buyScore).toBeGreaterThan(stalledName.buyScore);
  });

  it("supports regression_v1 as an additive V2 scoring lane", () => {
    const strongTrend = strategyScores("regression_v1", {
      ...baseFeatures,
      ret5d: 0.025,
      ret20d: 0.11,
      distSma20: 0.03,
      distSma50: 0.07,
      rsi14: 60,
      vol20: 0.22,
      volSpike: false,
    });
    const brokenTrend = strategyScores("regression_v1", {
      ...baseFeatures,
      ret5d: -0.03,
      ret20d: -0.08,
      distSma20: -0.06,
      distSma50: -0.09,
      rsi14: 37,
      vol20: 0.5,
      volSpike: true,
    });

    expect(strongTrend.buyScore).toBeGreaterThan(brokenTrend.buyScore);
    expect(strongTrend.sellRiskScore).toBeLessThan(brokenTrend.sellRiskScore);
    expect(strongTrend.breakdown.featureSummary).toContain("regression-v1");
  });
});
