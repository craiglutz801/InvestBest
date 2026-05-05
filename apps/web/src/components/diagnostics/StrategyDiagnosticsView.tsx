"use client";

import { useCallback, useEffect, useState } from "react";
import { AttributionTable } from "@/components/diagnostics/AttributionTable";
import { DiagnosticWarnings } from "@/components/diagnostics/DiagnosticWarnings";
import { DiagnosticsChartsPanel } from "@/components/diagnostics/DiagnosticsChartsPanel";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ClosedTradeSummary, DiagnosticsPayload } from "@/lib/diagnostics/types";
import { cn } from "@/lib/utils";

type WindowChoice = "30" | "90" | "180" | "365" | "all";

function fmtPct(v: number | null | undefined, digits = 2) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${v.toFixed(digits)}%`;
}

function fmtMoney(v: number | null | undefined) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}$${Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function MetricTile({
  label,
  value,
  sub,
  emphasize,
}: {
  label: string;
  value: string;
  sub?: string | null;
  emphasize?: "positive" | "negative" | "neutral";
}) {
  return (
    <div className="rounded-xl border border-border/80 bg-card p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-1 text-xl font-semibold tabular-nums tracking-tight",
          emphasize === "positive" && "text-success",
          emphasize === "negative" && "text-danger",
        )}
      >
        {value}
      </p>
      {sub ? <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

function TradeLeaderboard({
  title,
  trades,
}: {
  title: string;
  trades: ClosedTradeSummary[];
}) {
  return (
    <Card className="overflow-hidden border-border/80 shadow-sm">
      <CardHeader className="border-b border-border/60 bg-muted/20 py-3">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {trades.length === 0 ? (
          <p className="p-4 text-sm text-muted-foreground">No data.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/30 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2">Time</th>
                  <th className="px-3 py-2">Symbol</th>
                  <th className="px-3 py-2 text-right">P&amp;L</th>
                  <th className="px-3 py-2 text-right">Hold</th>
                  <th className="px-3 py-2">Exit</th>
                  <th className="px-3 py-2">Regime</th>
                  <th className="px-3 py-2">Trigger</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t) => (
                  <tr key={t.id} className="border-b border-border/60 last:border-0 hover:bg-muted/15">
                    <td className="px-3 py-2 whitespace-nowrap text-muted-foreground">
                      {new Date(t.executedAt).toLocaleString(undefined, {
                        month: "short",
                        day: "numeric",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </td>
                    <td className="px-3 py-2 font-medium">{t.ticker}</td>
                    <td className={cn("px-3 py-2 text-right tabular-nums font-medium", t.realizedPnl >= 0 ? "text-success" : "text-danger")}>
                      {fmtMoney(t.realizedPnl)}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums text-muted-foreground">{t.holdingDays}d</td>
                    <td className="max-w-[140px] truncate px-3 py-2 text-muted-foreground" title={t.exitReason ?? ""}>
                      {t.exitReason ?? "—"}
                    </td>
                    <td className="px-3 py-2 capitalize text-muted-foreground">{t.regimeAtSellRun}</td>
                    <td className="px-3 py-2 text-muted-foreground">{t.triggerSource}</td>
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

const TAB_KEYS = [
  { id: "symbol", label: "Symbol" },
  { id: "segment", label: "Segment" },
  { id: "exit", label: "Exit reason" },
  { id: "entry", label: "Entry score" },
  { id: "regime", label: "SPY regime" },
  { id: "hold", label: "Hold period" },
  { id: "trigger", label: "Trigger" },
  { id: "vol", label: "Volatility" },
  { id: "family", label: "Strategy" },
  { id: "dow", label: "Exit weekday" },
] as const;

type TabId = (typeof TAB_KEYS)[number]["id"];

export function StrategyDiagnosticsView() {
  const [windowChoice, setWindowChoice] = useState<WindowChoice>("90");
  const [useCached, setUseCached] = useState(false);
  const [tab, setTab] = useState<TabId>("symbol");
  const [payload, setPayload] = useState<DiagnosticsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [rebuildMsg, setRebuildMsg] = useState<string | null>(null);
  const [rebuilding, setRebuilding] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (useCached) {
        const res = await fetch("/api/diagnostics/attribution?cached=1", { cache: "no-store" });
        const data = (await res.json()) as { source: string; payload: DiagnosticsPayload | null };
        if (!res.ok) throw new Error((data as { error?: string }).error ?? res.statusText);
        setPayload(data.payload);
        return;
      }

      const params = new URLSearchParams();
      if (windowChoice === "all") params.set("all", "1");
      else params.set("windowDays", windowChoice);
      const res = await fetch(`/api/diagnostics/attribution?${params}`, { cache: "no-store" });
      const data = (await res.json()) as { source: "live"; payload: DiagnosticsPayload };
      if (!res.ok) throw new Error((data as { error?: string }).error ?? res.statusText);
      setPayload(data.payload);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [windowChoice, useCached]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onRebuild() {
    setRebuilding(true);
    setRebuildMsg(null);
    try {
      const body =
        windowChoice === "all"
          ? { all: true }
          : { windowDays: Number(windowChoice) };
      const res = await fetch("/api/diagnostics/rebuild", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await res.json()) as { ok?: boolean; snapshotId?: string; error?: string };
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setRebuildMsg(`Snapshot saved (${data.snapshotId?.slice(0, 8)}…).`);
    } catch (e) {
      setRebuildMsg(e instanceof Error ? e.message : "Rebuild failed");
    } finally {
      setRebuilding(false);
    }
  }

  const m = payload?.metrics;
  const tables = payload?.tables;

  const activeRows =
    tables == null
      ? []
      : tab === "symbol"
        ? tables.bySymbol
        : tab === "segment"
          ? tables.bySegment
          : tab === "exit"
            ? tables.byExitReason
            : tab === "entry"
              ? tables.byEntryScoreBucket
              : tab === "regime"
                ? tables.byRegime
                : tab === "hold"
                  ? tables.byHoldingPeriod
                  : tab === "trigger"
                    ? tables.byTriggerSource
                    : tab === "vol"
                      ? tables.byVolatilityRegime
                      : tab === "family"
                        ? tables.byStrategyFamily
                        : tables.byExitDayOfWeek;

  const tabTitle =
    TAB_KEYS.find((x) => x.id === tab)?.label ?? "Attribution";

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 border-b border-border/60 pb-6 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Strategy diagnostics</h1>
          <p className="mt-1 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            Attribution built from <strong className="font-medium text-foreground">FIFO closed lots</strong> in your
            paper ledger, joined to decision-run regime logs (SPY bullish / neutral / bearish) and scheduler trigger
            source. Use this to see what is driving realized P&amp;L before changing rules — Sprint&nbsp;3 backtests
            turn hypotheses into evidence.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="hidden sm:inline">Window</span>
            <select
              value={windowChoice}
              onChange={(e) => setWindowChoice(e.target.value as WindowChoice)}
              disabled={useCached}
              className="rounded-md border border-input bg-background px-2 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <option value="30">30 days</option>
              <option value="90">90 days</option>
              <option value="180">180 days</option>
              <option value="365">365 days</option>
              <option value="all">All time</option>
            </select>
          </label>
          <label className="flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={useCached}
              onChange={(e) => setUseCached(e.target.checked)}
              className="rounded border-input"
            />
            Cached snapshot
          </label>
          <Button type="button" variant="secondary" size="sm" onClick={() => void load()} disabled={loading}>
            {loading ? "Loading…" : "Refresh"}
          </Button>
          <Button type="button" size="sm" onClick={() => void onRebuild()} disabled={rebuilding || useCached}>
            {rebuilding ? "Saving…" : "Save snapshot"}
          </Button>
        </div>
      </div>

      {rebuildMsg ? (
        <p className="text-sm text-muted-foreground" role="status">
          {rebuildMsg}
        </p>
      ) : null}

      {error ? (
        <div className="rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      {useCached && !loading && !error && !payload ? (
        <p className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
          No saved diagnostics snapshot yet. Turn off &quot;Cached snapshot&quot; for live analysis, or click{" "}
          <strong className="font-medium text-foreground">Save snapshot</strong> while in live mode first.
        </p>
      ) : null}

      {payload ? (
        <>
          <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>
              {useCached ? "Saved snapshot" : "Live"} · Generated {new Date(payload.generatedAt).toLocaleString()}
              {payload.snapshotId ? ` · id ${payload.snapshotId.slice(0, 8)}…` : null}
            </span>
            <span>
              Window {new Date(payload.windowStart).toLocaleDateString()} — {new Date(payload.windowEnd).toLocaleDateString()}
            </span>
          </div>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Signals</h2>
            <DiagnosticWarnings warnings={payload.warnings} />
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Portfolio path</h2>
            {payload.charts && payload.charts.equity.length > 0 ? (
              <DiagnosticsChartsPanel charts={payload.charts} />
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-6 text-center text-sm text-muted-foreground">
                No portfolio snapshots in this window — charts fill in once the agent records equity points.
                {useCached
                  ? " Older snapshots may omit chart series; switch to Live and click Save snapshot to refresh."
                  : null}
              </div>
            )}
          </section>

          <section className="space-y-3">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Portfolio metrics</h2>
            {m?.openNote ? <p className="text-xs text-muted-foreground">{m.openNote}</p> : null}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <MetricTile
                label="Total return"
                value={fmtPct(m?.totalReturnPct)}
                sub={m?.benchmarkReturnPct != null ? `vs SPY bench ${fmtPct(m.benchmarkReturnPct)}` : "Benchmark n/a in window"}
                emphasize={
                  m?.totalReturnPct == null
                    ? "neutral"
                    : m.totalReturnPct >= 0
                      ? "positive"
                      : "negative"
                }
              />
              <MetricTile
                label="Excess vs benchmark"
                value={fmtPct(m?.excessReturnPct)}
                emphasize={
                  m?.excessReturnPct == null
                    ? "neutral"
                    : m.excessReturnPct >= 0
                      ? "positive"
                      : "negative"
                }
              />
              <MetricTile label="Max drawdown" value={fmtPct(m?.maxDrawdownPct != null ? -Math.abs(m.maxDrawdownPct) : null)} emphasize="negative" />
              <MetricTile
                label="Sharpe (ann.)"
                value={m?.sharpeAnnualized != null ? m.sharpeAnnualized.toFixed(2) : "—"}
                sub="From daily portfolio snapshots"
              />
              <MetricTile
                label="Sortino (ann.)"
                value={m?.sortinoAnnualized != null ? m.sortinoAnnualized.toFixed(2) : "—"}
              />
              <MetricTile
                label="Win rate (closed)"
                value={m?.winRatePct != null ? `${m.winRatePct.toFixed(1)}%` : "—"}
                sub={`${m?.closedTradeCount ?? 0} round-trips`}
              />
              <MetricTile label="Profit factor" value={m?.profitFactor != null ? m.profitFactor.toFixed(2) : "—"} />
              <MetricTile label="Expectancy / trade" value={fmtMoney(m?.expectancyPerTrade)} />
              <MetricTile label="Avg win" value={fmtMoney(m?.avgWin)} emphasize="positive" />
              <MetricTile label="Avg loss" value={fmtMoney(m?.avgLoss)} emphasize="negative" />
              <MetricTile label="Avg hold (days)" value={m?.avgHoldingDays != null ? m.avgHoldingDays.toFixed(1) : "—"} />
              <MetricTile
                label="Turnover / avg NAV"
                value={m?.turnoverApproxPct != null ? `${m.turnoverApproxPct.toFixed(1)}%` : "—"}
                sub="Σ |trade gross| / mean portfolio"
              />
              <MetricTile label="Exposure (latest)" value={m?.exposurePctLatest != null ? `${m.exposurePctLatest.toFixed(1)}%` : "—"} />
              <MetricTile label="Cash (latest)" value={m?.cashPctLatest != null ? `${m.cashPctLatest.toFixed(1)}%` : "—"} />
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <TradeLeaderboard title="Best closed trades" trades={payload.trades.best} />
            <TradeLeaderboard title="Worst closed trades" trades={payload.trades.worst} />
          </section>

          <section className="space-y-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Attribution tables</h2>
              <div className="flex flex-wrap gap-1">
                {TAB_KEYS.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => setTab(t.id)}
                    className={cn(
                      "rounded-full px-3 py-1 text-xs font-medium transition-colors",
                      tab === t.id ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground hover:bg-muted/80",
                    )}
                  >
                    {t.label}
                  </button>
                ))}
              </div>
            </div>
            <AttributionTable
              title={tabTitle}
              rows={activeRows}
              description="Sorted by realized P&amp;L (desc). Win rate is share of trades with positive realized P&amp;L in each bucket."
            />
          </section>
        </>
      ) : !loading && !error ? (
        <p className="text-sm text-muted-foreground">No payload.</p>
      ) : null}
    </div>
  );
}
