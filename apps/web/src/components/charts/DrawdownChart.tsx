"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { cn } from "@/lib/utils";

export type DrawdownChartPoint = { t: string; ddPct: number };

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric" });
  } catch {
    return iso;
  }
}

export function DrawdownChart({
  points,
  heightClassName = "h-56",
  /** Unique SVG gradient id when multiple drawdown charts mount on one page. */
  gradientId = "dd-fill",
}: {
  points: DrawdownChartPoint[];
  heightClassName?: string;
  gradientId?: string;
}) {
  if (!points.length) {
    return (
      <p className="text-sm text-muted-foreground">
        No portfolio snapshots yet. Drawdown appears once the agent records its first run.
      </p>
    );
  }

  const data = points.map((p) => ({ ...p, label: fmtDate(p.t) }));
  const minDd = data.reduce((m, p) => (p.ddPct < m ? p.ddPct : m), 0);
  const yMin = Math.min(0, Math.floor(minDd) - 1);

  return (
    <div className={cn(heightClassName, "w-full")}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="1" x2="0" y2="0">
              <stop offset="0%" stopColor="hsl(0 72% 51%)" stopOpacity={0.55} />
              <stop offset="100%" stopColor="hsl(0 72% 51%)" stopOpacity={0.05} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis
            tick={{ fontSize: 11 }}
            domain={[yMin, 0]}
            tickFormatter={(v) => `${v.toFixed(0)}%`}
          />
          <Tooltip
            formatter={(value: number) => [`${value.toFixed(2)}%`, "Drawdown"]}
            labelFormatter={(_, payload) => {
              const p = payload?.[0]?.payload as { t?: string } | undefined;
              return p?.t ? new Date(p.t).toLocaleString() : "";
            }}
          />
          <Area
            type="monotone"
            dataKey="ddPct"
            stroke="hsl(0 72% 51%)"
            strokeWidth={2}
            fill={`url(#${gradientId})`}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
