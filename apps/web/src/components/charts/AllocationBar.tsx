"use client";

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";

const COLORS = [
  "hsl(222 47% 45%)",
  "hsl(200 80% 45%)",
  "hsl(280 65% 50%)",
  "hsl(30 90% 48%)",
  "hsl(142 76% 36%)",
  "hsl(340 75% 52%)",
];

export function AllocationChart({ data }: { data: { name: string; value: number }[] }) {
  if (!data.length) return null;
  return (
    <div className="h-56 w-full max-w-md">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" outerRadius={80} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
