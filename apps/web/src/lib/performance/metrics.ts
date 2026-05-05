import { toNum } from "@/lib/portfolio/math";

export type EquityPoint = { t: string; value: number; benchmark?: number | null };

/** Max drawdown from monotonic-ish equity series (local peaks). */
export function maxDrawdownFromSeries(values: number[]): number {
  if (values.length < 2) return 0;
  let peak = values[0];
  let maxDd = 0;
  for (const v of values) {
    if (v > peak) peak = v;
    const dd = peak > 0 ? (peak - v) / peak : 0;
    if (dd > maxDd) maxDd = dd;
  }
  return maxDd;
}

export function totalReturnPct(starting: number, current: number): number {
  if (starting <= 0) return 0;
  return ((current - starting) / starting) * 100;
}

/** Parse portfolio snapshots to chart points + drawdown on totalValue */
export function snapshotsToEquitySeries(
  snaps: { timestamp: Date; totalValue: { toString(): string }; benchmarkValue?: { toString(): string } | null }[],
): { points: EquityPoint[]; maxDrawdown: number } {
  const vals = snaps.map((s) => toNum(s.totalValue));
  const points = snaps.map((s) => ({
    t: s.timestamp.toISOString(),
    value: toNum(s.totalValue),
    benchmark: s.benchmarkValue != null ? toNum(s.benchmarkValue) : null,
  }));
  return { points, maxDrawdown: maxDrawdownFromSeries(vals) };
}

export type DrawdownPoint = { t: string; ddPct: number };

/**
 * Build the running drawdown series (% from running peak) from the equity curve. Each point
 * is `<= 0`. Useful for visualizing how deep and how long pullbacks last.
 */
export function snapshotsToDrawdownSeries(
  snaps: { timestamp: Date; totalValue: { toString(): string } }[],
): DrawdownPoint[] {
  const out: DrawdownPoint[] = [];
  let peak = 0;
  for (const s of snaps) {
    const v = toNum(s.totalValue);
    if (v > peak) peak = v;
    const dd = peak > 0 ? ((v - peak) / peak) * 100 : 0;
    out.push({ t: s.timestamp.toISOString(), ddPct: dd });
  }
  return out;
}
