"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const RESET_STARTING_CASH = 100_000;

type ProgressEntry = {
  at: string;
  phase: string;
  message: string;
  detail?: string | null;
};

type HoldingsMarkRow = {
  ticker: string;
  quantity: number;
  marketValue: number;
  costBasis: number;
  unrealizedPnl: number;
  unrealizedPct: number;
  ret1d: number;
  ret5d: number;
  ret20d: number;
};

type RunPollPayload = {
  id: string;
  status: string;
  buysCount: number;
  sellsCount: number;
  progressLog: ProgressEntry[];
  finishedAt: string | null;
  holdingsMarkBefore?: HoldingsMarkRow[];
  holdingsMarkAfter?: HoldingsMarkRow[];
};

const POLL_MS = 750;

const phaseStyles: Record<string, string> = {
  start: "bg-muted text-foreground",
  ingest: "bg-primary/10 text-primary",
  portfolio: "bg-muted",
  valuation: "bg-muted",
  sells: "bg-amber-500/15 text-amber-800 dark:text-amber-200",
  sell: "bg-danger/15 text-danger",
  buys: "bg-blue-500/10 text-blue-800 dark:text-blue-200",
  buy: "bg-success/15 text-success",
  regime: "bg-indigo-500/10 text-indigo-800 dark:text-indigo-200",
  universe: "bg-muted",
  holdings: "bg-violet-500/10 text-violet-800 dark:text-violet-200",
  snapshot: "bg-muted",
  done: "bg-success/20 text-success",
  error: "bg-destructive/15 text-destructive",
};

export type AgentRunMonitorProps = {
  onPaperReset?: () => void;
};

