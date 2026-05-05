function mean(xs: number[]): number {
  if (xs.length === 0) return 0;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}

function sampleStd(xs: number[]): number {
  if (xs.length < 2) return 0;
  const m = mean(xs);
  const v = mean(xs.map((x) => (x - m) ** 2));
  return Math.sqrt(v);
}

/** Last snapshot value per calendar day (UTC); input snaps must be sorted ascending by time. */
export function dailyTotalValuesFromSnapshots(
  snaps: { timestamp: Date; totalValue: number }[],
): { date: string; value: number }[] {
  const byDay = new Map<string, number>();
  for (const s of snaps) {
    const date = s.timestamp.toISOString().slice(0, 10);
    byDay.set(date, s.totalValue);
  }
  return [...byDay.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([date, value]) => ({ date, value }));
}

export function dailyReturnsFromTotalValues(series: { date: string; value: number }[]): number[] {
  const rets: number[] = [];
  for (let i = 1; i < series.length; i++) {
    const prev = series[i - 1]!.value;
    const cur = series[i]!.value;
    if (prev > 1e-9) rets.push((cur - prev) / prev);
  }
  return rets;
}

/** Annualized Sharpe from daily returns (252 trading days). `riskFreeDaily` optional. */
export function sharpeAnnualized(dailyReturns: number[], riskFreeDaily = 0): number | null {
  if (dailyReturns.length < 8) return null;
  const excess = dailyReturns.map((r) => r - riskFreeDaily);
  const sd = sampleStd(excess);
  if (sd < 1e-12) return null;
  return (mean(excess) / sd) * Math.sqrt(252);
}

/** Annualized Sortino using downside deviation vs zero target (daily). */
export function sortinoAnnualized(dailyReturns: number[], riskFreeDaily = 0): number | null {
  if (dailyReturns.length < 8) return null;
  const excess = dailyReturns.map((r) => r - riskFreeDaily);
  const downside = excess.map((r) => Math.min(0, r));
  const dd = Math.sqrt(mean(downside.map((d) => d * d)));
  if (dd < 1e-12) return null;
  return (mean(excess) / dd) * Math.sqrt(252);
}

export function maxDrawdownFromValues(values: number[]): number {
  if (values.length < 2) return 0;
  let peak = values[0]!;
  let maxDd = 0;
  for (const v of values) {
    if (v > peak) peak = v;
    const dd = peak > 0 ? (peak - v) / peak : 0;
    if (dd > maxDd) maxDd = dd;
  }
  return maxDd;
}
