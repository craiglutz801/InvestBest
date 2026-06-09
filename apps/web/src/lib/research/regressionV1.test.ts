import { describe, expect, it } from "vitest";
import { computeForwardTargets, predictRegressionV1 } from "./regressionV1";

describe("predictRegressionV1", () => {
  it("assigns higher expected return and lower downside to stronger trends", () => {
    const strong = predictRegressionV1({
      ret1d: 0.01,
      ret5d: 0.03,
      ret20d: 0.12,
      distSma20: 0.03,
      distSma50: 0.08,
      rsi14: 60,
      vol20: 0.22,
      volSpike: false,
    });
    const weak = predictRegressionV1({
      ret1d: -0.01,
      ret5d: -0.03,
      ret20d: -0.08,
      distSma20: -0.05,
      distSma50: -0.07,
      rsi14: 38,
      vol20: 0.55,
      volSpike: true,
    });

    expect(strong.expectedReturn5d).toBeGreaterThan(weak.expectedReturn5d);
    expect(strong.downsideProbability5d).toBeLessThan(weak.downsideProbability5d);
  });
});

describe("computeForwardTargets", () => {
  it("computes forward return and downside over the lookahead window", () => {
    const targets = computeForwardTargets(100, [101, 98, 103, 104, 106]);
    expect(targets.targetClose).toBe(106);
    expect(targets.targetReturn).toBeCloseTo(0.06, 6);
    expect(targets.downsideReturn).toBeCloseTo(-0.02, 6);
    expect(targets.downsideHit).toBe(true);
  });
});
