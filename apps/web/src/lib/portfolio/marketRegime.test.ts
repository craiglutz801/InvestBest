import { describe, expect, it } from "vitest";
import { assessMarketRegime, regimeAdjustedMaxNew } from "./marketRegime";

function uptrend(n = 220): number[] {
  return Array.from({ length: n }, (_, i) => 100 + i * 0.5);
}
function downtrend(n = 220): number[] {
  return Array.from({ length: n }, (_, i) => 100 - i * 0.3);
}

describe("assessMarketRegime", () => {
  it("classifies a steady uptrend as bullish", () => {
    const r = assessMarketRegime(uptrend());
    expect(r.regime).toBe("bullish");
    expect(r.sma200).not.toBeNull();
    expect(r.distSma200).not.toBeNull();
    expect(r.distSma200!).toBeGreaterThan(0);
  });

  it("classifies a steady downtrend as bearish", () => {
    const r = assessMarketRegime(downtrend());
    expect(r.regime).toBe("bearish");
    expect(r.distSma200!).toBeLessThan(0);
  });

  it("falls back to neutral when there is not enough history", () => {
    const r = assessMarketRegime([100, 101, 102]);
    expect(r.regime).toBe("neutral");
    expect(r.sma200).toBeNull();
  });
});

describe("regimeAdjustedMaxNew", () => {
  it("passes through bullish or neutral runs", () => {
    expect(regimeAdjustedMaxNew(4, "bullish").adjusted).toBe(4);
    expect(regimeAdjustedMaxNew(4, "neutral").adjusted).toBe(4);
  });

  it("halves new buys when bearish (floor 0)", () => {
    expect(regimeAdjustedMaxNew(4, "bearish").adjusted).toBe(2);
    expect(regimeAdjustedMaxNew(1, "bearish").adjusted).toBe(0);
    expect(regimeAdjustedMaxNew(0, "bearish").adjusted).toBe(0);
  });

  it("can be disabled with mode=off (env or arg)", () => {
    expect(regimeAdjustedMaxNew(4, "bearish", "off")).toMatchObject({
      adjusted: 4,
      throttled: false,
      mode: "off",
    });
  });

  it("strict mode: bullish passes, neutral halves, bearish drops to 0", () => {
    expect(regimeAdjustedMaxNew(4, "bullish", "strict").adjusted).toBe(4);
    expect(regimeAdjustedMaxNew(4, "neutral", "strict").adjusted).toBe(2);
    expect(regimeAdjustedMaxNew(4, "bearish", "strict")).toMatchObject({
      adjusted: 0,
      throttled: true,
      mode: "strict",
    });
  });

  it("unknown mode strings fall back to soft", () => {
    expect(regimeAdjustedMaxNew(4, "bearish", "weird-thing").mode).toBe("soft");
    expect(regimeAdjustedMaxNew(4, "bearish", "weird-thing").adjusted).toBe(2);
  });
});
