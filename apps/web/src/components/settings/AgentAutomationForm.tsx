"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Agent Automation settings panel — Strategy Upgrade §2 / §11.
 *
 * Drives `AgentScheduleSettings`. Kept separate from the existing big SettingsForm
 * so the legacy form continues to work unchanged. All persistence goes through
 * `PUT /api/settings/agent-schedule`; the `next-run` endpoint is polled to keep
 * "Last run" / "Next run" honest while the user is on the page.
 */

type Preset =
  | "every_15_min"
  | "every_30_min"
  | "hourly"
  | "every_2h"
  | "every_4h"
  | "daily_after_close"
  | "daily_before_open"
  | "custom";

export type AgentScheduleInitial = {
  enabled: boolean;
  schedulePreset: Preset;
  frequencyMinutes: number;
  customCronExpression: string | null;
  timezone: string;
  runOnlyDuringMarketHours: boolean;
  runOnMarketDaysOnly: boolean;
  skipIfRunAlreadyActive: boolean;
  maxRunDurationMinutes: number;
  retryFailedRuns: boolean;
  maxRetries: number;
  nextRunAt: string | null;
  lastRunAt: string | null;
  lastRunStatus: string | null;
  lastRunError: string | null;
};

type NextRunResp = {
  enabled: boolean;
  nextRunAt: string | null;
  lastRunAt: string | null;
  lastRunStatus: string | null;
  lastRunError: string | null;
  description: string;
  marketWindowNow: string;
  warnings: string[];
};

const PRESET_LABELS: Record<Preset, string> = {
  every_15_min: "Every 15 minutes",
  every_30_min: "Every 30 minutes",
  hourly: "Every hour (default)",
  every_2h: "Every 2 hours",
  every_4h: "Every 4 hours",
  daily_after_close: "Daily after market close (16:15 ET)",
  daily_before_open: "Daily before market open (09:00 ET)",
  custom: "Custom (frequency in minutes)",
};

function fmtIso(s: string | null): string {
  if (!s) return "—";
  try {
    return new Date(s).toLocaleString();
  } catch {
    return s;
  }
}

