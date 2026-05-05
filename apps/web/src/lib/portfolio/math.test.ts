import { describe, expect, it } from "vitest";
import {
  applySlippage,
  avgCostAfterBuy,
  grossNotional,
  marketValue,
  realizedPnlSell,
  signedExposureMarketValue,
  unrealizedPnl,
  unrealizedPnlPosition,
  wholeShares,
} from "./math";

describe("portfolio math", () => {
  it("wholeShares floors", () => {
    expect(wholeShares(1000, 300)).toBe(3);
    expect(wholeShares(99, 100)).toBe(0);
  });

  it("applySlippage buy pays more, sell receives less", () => {
    expect(applySlippage(100, "BUY", 0.05)).toBeCloseTo(100.05, 8);
    expect(applySlippage(100, "SELL", 0.05)).toBeCloseTo(99.95, 8);
  });

  it("unrealized and realized", () => {
    expect(unrealizedPnl(10, 50, 55)).toBe(50);
    expect(realizedPnlSell(10, 50, 55)).toBe(50);
    expect(marketValue(10, 55)).toBe(550);
  });

  it("avgCostAfterBuy", () => {
    expect(avgCostAfterBuy(0, 0, 10, 100)).toBe(100);
    expect(avgCostAfterBuy(10, 100, 10, 120)).toBe(110);
  });

  it("short exposure and unrealized", () => {
    expect(signedExposureMarketValue(10, 50, true)).toBe(-500);
    expect(unrealizedPnlPosition(10, 50, 45, true)).toBe(50);
    expect(grossNotional(10, 50)).toBe(500);
  });
});
