import { describe, expect, it } from "vitest";
import { pickRotationTarget } from "./rotationRules";

describe("rotation rules", () => {
  const baseCandidate = {
    symbolId: "c1",
    ticker: "NVDA",
    segmentKey: "equities_core",
    buyScore: 72,
    sellRiskScore: 28,
    confidenceScore: 80,
  };

  it("selects the weakest eligible holding when the candidate has a clear edge", () => {
    const result = pickRotationTarget({
      candidate: baseCandidate,
      holdings: [
        {
          symbolId: "h1",
          ticker: "BRK.B",
          segmentKey: "equities_core",
          buyScore: 58,
          sellRiskScore: 48,
          confidenceScore: 80,
        },
        {
          symbolId: "h2",
          ticker: "MSFT",
          segmentKey: "equities_core",
          buyScore: 66,
          sellRiskScore: 32,
          confidenceScore: 85,
        },
      ],
      minBuyScoreEdge: 8,
      weakHoldMaxBuyScore: 60,
      minHeldSellRisk: 45,
      maxCandidateSellRiskSpread: 5,
    });

    expect(result?.ticker).toBe("BRK.B");
  });

  it("returns null when the candidate edge is too small", () => {
    const result = pickRotationTarget({
      candidate: { ...baseCandidate, buyScore: 64 },
      holdings: [
        {
          symbolId: "h1",
          ticker: "BRK.B",
          segmentKey: "equities_core",
          buyScore: 58,
          sellRiskScore: 48,
          confidenceScore: 80,
        },
      ],
      minBuyScoreEdge: 8,
      weakHoldMaxBuyScore: 60,
      minHeldSellRisk: 45,
      maxCandidateSellRiskSpread: 5,
    });

    expect(result).toBeNull();
  });

  it("returns null when the candidate is riskier than the holding allowance", () => {
    const result = pickRotationTarget({
      candidate: { ...baseCandidate, sellRiskScore: 60 },
      holdings: [
        {
          symbolId: "h1",
          ticker: "BRK.B",
          segmentKey: "equities_core",
          buyScore: 54,
          sellRiskScore: 48,
          confidenceScore: 80,
        },
      ],
      minBuyScoreEdge: 8,
      weakHoldMaxBuyScore: 60,
      minHeldSellRisk: 45,
      maxCandidateSellRiskSpread: 5,
    });

    expect(result).toBeNull();
  });
});
