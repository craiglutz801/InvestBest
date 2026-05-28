import type { FeatureVector } from "@/lib/portfolio/features";

export type BuyBlockReason =
  | "cash_reserve"
  | "confidence"
  | "buy_score"
  | "already_held"
  | "volatility"
  | "extended_from_mean"
  | "cooldown"
  | "liquidity"
  | "momentum_requirement"
  | "regime_segment";

export function evaluateBuyBlock(input: {
  cash: number;
  portfolioValue: number;
  availableForTrade: number;
  cashReservePct: number;
  minConfidence: number;
  buyScore: number;
  buyScoreThreshold: number;
  confidenceScore: number;
  alreadyHeld: boolean;
  features: FeatureVector;
  maxVolatility: number;
  maxDistFromMean: number;
  onCooldown: boolean;
  /**
   * Recent average daily dollar volume for the symbol (last N bars). Optional.
   * When provided AND `minDollarVolume > 0`, blocks symbols below the threshold
   * to avoid illiquid names. Defaults preserve back-compat (no extra blocks).
   */
  avgDollarVolume?: number;
  minDollarVolume?: number;
  /** When true, block unless both 5d and 20d returns are positive (trend confirmation). */
  requirePositiveMomentum?: boolean;
}): { blocked: false } | { blocked: true; reason: BuyBlockReason; detail: string } {
  const minCash = (input.portfolioValue * input.cashReservePct) / 100;
  if (input.cash < minCash && input.availableForTrade <= 0) {
    return { blocked: true, reason: "cash_reserve", detail: "Would violate cash reserve" };
  }
  if (input.confidenceScore < input.minConfidence) {
    return { blocked: true, reason: "confidence", detail: `Confidence ${input.confidenceScore} < ${input.minConfidence}` };
  }
  if (input.buyScore < input.buyScoreThreshold) {
    return { blocked: true, reason: "buy_score", detail: `Buy score ${input.buyScore} < ${input.buyScoreThreshold}` };
  }
  if (input.alreadyHeld) {
    return { blocked: true, reason: "already_held", detail: "Pyramiding disabled" };
  }
  if (
    input.requirePositiveMomentum &&
    !(input.features.ret5d > 0 && input.features.ret20d > 0)
  ) {
    return {
      blocked: true,
      reason: "momentum_requirement",
      detail: `Momentum filter: need positive 5d and 20d (got 5d ${(input.features.ret5d * 100).toFixed(2)}%, 20d ${(input.features.ret20d * 100).toFixed(2)}%)`,
    };
  }
  if (input.features.vol20 > input.maxVolatility) {
    return { blocked: true, reason: "volatility", detail: `Vol ${input.features.vol20.toFixed(2)} too high` };
  }
  if (input.features.distSma20 > input.maxDistFromMean) {
    return { blocked: true, reason: "extended_from_mean", detail: "Price extended above mean" };
  }
  if (input.onCooldown) {
    return { blocked: true, reason: "cooldown", detail: "Symbol on post-sell cooldown" };
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
      detail: `Avg $vol ${formatDollar(input.avgDollarVolume)} < min ${formatDollar(input.minDollarVolume)}`,
    };
  }
  return { blocked: false };
}

function formatDollar(n: number): string {
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(2)}M`;
  if (n >= 1e3) return `$${(n / 1e3).toFixed(0)}k`;
  return `$${n.toFixed(0)}`;
}
