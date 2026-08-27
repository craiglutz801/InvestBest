import { SettingsForm } from "@/components/SettingsForm";
import { AgentAutomationForm } from "@/components/settings/AgentAutomationForm";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { loadOrInitScheduleSettings } from "@/lib/scheduler/scheduleSettings";
import { requireDefaultUser } from "@/lib/server/defaultUser";

function toLocalInput(d: Date | null | undefined): string {
  if (!d) return "";
  const x = new Date(d);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}T${pad(x.getHours())}:${pad(x.getMinutes())}`;
}

export default async function SettingsPage() {
  const user = await requireDefaultUser();
  const s = await prisma.appSettings.findUnique({ where: { userId: user.id } });
  if (!s) throw new Error("Settings missing");

  const initial = {
    startingCash: toNum(s.startingCash),
    maxPositionPct: toNum(s.maxPositionPct),
    maxNewPositionsPerRun: s.maxNewPositionsPerRun,
    targetHoldings: s.targetHoldings,
    stopLossPct: toNum(s.stopLossPct),
    takeProfitPct: toNum(s.takeProfitPct),
    minConfidence: toNum(s.minConfidence),
    cashReservePct: toNum(s.cashReservePct),
    runFrequencyMinutes: s.runFrequencyMinutes,
    newsEnabled: s.newsEnabled,
    shortingEnabled: s.shortingEnabled,
    defaultSlippagePct: toNum(s.defaultSlippagePct),
    strategyMode: (s.strategyMode as "rules_v1" | "alpha_v1" | "regression_v1") ?? "rules_v1",
    buyScoreThreshold: toNum(s.buyScoreThreshold),
    sellRiskThreshold: toNum(s.sellRiskThreshold),
    cooldownHours: s.cooldownHours,
    staleQuoteAllowSells: s.staleQuoteAllowSells ?? false,
    paperStartDate: toLocalInput(s.paperStartDate),
    paperEndDate: toLocalInput(s.paperEndDate),
    agentPaused: Boolean((s as { agentPaused?: boolean }).agentPaused),
    buyScoreMargin: toNum(s.buyScoreMargin),
    confidenceMarginForBuy: toNum(s.confidenceMarginForBuy),
    requireMomentumForBuy: s.requireMomentumForBuy,
    maxBuyAnnualVol: toNum(s.maxBuyAnnualVol),
    bearScoreThreshold: toNum(s.bearScoreThreshold),
    confidenceMarginForShort: toNum(s.confidenceMarginForShort),
    shortOnlyInBearRegime: s.shortOnlyInBearRegime,
    maxShortPositionsPerRun: s.maxShortPositionsPerRun,
    buyScoreCoverShortThreshold: toNum(s.buyScoreCoverShortThreshold),
  };

  const schedule = await loadOrInitScheduleSettings(user.id);
  const automationInitial = {
    enabled: schedule.enabled,
    schedulePreset: schedule.schedulePreset,
    frequencyMinutes: schedule.frequencyMinutes,
    customCronExpression: schedule.customCronExpression,
    timezone: schedule.timezone,
    runOnlyDuringMarketHours: schedule.runOnlyDuringMarketHours,
    runOnMarketDaysOnly: schedule.runOnMarketDaysOnly,
    skipIfRunAlreadyActive: schedule.skipIfRunAlreadyActive,
    maxRunDurationMinutes: schedule.maxRunDurationMinutes,
    retryFailedRuns: schedule.retryFailedRuns,
    maxRetries: schedule.maxRetries,
    nextRunAt: schedule.nextRunAt?.toISOString() ?? null,
    lastRunAt: schedule.lastRunAt?.toISOString() ?? null,
    lastRunStatus: schedule.lastRunStatus,
    lastRunError: schedule.lastRunError,
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Portfolio rules for the paper engine. Every control in the form below has a short explanation under its
          label.
        </p>
      </div>
      <AgentAutomationForm initial={automationInitial} />
      <SettingsForm initial={initial} />
    </div>
  );
}