export function AgentAutomationForm({ initial }: { initial: AgentScheduleInitial }) {
  const router = useRouter();
  const [v, setV] = useState(initial);
  const [meta, setMeta] = useState<NextRunResp | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);

  const showSubHourlyWarning = useMemo(
    () => v.schedulePreset === "every_15_min" || v.schedulePreset === "every_30_min",
    [v.schedulePreset],
  );

  async function refreshNextRun() {
    try {
      const res = await fetch("/api/settings/agent-schedule/next-run", { cache: "no-store" });
      if (res.ok) setMeta((await res.json()) as NextRunResp);
    } catch {
      /* silent — meta is purely informational */
    }
  }

  useEffect(() => {
    void refreshNextRun();
    const t = setInterval(refreshNextRun, 30_000);
    return () => clearInterval(t);
  }, []);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = { ...v };
      delete body.nextRunAt;
      delete body.lastRunAt;
      delete body.lastRunStatus;
      delete body.lastRunError;
      const res = await fetch("/api/settings/agent-schedule", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg("Saved.");
      void refreshNextRun();
      router.refresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setLoading(false);
    }
  }

  async function runNow(opts?: { dryRun?: boolean; force?: boolean }) {
    setRunning(true);
    setMsg(null);
    try {
      const res = await fetch("/api/runs/trigger", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(opts ?? {}),
      });
      const data = (await res.json().catch(() => ({}))) as {
        status?: string;
        error?: string;
        runId?: string | null;
      };
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg(
        data.status === "skipped_in_progress"
          ? "Skipped: an agent run is already active. Use Force to override."
          : `Triggered (${data.status ?? "started"}).`,
      );
      void refreshNextRun();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Run failed");
    } finally {
      setRunning(false);
    }
  }

  const inp =
    "w-full rounded-md border border-border bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Agent Automation</CardTitle>
        <p className="text-sm leading-relaxed text-muted-foreground">
          Schedule when InvestBest&apos;s paper-trading agent runs automatically. Defaults to every hour. Manual{" "}
          <strong>Run agent now</strong> and the scheduled job share the same orchestrator and the same per-user
          run lock, so triggers cannot overlap.
        </p>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="grid gap-3 rounded-md border border-border bg-muted/20 p-3 sm:grid-cols-3">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Enabled</p>
            <p className="text-sm font-medium">{meta?.enabled ?? v.enabled ? "Yes" : "No"}</p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Last run</p>
            <p className="text-sm font-medium">
              {fmtIso(meta?.lastRunAt ?? v.lastRunAt)}{" "}
              <span className="text-xs text-muted-foreground">
                {(meta?.lastRunStatus ?? v.lastRunStatus) ? `(${meta?.lastRunStatus ?? v.lastRunStatus})` : ""}
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Next run</p>
            <p className="text-sm font-medium">{fmtIso(meta?.nextRunAt ?? v.nextRunAt)}</p>
          </div>
          <div className="sm:col-span-3">
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Schedule</p>
            <p className="text-sm">{meta?.description ?? PRESET_LABELS[v.schedulePreset]}</p>
            {meta?.marketWindowNow ? (
              <p className="mt-1 text-xs text-muted-foreground">{meta.marketWindowNow}</p>
            ) : null}
          </div>
          {meta?.lastRunError ? (
            <div className="sm:col-span-3 rounded border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
              Last error: {meta.lastRunError}
            </div>
          ) : null}
          {(meta?.warnings ?? []).length > 0 ? (
            <ul className="sm:col-span-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
              {meta!.warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" disabled={running} onClick={() => void runNow()}>
            {running ? "Working…" : "Run agent now"}
          </Button>
          <Button type="button" variant="outline" disabled={running} onClick={() => void runNow({ dryRun: true })}>
            Dry run
          </Button>
          <Button type="button" variant="outline" disabled={running} onClick={() => void runNow({ force: true })}>
            Force run (ignore lock)
          </Button>
        </div>

        <form onSubmit={save} className="grid gap-6 sm:grid-cols-2">
          <label className="grid gap-1.5 text-sm sm:col-span-2">
            <span className="font-medium text-foreground">Scheduled runs</span>
            <span className="text-xs text-muted-foreground">
              Master switch. When off, the scheduler tick records &quot;skipped (disabled)&quot; without invoking the agent.
            </span>
            <label className="flex cursor-pointer items-center gap-2 pt-1">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={v.enabled}
                onChange={(e) => setV({ ...v, enabled: e.target.checked })}
              />
              <span>Enable scheduled runs</span>
            </label>
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Preset</span>
            <span className="text-xs text-muted-foreground">
              Picks the cadence the scheduler tick uses. <em>Hourly</em> matches the spec default.
            </span>
            <select
              className={inp}
              value={v.schedulePreset}
              onChange={(e) => setV({ ...v, schedulePreset: e.target.value as Preset })}
            >
              {(Object.keys(PRESET_LABELS) as Preset[]).map((k) => (
                <option key={k} value={k}>
                  {PRESET_LABELS[k]}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Frequency (minutes)</span>
            <span className="text-xs text-muted-foreground">
              Used directly when preset is <em>custom</em>; otherwise the preset overrides this on save.
            </span>
            <input
              type="number"
              min={1}
              className={inp}
              value={v.frequencyMinutes}
              onChange={(e) => setV({ ...v, frequencyMinutes: Number(e.target.value) })}
            />
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Custom cron expression</span>
            <span className="text-xs text-muted-foreground">
              Stored for documentation today. The Sprint 1 scheduler treats <em>custom</em> as a flat
              <code className="mx-1 rounded bg-muted px-1 py-0.5 text-xs">frequencyMinutes</code> cadence; a real cron
              parser ships in a later sprint.
            </span>
            <input
              type="text"
              className={inp}
              placeholder="e.g. 0 */2 * * *"
              value={v.customCronExpression ?? ""}
              onChange={(e) => setV({ ...v, customCronExpression: e.target.value || null })}
            />
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Timezone</span>
            <span className="text-xs text-muted-foreground">
              Display only for now (next-run math uses ET for market windows). Defaults to{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">America/Denver</code>.
            </span>
            <input
              type="text"
              className={inp}
              value={v.timezone}
              onChange={(e) => setV({ ...v, timezone: e.target.value })}
            />
          </label>

          <label className="grid gap-1.5 text-sm sm:col-span-2">
            <span className="font-medium text-foreground">Market-hours filters</span>
            <span className="text-xs text-muted-foreground">
              The current strategy uses daily indicators — running outside market hours mostly re-marks the same
              decisions. Toggle <em>only during market hours</em> if you want to suppress those repeats.
            </span>
            <div className="flex flex-col gap-2 pt-1 sm:flex-row sm:gap-6">
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={v.runOnlyDuringMarketHours}
                  onChange={(e) => setV({ ...v, runOnlyDuringMarketHours: e.target.checked })}
                />
                <span>Run only during market hours (ET 09:30–16:00)</span>
              </label>
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={v.runOnMarketDaysOnly}
                  onChange={(e) => setV({ ...v, runOnMarketDaysOnly: e.target.checked })}
                />
                <span>Run on market days only (Mon–Fri)</span>
              </label>
            </div>
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Skip if a run is already active</span>
            <span className="text-xs text-muted-foreground">
              The per-user run lock always prevents overlap. This setting controls whether the scheduler tick records
              the skip explicitly (recommended).
            </span>
            <label className="flex cursor-pointer items-center gap-2 pt-1">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={v.skipIfRunAlreadyActive}
                onChange={(e) => setV({ ...v, skipIfRunAlreadyActive: e.target.checked })}
              />
              <span>Skip overlapping runs</span>
            </label>
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Lock timeout (minutes)</span>
            <span className="text-xs text-muted-foreground">
              How long the run lock is held before it auto-expires. Pick higher than your slowest expected run.
            </span>
            <input
              type="number"
              min={1}
              max={180}
              className={inp}
              value={v.maxRunDurationMinutes}
              onChange={(e) => setV({ ...v, maxRunDurationMinutes: Number(e.target.value) })}
            />
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Retry failed runs</span>
            <span className="text-xs text-muted-foreground">
              Sprint 1 stores the preference but the actual retry loop ships in a later sprint (along with retry
              attribution).
            </span>
            <label className="flex cursor-pointer items-center gap-2 pt-1">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-border"
                checked={v.retryFailedRuns}
                onChange={(e) => setV({ ...v, retryFailedRuns: e.target.checked })}
              />
              <span>Auto-retry on failure</span>
            </label>
          </label>

          <label className="grid gap-1.5 text-sm">
            <span className="font-medium text-foreground">Max retries</span>
            <span className="text-xs text-muted-foreground">
              Cap on automatic retry attempts (only used once retry logic ships).
            </span>
            <input
              type="number"
              min={0}
              max={10}
              className={inp}
              value={v.maxRetries}
              onChange={(e) => setV({ ...v, maxRetries: Number(e.target.value) })}
            />
          </label>

          {showSubHourlyWarning ? (
            <p className="sm:col-span-2 rounded border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-950 dark:text-amber-100">
              <strong>Heads up.</strong> Sub-hourly cadences require an external cron that ticks at least that often.
              Vercel Cron on Hobby is once-per-hour. For 15/30 minute runs, switch{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">SCHEDULER_PROVIDER=triggerdev</code> and configure
              a Trigger.dev scheduled task to POST <code className="rounded bg-muted px-1 py-0.5 text-xs">/api/internal/scheduler-tick</code>.
            </p>
          ) : null}

          <p className="sm:col-span-2 rounded border border-border bg-muted/20 p-3 text-xs text-muted-foreground">
            <strong>Daily-strategy reminder.</strong> The current paper engine uses mostly daily OHLCV indicators.
            Hourly runs may repeat decisions from stale daily signals. <em>Daily after market close</em> is the most
            faithful cadence for the current strategy until intraday features ship.
          </p>

          <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
            <Button type="submit" disabled={loading}>
              {loading ? "Saving…" : "Save automation settings"}
            </Button>
            {msg ? <span className="text-sm text-muted-foreground">{msg}</span> : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
