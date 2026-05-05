import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS } from "@/lib/diagnostics/constants";
import type { DiagnosticsPayload } from "@/lib/diagnostics/types";
import { cn } from "@/lib/utils";

function fmtPct(v: number | null | undefined, digits = 1) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
}

export function DiagnosticsSummaryStrip({ payload }: { payload: DiagnosticsPayload }) {
  const m = payload.metrics;
  const crit = payload.warnings.filter((w) => w.severity === "critical").length;
  const warn = payload.warnings.filter((w) => w.severity === "warning").length;
  const info = payload.warnings.filter((w) => w.severity === "info").length;
  const warnParts: string[] = [];
  if (crit > 0) warnParts.push(`${crit} critical`);
  if (warn > 0) warnParts.push(`${warn} warn`);
  if (info > 0) warnParts.push(`${info} info`);
  const warnSummary = warnParts.length > 0 ? warnParts.join(" · ") : "None";

  return (
    <Card className="border-border/80 shadow-sm">
      <CardHeader className="flex flex-col gap-1 border-b border-border/60 bg-muted/15 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base">Strategy diagnostics</CardTitle>
          <p className="text-xs font-normal text-muted-foreground">
            Last {DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS}-day window · same engine as{" "}
            <code className="rounded bg-muted px-1 py-0.5 text-[11px]">/api/diagnostics/summary</code>
          </p>
        </div>
        <Link
          href="/diagnostics"
          className="text-sm font-medium text-primary underline-offset-4 hover:underline"
        >
          Open full diagnostics →
        </Link>
      </CardHeader>
      <CardContent className="grid gap-3 pt-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-lg border border-border/60 bg-card px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Return</p>
          <p
            className={cn(
              "text-lg font-semibold tabular-nums",
              m.totalReturnPct == null && "text-muted-foreground",
              m.totalReturnPct != null && m.totalReturnPct >= 0 && "text-success",
              m.totalReturnPct != null && m.totalReturnPct < 0 && "text-danger",
            )}
          >
            {fmtPct(m.totalReturnPct, 2)}
          </p>
          {m.benchmarkReturnPct != null ? (
            <p className="text-xs text-muted-foreground">SPY {fmtPct(m.benchmarkReturnPct, 2)}</p>
          ) : (
            <p className="text-xs text-muted-foreground">Bench n/a</p>
          )}
        </div>
        <div className="rounded-lg border border-border/60 bg-card px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Sharpe (ann.)</p>
          <p className="text-lg font-semibold tabular-nums">{m.sharpeAnnualized != null ? m.sharpeAnnualized.toFixed(2) : "—"}</p>
          <p className="text-xs text-muted-foreground">Daily snapshot curve</p>
        </div>
        <div className="rounded-lg border border-border/60 bg-card px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Max drawdown</p>
          <p className="text-lg font-semibold tabular-nums text-danger">
            {m.maxDrawdownPct != null ? `${(-Math.abs(m.maxDrawdownPct)).toFixed(2)}%` : "—"}
          </p>
          <p className="text-xs text-muted-foreground">Peak to trough</p>
        </div>
        <div className="rounded-lg border border-border/60 bg-card px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Closed trades</p>
          <p className="text-lg font-semibold tabular-nums">{m.closedTradeCount}</p>
          <p className="text-xs text-muted-foreground">FIFO round-trips</p>
        </div>
        <div className="rounded-lg border border-border/60 bg-card px-3 py-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Warnings</p>
          <p className="text-lg font-semibold tabular-nums leading-snug">
            <span className={crit > 0 ? "text-danger" : warn > 0 ? "text-amber-700 dark:text-amber-400" : "text-muted-foreground"}>
              {warnSummary}
            </span>
          </p>
          <p className="text-xs text-muted-foreground">Automated checks</p>
        </div>
      </CardContent>
    </Card>
  );
}
