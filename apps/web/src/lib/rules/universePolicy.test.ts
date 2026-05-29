import { describe, expect, it } from "vitest";
import { applyLongUniversePolicy } from "./universePolicy";

describe("applyLongUniversePolicy", () => {
  it("blocks defensive macro ETFs in bullish regimes", () => {
    const result = applyLongUniversePolicy({
      ticker: "IEF",
      segmentKey: "macro",
      regime: "bullish",
      buyScore: 72,
    });

    expect(result.blocked).toBe(true);
    expect(result.blockedReason).toBe("regime_segment");
  });

  it("boosts software/cloud leadership in bullish regimes", () => {
    const result = applyLongUniversePolicy({
      ticker: "SNOW",
      segmentKey: "software_cloud",
      regime: "bullish",
      buyScore: 74,
    });

    expect(result.blocked).toBe(false);
    expect(result.adjustedBuyScore).toBeGreaterThan(74);
  });

  it("penalizes commodity proxy segments in bullish regimes", () => {
    const result = applyLongUniversePolicy({
      ticker: "CPER",
      segmentKey: "metals",
      regime: "bullish",
      buyScore: 90,
    });

    expect(result.blocked).toBe(false);
    expect(result.adjustedBuyScore).toBeLessThan(90);
    expect(result.note).toContain("Commodity proxy penalty");
  });
});
