import type { DiagnosticsBucketRow } from "@/lib/diagnostics/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

function Pnl({ v }: { v: number }) {
  const pos = v >= 0;
  return (
    <span className={cn("tabular-nums", pos ? "text-success" : "text-danger")}>
      {pos ? "+" : ""}
      {v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
    </span>
  );
}

export function AttributionTable({
  title,
  rows,
  description,
}: {
  title: string;
  rows: DiagnosticsBucketRow[];
  description?: string;
}) {
  return (
    <Card className="overflow-hidden border-border/80 shadow-sm">
      <CardHeader className="border-b border-border/60 bg-muted/20 pb-3">
        <CardTitle className="text-base font-semibold">{title}</CardTitle>
        {description ? <p className="text-xs font-normal text-muted-foreground">{description}</p> : null}
      </CardHeader>
      <CardContent className="p-0">
        {rows.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">No rows — need closed round-trips in this window.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <th className="px-4 py-2.5">Name</th>
                  <th className="px-4 py-2.5 text-right">Trades</th>
                  <th className="px-4 py-2.5 text-right">Win rate</th>
                  <th className="px-4 py-2.5 text-right">Realized P&amp;L</th>
                  <th className="px-4 py-2.5 text-right">Avg / trade</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.key} className="border-b border-border/60 last:border-0 hover:bg-muted/20">
                    <td className="px-4 py-2 font-medium">{r.label}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">{r.trades}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                      {r.winRatePct != null ? `${r.winRatePct.toFixed(1)}%` : "—"}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Pnl v={r.realizedPnl} />
                    </td>
                    <td className="px-4 py-2 text-right tabular-nums">
                      <Pnl v={r.avgPnl} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
