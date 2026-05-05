import { describe, expect, it } from "vitest";
import { shouldSell } from "./sellRules";

describe("sell rules", () => {
  it("stop loss", () => {
    const r = shouldSell({
      currentPrice: 90,
      avgCost: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      sellRiskScore: 0,
      sellRiskThreshold: 65,
      ret5d: 0,
      rsi: 50,
    });
    expect(r.sell).toBe(true);
    if (r.sell) expect(r.code).toBe("stop_loss");
  });

  it("take profit", () => {
    const r = shouldSell({
      currentPrice: 120,
      avgCost: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      sellRiskScore: 0,
      sellRiskThreshold: 65,
      ret5d: 0.1,
      rsi: 60,
    });
    expect(r.sell).toBe(true);
    if (r.sell) expect(r.code).toBe("take_profit");
  });

  it("sell risk threshold", () => {
    const r = shouldSell({
      currentPrice: 100,
      avgCost: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      sellRiskScore: 70,
      sellRiskThreshold: 65,
      ret5d: 0,
      rsi: 50,
    });
    expect(r.sell).toBe(true);
    if (r.sell) expect(r.code).toBe("sell_risk");
  });

  it("hold otherwise", () => {
    const r = shouldSell({
      currentPrice: 100,
      avgCost: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      sellRiskScore: 30,
      sellRiskThreshold: 65,
      ret5d: 0,
      rsi: 50,
    });
    expect(r).toEqual({ sell: false });
  });

  describe("trailing stop (give-back)", () => {
    const baseTrailing = {
      avgCost: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      sellRiskScore: 0,
      sellRiskThreshold: 65,
      ret5d: 0.01,
      rsi: 55,
    };

    it("fires when price gives back ≥ default 4% from a peak that reached halfway to TP", () => {
      const r = shouldSell({
        ...baseTrailing,
        currentPrice: 105,
        recentHigh: 110,
      });
      expect(r.sell).toBe(true);
      if (r.sell) expect(r.code).toBe("trailing_stop");
    });

    it("does not fire when peak never reached halfway to TP", () => {
      const r = shouldSell({
        ...baseTrailing,
        currentPrice: 102,
        recentHigh: 104,
      });
      expect(r.sell).toBe(false);
    });

    it("does not fire when give-back is small (< threshold)", () => {
      const r = shouldSell({
        ...baseTrailing,
        currentPrice: 109,
        recentHigh: 110,
      });
      expect(r.sell).toBe(false);
    });

    it("does not fire when position is still at a loss vs cost", () => {
      const r = shouldSell({
        ...baseTrailing,
        currentPrice: 95,
        recentHigh: 110,
      });
      expect(r.sell).toBe(false);
    });

    it("respects a custom trailingGiveBackPct override", () => {
      const r = shouldSell({
        ...baseTrailing,
        currentPrice: 108,
        recentHigh: 110,
        trailingGiveBackPct: 1,
      });
      expect(r.sell).toBe(true);
      if (r.sell) expect(r.code).toBe("trailing_stop");
    });

    it("is back-compat: omitting recentHigh disables the branch", () => {
      const r = shouldSell({
        ...baseTrailing,
        currentPrice: 105,
      });
      expect(r.sell).toBe(false);
    });
  });
});
