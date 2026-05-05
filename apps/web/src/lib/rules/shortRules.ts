import type { FeatureVector } from "@/lib/portfolio/features";
import { DEFAULT_TRAILING_GIVE_BACK_PCT } from "@/lib/rules/sellRules";

export type ShortBlockReason =
  | "shorting_disabled"
  | "bear_regime"
  | "bear_score"
  | "confidence"
  | "volatility"
  | "overextended_down"
  | "overextended_up"
  | "cooldown"
  | "liquidity";

export function evaluateShortBlock(input: {
  shortingEnabled: boolean;
  regimeAllowsShort: boolean;
  bearScore: number;
  bearScoreThreshold: number;
  confidenceScore: number;
  minConfidenceEffective: number;
  features: FeatureVector;
  maxVolatility: number;
  /** Block shorts when price is already far below SMA20 (distSma20 &lt; floor). */
  minDistSma20Floor: number;
  /** Block shorts when price is far above SMA20 (squeeze risk). */
  maxDistSma20Ceiling: number;
  onCooldown: boolean;
  avgDollarVolume?: number;
  minDollarVolume?: number;
}): { blocked: false } | { blocked: true; reason: ShortBlockReason; detail: string } {
  if (!input.shortingEnabled) {
    return { blocked: true, reason: "shorting_disabled", detail: "Shorting disabled in settings" };
  }
  if (!input.regimeAllowsShort) {
    return { blocked: true, reason: "bear_regime", detail: "Bear-regime filter blocks new shorts this run" };
  }
  if (input.confidenceScore < input.minConfidenceEffective) {
    return {
      blocked: true,
      reason: "confidence",
      detail: `Confidence ${input.confidenceScore} < ${input.minConfidenceEffective} (short bar)`,
    };
  }
  if (input.bearScore < input.bearScoreThreshold) {
    return {
      blocked: true,
      reason: "bear_score",
      detail: `Bear score ${input.bearScore} < ${input.bearScoreThreshold}`,
    };
  }
  if (input.features.vol20 > input.maxVolatility) {
    return { blocked: true, reason: "volatility", detail: `Vol ${input.features.vol20.toFixed(2)} too high to short` };
  }
  if (input.features.distSma20 < input.minDistSma20Floor) {
    return {
      blocked: true,
      reason: "overextended_down",
      detail: `Already extended below SMA20 (${(input.features.distSma20 * 100).toFixed(1)}%)`,
    };
  }
  if (input.features.distSma20 > input.maxDistSma20Ceiling) {
    return {
      blocked: true,
      reason: "overextended_up",
      detail: `Too far above SMA20 (${(input.features.distSma20 * 100).toFixed(1)}%) — squeeze risk`,
    };
  }
  if (input.onCooldown) {
    return { blocked: true, reason: "cooldown", detail: "Symbol on post-cover cooldown" };
  }
  if (
    input.minDollarVolume != null &&
    input.minDollarVolume > 0 &&
    input.avgDollarVolume != null &&
    input.avgDollarVolume > 0 &&
    input.avgDollarVolume < input.minDollarVolume
  ) {
    return {
      blocked: true,
      reason: "liquidity",
      detail: "Liquidity too thin for short entry",
    };
  }
  return { blocked: false };
}

export type CoverReasonCode =
  | "stop_loss"
  | "take_profit"
  | "trailing_cover"
  | "buy_recovery"
  | "momentum_recovery";

/** Exit rules for an open short (avgCostShort = price at which shares were sold short). */
export function shouldCoverShort(input: {
  currentPrice: number;
  avgCostShort: number;
  stopLossPct: number;
  takeProfitPct: number;
  buyScore: number;
  buyScoreCoverThreshold: number;
  ret5d: number;
  rsi: number;
  recentLow?: number;
  trailingGiveBackPct?: number;
}): { cover: false } | { cover: true; code: CoverReasonCode; detail: string } {
  const avg = input.avgCostShort;
  if (avg <= 0 || input.currentPrice <= 0) return { cover: false };

  const lossPct = ((input.currentPrice - avg) / avg) * 100;
  if (lossPct >= input.stopLossPct) {
    return {
      cover: true,
      code: "stop_loss",
      detail: `Short stop: price +${lossPct.toFixed(2)}% vs entry ≥ ${input.stopLossPct}%`,
    };
  }

  const profitPct = ((avg - input.currentPrice) / avg) * 100;
  if (profitPct >= input.takeProfitPct) {
    return {
      cover: true,
      code: "take_profit",
      detail: `Short target: +${profitPct.toFixed(2)}% vs entry ≥ ${input.takeProfitPct}%`,
    };
  }

  const giveBackPct = input.trailingGiveBackPct ?? DEFAULT_TRAILING_GIVE_BACK_PCT;
  const rl = input.recentLow;
  if (
    rl != null &&
    rl > 0 &&
    input.takeProfitPct > 0 &&
    input.currentPrice < avg
  ) {
    const halfwayPx = avg * (1 - (0.5 * input.takeProfitPct) / 100);
    if (rl <= halfwayPx) {
      const bounceFromLowPct = ((input.currentPrice - rl) / rl) * 100;
      if (bounceFromLowPct >= giveBackPct) {
        return {
          cover: true,
          code: "trailing_cover",
          detail: `Bounced ${bounceFromLowPct.toFixed(2)}% off recent low ≥ ${giveBackPct}% trail`,
        };
      }
    }
  }

  if (input.buyScore >= input.buyScoreCoverThreshold) {
    return {
      cover: true,
      code: "buy_recovery",
      detail: `Buy score ${input.buyScore} ≥ ${input.buyScoreCoverThreshold} (recovery)`,
    };
  }

  if (input.ret5d > 0.04 && input.rsi > 58) {
    return {
      cover: true,
      code: "momentum_recovery",
      detail: `5d momentum strong (${(input.ret5d * 100).toFixed(1)}%) with RSI ${input.rsi.toFixed(0)}`,
    };
  }

  return { cover: false };
}
