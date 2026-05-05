import type { StrategySpec } from "@/lib/strategy/types";
import type { TrialMetrics } from "@/lib/research/types";

/**
 * **Trial-only** sensitivity model: perturbs observable metrics based on config deltas.
 * This does NOT replay trades — it makes the UI demonstrable before a real backtest engine exists.
 * See UI disclaimer string on the Karpathy page.
 */
export function applyTrialSensitivity(
  baseline: TrialMetrics,
  baseSpec: StrategySpec,
  candidate: StrategySpec,
): TrialMetrics {
  const dBuy = candidate.buy_threshold - baseSpec.buy_threshold;
  const dSell = candidate.sell_risk_threshold - baseSpec.sell_risk_threshold;
  const dSl = candidate.stop_loss_pct - baseSpec.stop_loss_pct;
  const dTp = candidate.take_profit_pct - baseSpec.take_profit_pct;
  const dCash = candidate.cash_reserve_pct - baseSpec.cash_reserve_pct;
  const dMaxPos = candidate.max_position_pct - baseSpec.max_position_pct;

  // Small linear sensitivities (tunable, documented as illustrative)
  let totalReturnPct = baseline.totalReturnPct;
  totalReturnPct -= dBuy * 0.04;
  totalReturnPct += dSell * 0.02;
  totalReturnPct -= dCash * 8;
  totalReturnPct += dMaxPos * 6;

  let sharpeRatio = baseline.sharpeRatio;
  sharpeRatio += dBuy * 0.003;
  sharpeRatio -= dSl * 2;
  sharpeRatio -= dMaxPos * 1.5;

  let maxDrawdown = baseline.maxDrawdown;
  maxDrawdown += Math.max(0, dSl) * 0.8;
  maxDrawdown -= Math.max(0, -dSl) * 0.3;
  maxDrawdown += dMaxPos * 0.4;
  maxDrawdown -= Math.max(0, dTp) * 0.15;

  let turnover = baseline.turnover;
  turnover -= dBuy * 0.0015;
  turnover += Math.max(0, -dBuy) * 0.002;
  turnover += Math.abs(dSell) * 0.0008;

  let concentration = baseline.concentration;
  concentration += dMaxPos * 0.35;
  const energyCapDelta =
    (candidate.segment_caps.energy ?? 0) - (baseSpec.segment_caps.energy ?? 0);
  concentration += energyCapDelta * 0.2;

  maxDrawdown = Math.max(0.01, Math.min(0.85, maxDrawdown));
  turnover = Math.max(0.02, Math.min(0.95, turnover));
  concentration = Math.max(0.05, Math.min(0.9, concentration));

  return {
    totalReturnPct,
    sharpeRatio,
    maxDrawdown,
    turnover,
    concentration,
  };
}
