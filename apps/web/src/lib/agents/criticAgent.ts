import type { TrialMetrics } from "@/lib/research/types";
import { TRIAL_PROMOTION_THRESHOLDS } from "@/lib/evaluation/metricThresholds";

/**
 * Rule-based critic (MVP). Optional LLM layer can be added later — v1 stays deterministic.
 */
export function runCriticAgent(input: {
  baseline: TrialMetrics;
  candidate: TrialMetrics;
  candidateName: string;
}): string[] {
  const notes: string[] = [];
  const dd = input.candidate.maxDrawdown - input.baseline.maxDrawdown;
  if (dd > TRIAL_PROMOTION_THRESHOLDS.maxDrawdownWorsening) {
    notes.push(`Drawdown concern: +${(dd * 100).toFixed(2)}pp vs baseline (threshold ${(TRIAL_PROMOTION_THRESHOLDS.maxDrawdownWorsening * 100).toFixed(0)}pp).`);
  }
  const to = input.baseline.turnover > 0 ? (input.candidate.turnover - input.baseline.turnover) / input.baseline.turnover : 0;
  if (to > TRIAL_PROMOTION_THRESHOLDS.maxTurnoverIncreasePct) {
    notes.push(`Turnover increased ${(to * 100).toFixed(0)}% vs baseline — watch over-trading / overfitting.`);
  }
  if (input.candidate.sharpeRatio < input.baseline.sharpeRatio - 0.15) {
    notes.push("Sharpe materially lower — unstable improvement?");
  }
  if (notes.length === 0) {
    notes.push(`Critic: no hard red flags for "${input.candidateName}" under trial thresholds.`);
  }
  return notes;
}
