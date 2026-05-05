"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Dashboard card for "agent automation health" — Strategy Upgrade §11 / §40.
 *
 * Polls `/api/runs/latest` and `/api/settings/agent-schedule/next-run` every 30s
 * so the user can see, at a glance:
 *   - last agent run + status + trigger source
 *   - next scheduled run + cadence description
 *   - whether scheduled runs are enabled
 *   - any recent error
 */

type Latest = {
  id: string;
  startedAt: string;
  finishedAt: string | null;
  status: string;
  triggerSource: string | null;
  runMode: string | null;
  buysCount: number;
  sellsCount: number;
};

type NextRun = {
  enabled: boolean;
  nextRunAt: string | null;
  lastRunStatus: string | null;
  lastRunError: string | null;
  description: string;
  marketWindowNow: string;
  warnings: string[];
};

function fmt(s: string | null | undefined): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
}

function statusTone(status: string | null | undefined): string {
  if (!status) return "text-muted-foreground";
  if (status === "completed" || status === "success") return "text-success";
  if (status === "failed" || status === "timeout") return "text-danger";
  if (status === "running") return "text-amber-600 dark:text-amber-400";
  return "text-muted-foreground";
}

export function AgentRunStatusCard() {
  const [latest, setLatest] = useState<Latest | null>(null);
  const [nextRun, setNextRun] = useState<NextRun | null>(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const [a, b] = await Promise.all([
          fetch("/api/runs/latest", { cache: "no-store" }).then((r) => r.json()),
          fetch("/api/settings/agent-schedule/next-run", { cache: "no-store" }).then((r) => r.json()),
        ]);
        if (!alive) return;
        setLatest((a?.run as Latest | null) ?? null);
        setNextRun((b as NextRun) ?? null);
      } catch {
        /* leave previous values */
      }
    };
    void load();
    const t = setInterval(load, 30_000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">Agent automation</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Status</p>
            <p className={`text-sm font-medium ${statusTone(latest?.status)}`}>
              {latest?.status ?? "—"}
              {latest?.triggerSource ? (
                <span className="ml-1 text-xs text-muted-foreground">({latest.triggerSource})</span>
              ) : null}
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Last run</p>
            <p className="text-sm font-medium">{fmt(latest?.startedAt)}</p>
            {latest ? (
              <p className="text-xs text-muted-foreground">
                {latest.buysCount} buys · {latest.sellsCount} sells
              </p>
            ) : null}
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Next scheduled</p>
            <p className="text-sm font-medium">
              {nextRun?.enabled === false ? "Disabled" : fmt(nextRun?.nextRunAt ?? null)}
            </p>
            {nextRun?.description ? (
              <p className="text-xs text-muted-foreground">{nextRun.description}</p>
            ) : null}
          </div>
        </div>

        {nextRun?.lastRunError ? (
          <p className="mt-3 rounded border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
            Last error: {nextRun.lastRunError}
          </p>
        ) : null}
        {nextRun?.warnings && nextRun.warnings.length > 0 ? (
          <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
            {nextRun.warnings.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}
