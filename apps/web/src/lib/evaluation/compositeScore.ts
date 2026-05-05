import type { TrialMetrics } from "@/lib/research/types";

/**
 * Composite objective from addendum §6 (weights configurable).
 * Inputs should be normalized via `normalizeMetricsGroup` first.
 */
export type CompositeWeights = {
  totalReturn: number;
  sharpe: number;
  maxDrawdown: number;
  turnover: number;
  concentration: number;
};

export const DEFAULT_COMPOSITE_WEIGHTS: CompositeWeights = {
  totalReturn: 0.35,
  sharpe: 0.25,
  maxDrawdown: -0.2,
  turnover: -0.1,
  concentration: -0.1,
};

/** Min-max normalize each dimension across rows (higher is better; for costs we invert). */
export function normalizeMetricsGroup(rows: TrialMetrics[]): TrialMetrics[] {
  if (rows.length === 0) return [];

  const minmax = (key: keyof TrialMetrics, invert = false) => {
    const vals = rows.map((r) => r[key]);
    const lo = Math.min(...vals);
    const hi = Math.max(...vals);
    const span = hi - lo || 1;
    return rows.map((r) => {
      let v = (r[key] - lo) / span;
      if (invert) v = 1 - v;
      return v;
    });
  };

  const nRet = minmax("totalReturnPct");
  const nSharpe = minmax("sharpeRatio");
  const nDd = minmax("maxDrawdown", true);
  const nTo = minmax("turnover", true);
  const nConc = minmax("concentration", true);

  return rows.map((_, i) => ({
    totalReturnPct: nRet[i]!,
    sharpeRatio: nSharpe[i]!,
    maxDrawdown: nDd[i]!,
    turnover: nTo[i]!,
    concentration: nConc[i]!,
  }));
}

export function compositeScore(
  normalized: TrialMetrics,
  weights: CompositeWeights = DEFAULT_COMPOSITE_WEIGHTS,
): number {
  return (
    weights.totalReturn * normalized.totalReturnPct +
    weights.sharpe * normalized.sharpeRatio +
    weights.maxDrawdown * normalized.maxDrawdown +
    weights.turnover * normalized.turnover +
    weights.concentration * normalized.concentration
  );
}
