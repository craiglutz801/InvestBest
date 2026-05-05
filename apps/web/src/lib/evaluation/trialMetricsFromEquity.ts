import { maxDrawdownFromSeries, totalReturnPct } from "@/lib/performance/metrics";
import { toNum } from "@/lib/portfolio/math";
import type { TrialMetrics } from "@/lib/research/types";

function dailyReturns(values: number[]): number[] {
  const out: number[] = [];
  for (let i = 1; i < values.length; i++) {
    const a = values[i - 1];
    const b = values[i];
    if (a > 0) out.push((b - a) / a);
  }
  return out;
}

/** Annualized Sharpe from daily simple returns (trading days). */
export function sharpeFromDailyReturns(daily: number[], annualization = 252): number {
  if (daily.length < 5) return 0;
  const mean = daily.reduce((s, x) => s + x, 0) / daily.length;
  const variance = daily.reduce((s, x) => s + (x - mean) ** 2, 0) / daily.length;
  const std = Math.sqrt(variance);
  if (std < 1e-12) return 0;
  return (mean / std) * Math.sqrt(annualization);
}

/**
 * Build trial metrics from portfolio totalValue snapshots (read-only).
 * Turnover/concentration are placeholders when not derivable from snapshots alone.
 */
export function metricsFromEquitySnapshots(
  snaps: { totalValue: { toString(): string } }[],
  placeholders: { turnover: number; concentration: number } = { turnover: 0.12, concentration: 0.22 },
): TrialMetrics {
  if (snaps.length < 2) {
    return {
      totalReturnPct: 0,
      sharpeRatio: 0,
      maxDrawdown: 0,
      turnover: placeholders.turnover,
      concentration: placeholders.concentration,
    };
  }
  const vals = snaps.map((s) => toNum(s.totalValue));
  const start = vals[0]!;
  const end = vals[vals.length - 1]!;
  const daily = dailyReturns(vals);
  return {
    totalReturnPct: totalReturnPct(start, end),
    sharpeRatio: sharpeFromDailyReturns(daily),
    maxDrawdown: maxDrawdownFromSeries(vals),
    turnover: placeholders.turnover,
    concentration: placeholders.concentration,
  };
}

export const DEMO_BASELINE_METRICS: TrialMetrics = {
  totalReturnPct: 4.2,
  sharpeRatio: 0.85,
  maxDrawdown: 0.09,
  turnover: 0.18,
  concentration: 0.28,
};
