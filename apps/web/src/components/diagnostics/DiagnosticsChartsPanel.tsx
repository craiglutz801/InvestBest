"use client";

import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { EquityBenchmarkChart } from "@/components/charts/EquityBenchmarkChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { DiagnosticsPayload } from "@/lib/diagnostics/types";

export function DiagnosticsChartsPanel({
  charts,
}: {
  charts: NonNullable<DiagnosticsPayload["charts"]>;
}) {
  const hasBench = charts.equity.some((p) => p.benchmark != null);

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="overflow-hidden border-border/80 shadow-sm">
        <CardHeader className="border-b border-border/60 bg-muted/20 py-3">
          <CardTitle className="text-base">Equity vs benchmark</CardTitle>
          <p className="text-xs font-normal text-muted-foreground">
            Portfolio total value through the selected window{hasBench ? " · SPY same-scale benchmark when logged" : ""}.
          </p>
        </CardHeader>
        <CardContent className="pt-4">
          <EquityBenchmarkChart points={charts.equity} heightClassName="h-52" />
        </CardContent>
      </Card>
      <Card className="overflow-hidden border-border/80 shadow-sm">
        <CardHeader className="border-b border-border/60 bg-muted/20 py-3">
          <CardTitle className="text-base">Drawdown</CardTitle>
          <p className="text-xs font-normal text-muted-foreground">
            Running peak-to-trough drawdown (%) from the same snapshots.
          </p>
        </CardHeader>
        <CardContent className="pt-4">
          <DrawdownChart points={charts.drawdown} heightClassName="h-52" gradientId="diag-dd-fill" />
        </CardContent>
      </Card>
    </div>
  );
}
