"use client";

import { PositionValueMiniChart, type PositionValuePoint } from "@/components/charts/PositionValueMiniChart";
import { cn } from "@/lib/utils";

export type HoldingsPerformanceRow = {
  ticker: string;
  marketValue: number;
  unrealizedPct: number;
  valueHistory: PositionValuePoint[];
  costBasisValue: number;
  vsLastSnapshotPct: number | null;
  dayOverDayPct: number | null;
};

function fmtPct(v: number | null) {
  if (v == null || Number.isNaN(v)) return "—";
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(2)}%`;
}

export function DashboardHoldingsPerformance({ rows }: { rows: HoldingsPerformanceRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No open positions. Run the agent to open paper trades.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {rows.map((r) => (
        <div key={r.ticker} className="rounded-lg border border-border bg-muted/20 p-3">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="font-semibold">{r.ticker}</p>
              <p className="text-xs text-muted-foreground tabular-nums">${r.marketValue.toLocaleString(undefined, { maximumFractionDigits: 2 })} now</p>
            </div>
            <span
              className={cn(
                "shrink-0 text-sm font-medium tabular-nums",
                r.unrealizedPct >= 0 ? "text-success" : "text-danger",
              )}
            >
              {r.unrealizedPct >= 0 ? "+" : ""}
              {r.unrealizedPct.toFixed(2)}% vs cost
            </span>
          </div>
          <p className="mt-1 text-[10px] text-muted-foreground">
            Dashed line = cost at open · Area = value after each completed run (live quote at run end, not the stale daily bar)
          </p>
          <div className="mt-2 flex justify-center">
            <PositionValueMiniChart points={r.valueHistory} costBasisValue={r.costBasisValue} />
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
            <span title="Last two distinct daily marks in the database">DoD {fmtPct(r.dayOverDayPct)}</span>
            <span title="Current quote vs most recent stored daily close">vs last bar {fmtPct(r.vsLastSnapshotPct)}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
