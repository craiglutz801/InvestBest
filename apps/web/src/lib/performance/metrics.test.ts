import { describe, expect, it } from "vitest";
import {
  maxDrawdownFromSeries,
  snapshotsToDrawdownSeries,
  snapshotsToEquitySeries,
  totalReturnPct,
} from "./metrics";

function snap(date: string, totalValue: number, benchmarkValue?: number) {
  return {
    timestamp: new Date(date),
    totalValue,
    benchmarkValue: benchmarkValue ?? null,
  } as const;
}

describe("metrics", () => {
  it("totalReturnPct handles zero / negative starting cash", () => {
    expect(totalReturnPct(0, 1000)).toBe(0);
    expect(totalReturnPct(-100, 1000)).toBe(0);
    expect(totalReturnPct(100, 110)).toBeCloseTo(10, 4);
  });

  it("maxDrawdownFromSeries computes the worst peak-to-trough drop", () => {
    expect(maxDrawdownFromSeries([100, 110, 99, 105, 70, 80])).toBeCloseTo((110 - 70) / 110, 4);
    expect(maxDrawdownFromSeries([100])).toBe(0);
    expect(maxDrawdownFromSeries([])).toBe(0);
  });

  it("snapshotsToEquitySeries returns aligned points and matching maxDrawdown", () => {
    const snaps = [
      snap("2024-01-01", 100, 100),
      snap("2024-01-02", 110, 102),
      snap("2024-01-03", 90, 95),
    ];
    const r = snapshotsToEquitySeries(snaps);
    expect(r.points).toHaveLength(3);
    expect(r.points[0].t).toBe(new Date("2024-01-01").toISOString());
    expect(r.points[0].benchmark).toBe(100);
    expect(r.maxDrawdown).toBeCloseTo((110 - 90) / 110, 4);
  });

  it("snapshotsToDrawdownSeries yields running drawdowns ≤ 0", () => {
    const snaps = [
      snap("2024-01-01", 100),
      snap("2024-01-02", 110),
      snap("2024-01-03", 99),
      snap("2024-01-04", 120),
    ];
    const dd = snapshotsToDrawdownSeries(snaps);
    expect(dd).toHaveLength(4);
    expect(dd[0].ddPct).toBe(0);
    expect(dd[1].ddPct).toBe(0);
    expect(dd[2].ddPct).toBeCloseTo(((99 - 110) / 110) * 100, 4);
    expect(dd[3].ddPct).toBe(0);
    for (const p of dd) expect(p.ddPct).toBeLessThanOrEqual(0);
  });
});
