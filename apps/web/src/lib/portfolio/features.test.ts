import { describe, expect, it } from "vitest";
import type { OhlcvBar } from "@/lib/data-provider/twelveData";
import { computeFeatures, rulesScores } from "./features";

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
});
