export type SellReasonCode =
  | "stop_loss"
  | "take_profit"
  | "trailing_stop"
  | "sell_risk"
  | "momentum_break"
  | "confidence_collapse"
  | "rebalance";

/**
 * Default give-back used by the trailing-stop rule. Once a position has reached at least halfway
 * to its take-profit target, surrendering this much of the recent peak triggers a sell.
 * Tuned to be conservative — does not fire on small wiggles, but locks in gains on real reversals.
 */
export const DEFAULT_TRAILING_GIVE_BACK_PCT = 4;

export function shouldSell(input: {
  currentPrice: number;
  avgCost: number;
  stopLossPct: number;
  takeProfitPct: number;
  sellRiskScore: number;
  sellRiskThreshold: number;
  ret5d: number;
  rsi: number;
  /**
   * Highest close (or quote) observed in the recent lookback window for this symbol.
   * Optional — when omitted, the trailing-stop branch is skipped entirely (back-compat).
   */
  recentHigh?: number;
  /** Override the default trailing give-back threshold (% from recent high). */
  trailingGiveBackPct?: number;
}): { sell: false } | { sell: true; code: SellReasonCode; detail: string } {
  const dd = (input.currentPrice - input.avgCost) / input.avgCost;
  if (dd <= -input.stopLossPct / 100) {
    return { sell: true, code: "stop_loss", detail: `Down ${(dd * 100).toFixed(2)}% >= stop ${input.stopLossPct}%` };
  }
  if (dd >= input.takeProfitPct / 100) {
    return { sell: true, code: "take_profit", detail: `Up ${(dd * 100).toFixed(2)}% >= target ${input.takeProfitPct}%` };
  }

  // Trailing-stop only fires when we have meaningful profit to protect AND the recent high
  // shows we got at least halfway to the take-profit target before reversing.
  if (
    input.recentHigh != null &&
    input.recentHigh > 0 &&
    input.currentPrice > input.avgCost &&
    input.takeProfitPct > 0
  ) {
    const halfwayPx = input.avgCost * (1 + (0.5 * input.takeProfitPct) / 100);
    const giveBackPct = input.trailingGiveBackPct ?? DEFAULT_TRAILING_GIVE_BACK_PCT;
    if (input.recentHigh >= halfwayPx) {
      const dropFromHighPct = ((input.recentHigh - input.currentPrice) / input.recentHigh) * 100;
      if (dropFromHighPct >= giveBackPct) {
        const peakGainPct = ((input.recentHigh - input.avgCost) / input.avgCost) * 100;
        return {
          sell: true,
          code: "trailing_stop",
          detail: `Gave back ${dropFromHighPct.toFixed(2)}% from recent high (peak +${peakGainPct.toFixed(2)}% vs cost) ≥ ${giveBackPct}% trail`,
        };
      }
    }
  }

  if (input.sellRiskScore >= input.sellRiskThreshold) {
    return { sell: true, code: "sell_risk", detail: `Sell-risk ${input.sellRiskScore}` };
  }
  if (input.ret5d < -0.04 && input.rsi < 45) {
    return { sell: true, code: "momentum_break", detail: "5d return weak and RSI rolling over" };
  }
  return { sell: false };
}
