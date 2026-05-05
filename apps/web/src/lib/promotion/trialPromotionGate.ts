import { TRIAL_PROMOTION_THRESHOLDS } from "@/lib/evaluation/metricThresholds";
import type { ScoredVariant, TrialMetrics } from "@/lib/research/types";

export type PromotionResult = {
  approved: boolean;
  candidateName: string | null;
  reason: string;
};

/**
 * Deterministic gate: pick best composite among variants, then check risk constraints vs baseline.
 */
export function runTrialPromotionGate(
  baselineComposite: number,
  baselineMetrics: TrialMetrics,
  variants: ScoredVariant[],
): PromotionResult {
  if (variants.length === 0) {
    return { approved: false, candidateName: null, reason: "No candidate variants to evaluate." };
  }

  const sorted = [...variants].sort((a, b) => b.compositeScore - a.compositeScore);
  const best = sorted[0]!;
  const margin = best.compositeScore - baselineComposite;

  if (margin < TRIAL_PROMOTION_THRESHOLDS.minCompositeMargin) {
    return {
      approved: false,
      candidateName: best.proposal.name,
      reason: `Best challenger composite (${best.compositeScore.toFixed(4)}) did not beat baseline (${baselineComposite.toFixed(4)}) by ≥ ${TRIAL_PROMOTION_THRESHOLDS.minCompositeMargin} (trial margin).`,
    };
  }

  const ddWorse = best.metrics.maxDrawdown - baselineMetrics.maxDrawdown;
  if (ddWorse > TRIAL_PROMOTION_THRESHOLDS.maxDrawdownWorsening) {
    return {
      approved: false,
      candidateName: best.proposal.name,
      reason: `Drawdown worsened by ${ddWorse.toFixed(3)} vs allowed ${TRIAL_PROMOTION_THRESHOLDS.maxDrawdownWorsening}.`,
    };
  }

  const toBase = baselineMetrics.turnover;
  const toCand = best.metrics.turnover;
  if (toBase > 0 && (toCand - toBase) / toBase > TRIAL_PROMOTION_THRESHOLDS.maxTurnoverIncreasePct) {
    return {
      approved: false,
      candidateName: best.proposal.name,
      reason: `Turnover increased too much vs baseline (${((100 * (toCand - toBase)) / toBase).toFixed(1)}%).`,
    };
  }

  return {
    approved: true,
    candidateName: best.proposal.name,
    reason: `Challenger "${best.proposal.name}" clears trial gates: composite margin ${margin.toFixed(4)}, drawdown & turnover within limits.`,
  };
}
