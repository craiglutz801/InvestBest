"use client";

import { Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, YAxis } from "recharts";

export type PositionValuePoint = { t: string; value: number };

export function PositionValueMiniChart({
  points,
  costBasisValue,
}: {
  points: PositionValuePoint[];
  costBasisValue: number;
}) {
  if (points.length < 2) {
    return <span className="text-xs text-muted-foreground">Need more history</span>;
  }

  const first = points[0]!.value;
  const last = points[points.length - 1]!.value;
  const positive = last >= first;
  const stroke = positive ? "hsl(142 76% 36%)" : "hsl(0 72% 51%)";

  const data = points.map((p) => ({
    ...p,
    label: new Date(p.t).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
  }));

  return (
    <div className="h-14 w-[148px] shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 4, left: 0, bottom: 0 }}>
          <YAxis domain={["auto", "auto"]} hide width={0} />
          <Tooltip
            contentStyle={{ fontSize: 11 }}
            formatter={(v: number) => [`$${v.toFixed(2)}`, "Position value"]}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as { t?: string } | undefined;
              return row?.t ? new Date(row.t).toLocaleString() : "";
            }}
          />
          <ReferenceLine
            y={costBasisValue}
            stroke="hsl(220 9% 46% / 0.45)"
            strokeDasharray="4 4"
            strokeWidth={1}
          />
          <Area
            type="monotone"
            dataKey="value"
            stroke={stroke}
            fill={stroke}
            fillOpacity={0.12}
            strokeWidth={1.5}
            dot={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