export function AgentRunMonitor({ onPaperReset }: AgentRunMonitorProps) {
  const router = useRouter();
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [progressLog, setProgressLog] = useState<ProgressEntry[]>([]);
  const [buysCount, setBuysCount] = useState(0);
  const [sellsCount, setSellsCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [holdingsBefore, setHoldingsBefore] = useState<HoldingsMarkRow[]>([]);
  const [holdingsAfter, setHoldingsAfter] = useState<HoldingsMarkRow[]>([]);
  const [clearModalOpen, setClearModalOpen] = useState(false);
  const [resetSure, setResetSure] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);
  const logEndRef = useRef<HTMLDivElement>(null);
  const clearPanelRef = useRef<HTMLDivElement>(null);

  const tapeFmt = (x: number) => {
    const s = x >= 0 ? "+" : "";
    return `${s}${(x * 100).toFixed(2)}%`;
  };

  const scrollToBottom = useCallback(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [progressLog, scrollToBottom]);

  const closeClearModal = useCallback(() => {
    setClearModalOpen(false);
    setResetSure(false);
    setResetMsg(null);
  }, []);

  useEffect(() => {
    if (!clearModalOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeClearModal();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [clearModalOpen, closeClearModal]);

  useEffect(() => {
    if (!clearModalOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [clearModalOpen]);

  useEffect(() => {
    if (!clearModalOpen) return;
    clearPanelRef.current?.querySelector<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")?.focus();
  }, [clearModalOpen]);

  useEffect(() => {
    if (!activeRunId) return;

    let cancelled = false;

    async function poll() {
      try {
        const res = await fetch(`/api/runs/${activeRunId}`, { cache: "no-store" });
        const data = (await res.json()) as RunPollPayload & { error?: string };
        if (!res.ok) {
          if (!cancelled) setError(data.error ?? res.statusText);
          return;
        }
        if (cancelled) return;
        setError(null);
        setStatus(data.status);
        setBuysCount(data.buysCount);
        setSellsCount(data.sellsCount);
        setProgressLog(Array.isArray(data.progressLog) ? data.progressLog : []);
        setHoldingsBefore(Array.isArray(data.holdingsMarkBefore) ? data.holdingsMarkBefore : []);
        setHoldingsAfter(Array.isArray(data.holdingsMarkAfter) ? data.holdingsMarkAfter : []);
        if (data.status === "completed" || data.status === "failed") {
          setActiveRunId(null);
          router.refresh();
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Poll failed");
      }
    }

    void poll();
    const t = setInterval(() => void poll(), POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [activeRunId, router]);

  async function startRun() {
    setStarting(true);
    setError(null);
    setProgressLog([]);
    setHoldingsBefore([]);
    setHoldingsAfter([]);
    setStatus("starting");
    try {
      const res = await fetch("/api/runs/trigger", { method: "POST", cache: "no-store" });
      const data = (await res.json().catch(() => ({}))) as {
        runId?: string | null;
        status?: string;
        error?: string;
      };
      if (!res.ok) throw new Error(data.error ?? res.statusText);

      // Happy path — wrapper returned an id we can poll on.
      if (data.runId && (data.status === "started" || data.status === "completed")) {
        setActiveRunId(data.runId);
        setStatus(data.status === "completed" ? "completed" : "running");
        if (data.status === "completed") router.refresh();
        return;
      }

      // Another run is already in flight — attach to it instead of erroring.
      if (data.status === "skipped_in_progress") {
        if (data.runId) {
          setActiveRunId(data.runId);
          setStatus("running");
          setError(
            data.error ?? "Another agent run is already in progress — attached to it; live progress below.",
          );
        } else {
          // No runId on the existing lock yet — fall back to the latest run for this user.
          try {
            const latest = await fetch("/api/runs/latest", { cache: "no-store" });
            const lj = (await latest.json().catch(() => ({}))) as { runId?: string | null };
            if (lj.runId) {
              setActiveRunId(lj.runId);
              setStatus("running");
              setError(data.error ?? "Another agent run is already in progress — attached to it.");
              return;
            }
          } catch {
            /* fall through to the soft message below. */
          }
          setStatus(null);
          setError(data.error ?? "Another agent run is already in progress. Try again in a moment.");
        }
        return;
      }

      // Anything else is a real failure.
      throw new Error(data.error ?? `Trigger returned status "${data.status ?? "unknown"}"`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
      setStatus(null);
    } finally {
      setStarting(false);
    }
  }

  async function clearHoldings() {
    setResetLoading(true);
    setResetMsg(null);
    try {
      const res = await fetch("/api/settings/reset-paper", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ acknowledged: true }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      onPaperReset?.();
      closeClearModal();
      router.refresh();
    } catch (err) {
      setResetMsg(err instanceof Error ? err.message : "Reset failed");
    } finally {
      setResetLoading(false);
    }
  }

  const busy = starting || (activeRunId != null && status === "running");

  return (
    <>
    <Card>
      <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <CardTitle className="text-base">Hourly agent</CardTitle>
          <p className="text-sm text-muted-foreground">
            Ingests the universe, <strong>marks open holdings</strong> (value, unrealized PnL, 1d / 5d / 20d
            share-price trends), then evaluates sells and buys. Most runs add <strong>no</strong> new
            positions when scores, cash, or limits do not justify a buy—watch the log for
            blocked/skip lines. Progress streams below while the run is active.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" onClick={startRun} disabled={busy}>
            {starting ? "Starting…" : busy ? "Running…" : "Run agent now"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="border-destructive/50 text-destructive hover:bg-destructive/10"
            disabled={busy}
            onClick={() => {
              setResetSure(false);
              setResetMsg(null);
              setClearModalOpen(true);
            }}
          >
            Clear holdings
          </Button>
          {status ? (
            <span
              className={cn(
                "rounded-md px-2 py-1 text-xs font-medium capitalize",
                status === "completed" || status === "failed" || status === "running"
                  ? status === "failed"
                    ? "bg-destructive/15 text-destructive"
                    : status === "completed"
                      ? "bg-success/15 text-success"
                      : "bg-muted"
                  : "bg-muted",
              )}
            >
              {status}
            </span>
          ) : null}
          <span className="text-xs text-muted-foreground tabular-nums">
            {sellsCount} sells · {buysCount} buys
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {error ? <p className="mb-3 text-sm text-destructive">{error}</p> : null}
        <div
          className="max-h-80 overflow-y-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs leading-relaxed"
          aria-live="polite"
        >
          {progressLog.length === 0 ? (
            <p className="text-muted-foreground">
              No log yet. Click &quot;Run agent now&quot; to ingest the universe, evaluate sells, then buys.
            </p>
          ) : (
            <ul className="space-y-2">
              {progressLog.map((e, i) => (
                <li key={`${e.at}-${i}`} className="border-b border-border/40 pb-2 last:border-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                        phaseStyles[e.phase] ?? "bg-muted",
                      )}
                    >
                      {e.phase}
                    </span>
                    <time className="text-[10px] text-muted-foreground">{new Date(e.at).toLocaleTimeString()}</time>
                  </div>
                  <p className="mt-1 text-foreground">{e.message}</p>
                  {e.detail ? (
                    <p className="mt-0.5 text-[11px] text-muted-foreground">{e.detail}</p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          <div ref={logEndRef} />
        </div>

        {holdingsBefore.length > 0 || holdingsAfter.length > 0 ? (
          <div className="mt-4 space-y-4">
            {holdingsBefore.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Holdings at start of run
                </p>
                <div className="overflow-x-auto rounded-md border border-border">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b bg-muted/40 text-muted-foreground">
                        <th className="px-2 py-1.5 font-medium">Symbol</th>
                        <th className="px-2 py-1.5 text-right font-medium">Value</th>
                        <th className="px-2 py-1.5 text-right font-medium">Cost</th>
                        <th className="px-2 py-1.5 text-right font-medium">PnL $</th>
                        <th className="px-2 py-1.5 text-right font-medium">PnL %</th>
                        <th className="px-2 py-1.5 text-right font-medium">1d</th>
                        <th className="px-2 py-1.5 text-right font-medium">5d</th>
                        <th className="px-2 py-1.5 text-right font-medium">20d</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdingsBefore.map((r) => (
                        <tr key={r.ticker} className="border-b border-border/50 last:border-0">
                          <td className="px-2 py-1.5 font-medium">{r.ticker}</td>
                          <td className="px-2 py-1.5 text-right tabular-nums">${r.marketValue.toFixed(2)}</td>
                          <td className="px-2 py-1.5 text-right tabular-nums">${r.costBasis.toFixed(2)}</td>
                          <td
                            className={cn(
                              "px-2 py-1.5 text-right tabular-nums",
                              r.unrealizedPnl >= 0 ? "text-success" : "text-danger",
                            )}
                          >
                            {r.unrealizedPnl >= 0 ? "+" : ""}
                            {r.unrealizedPnl.toFixed(2)}
                          </td>
                          <td
                            className={cn(
                              "px-2 py-1.5 text-right tabular-nums",
                              r.unrealizedPct >= 0 ? "text-success" : "text-danger",
                            )}
                          >
                            {r.unrealizedPct >= 0 ? "+" : ""}
                            {r.unrealizedPct.toFixed(2)}%
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                            {tapeFmt(r.ret1d)}
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                            {tapeFmt(r.ret5d)}
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                            {tapeFmt(r.ret20d)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
            {holdingsAfter.length > 0 ? (
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Holdings after this run
                </p>
                <div className="overflow-x-auto rounded-md border border-border">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b bg-muted/40 text-muted-foreground">
                        <th className="px-2 py-1.5 font-medium">Symbol</th>
                        <th className="px-2 py-1.5 text-right font-medium">Value</th>
                        <th className="px-2 py-1.5 text-right font-medium">Cost</th>
                        <th className="px-2 py-1.5 text-right font-medium">PnL $</th>
                        <th className="px-2 py-1.5 text-right font-medium">PnL %</th>
                        <th className="px-2 py-1.5 text-right font-medium">1d</th>
                        <th className="px-2 py-1.5 text-right font-medium">5d</th>
                        <th className="px-2 py-1.5 text-right font-medium">20d</th>
                      </tr>
                    </thead>
                    <tbody>
                      {holdingsAfter.map((r) => (
                        <tr key={r.ticker} className="border-b border-border/50 last:border-0">
                          <td className="px-2 py-1.5 font-medium">{r.ticker}</td>
                          <td className="px-2 py-1.5 text-right tabular-nums">${r.marketValue.toFixed(2)}</td>
                          <td className="px-2 py-1.5 text-right tabular-nums">${r.costBasis.toFixed(2)}</td>
                          <td
                            className={cn(
                              "px-2 py-1.5 text-right tabular-nums",
                              r.unrealizedPnl >= 0 ? "text-success" : "text-danger",
                            )}
                          >
                            {r.unrealizedPnl >= 0 ? "+" : ""}
                            {r.unrealizedPnl.toFixed(2)}
                          </td>
                          <td
                            className={cn(
                              "px-2 py-1.5 text-right tabular-nums",
                              r.unrealizedPct >= 0 ? "text-success" : "text-danger",
                            )}
                          >
                            {r.unrealizedPct >= 0 ? "+" : ""}
                            {r.unrealizedPct.toFixed(2)}%
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                            {tapeFmt(r.ret1d)}
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                            {tapeFmt(r.ret5d)}
                          </td>
                          <td className="px-2 py-1.5 text-right tabular-nums text-muted-foreground">
                            {tapeFmt(r.ret20d)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
            <p className="text-[10px] text-muted-foreground">
              1d / 5d / 20d columns are share-price moves from the latest daily series (tape), not your position
              dollar return. Unrealized PnL is vs your average cost.
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>

      {clearModalOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          role="presentation"
        >
          <button
            type="button"
            className="absolute inset-0 bg-black/50"
            aria-label="Close dialog"
            onClick={closeClearModal}
          />
          <div
            ref={clearPanelRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="clear-holdings-title"
            className="relative z-10 w-full max-w-lg rounded-lg border border-border bg-background p-6 shadow-lg"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="clear-holdings-title" className="text-base font-semibold text-destructive">
              Clear all holdings
            </h2>
            <p className="mt-3 text-sm font-medium text-foreground">
              Are you absolutely sure you want to do this?
            </p>
            <p className="mt-2 text-sm text-muted-foreground">
              This removes every open position, all trade history, portfolio snapshots, and decision runs. Your
              paper account goes back to{" "}
              <strong className="text-foreground">${RESET_STARTING_CASH.toLocaleString()}</strong> cash with nothing
              invested. Other settings (thresholds, limits) are unchanged.
            </p>
            <label className="mt-4 flex cursor-pointer items-start gap-3 text-sm">
              <input
                type="checkbox"
                className="mt-1"
                checked={resetSure}
                onChange={(e) => setResetSure(e.target.checked)}
              />
              <span>
                I understand this cannot be undone and I want to wipe my paper portfolio and history.
              </span>
            </label>
            {resetMsg ? (
              <p className="mt-3 text-sm text-destructive" role="alert">
                {resetMsg}
              </p>
            ) : null}
            <div className="mt-6 flex flex-wrap items-center justify-end gap-2">
              <Button type="button" variant="outline" onClick={closeClearModal} disabled={resetLoading}>
                Cancel
              </Button>
              <Button
                type="button"
                variant="destructive"
                disabled={!resetSure || resetLoading}
                onClick={() => void clearHoldings()}
              >
                {resetLoading ? "Resetting…" : "Clear all holdings"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
