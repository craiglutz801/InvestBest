"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";

export type ChartPoint = { t: string; value: number; benchmark?: number | null };

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

export function EquityBenchmarkChart({
  points,
  heightClassName = "h-72",
}: {
  points: ChartPoint[];
  /** Tailwind height class for the chart viewport (e.g. `h-52` for compact layouts). */
  heightClassName?: string;
}) {
  if (!points.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No portfolio snapshots yet. Trigger a run from Settings or wait for the hourly job.
      </p>
    );
  }

  const data = points.map((p) => ({
    ...p,
    label: fmtDate(p.t),
    bench: p.benchmark ?? undefined,
  }));

  return (
    <div className={cn(heightClassName, "w-full")}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={(v) =>
              v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : v >= 1e3 ? `${(v / 1e3).toFixed(0)}k` : String(v)
            }
          />
          <Tooltip
            formatter={(value: number, name: string) => [`$${value.toFixed(2)}`, name]}
            labelFormatter={(_, payload) => {
              const p = payload?.[0]?.payload as { t?: string } | undefined;
              return p?.t ? new Date(p.t).toLocaleString() : "";
            }}
          />
          <Legend />
          <Line type="monotone" dataKey="value" name="Portfolio" stroke="hsl(222 47% 35%)" dot={false} strokeWidth={2} />
          <Line
            type="monotone"
            dataKey="bench"
            name="SPY benchmark"
            stroke="hsl(142 76% 36%)"
            dot={false}
            strokeWidth={2}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
