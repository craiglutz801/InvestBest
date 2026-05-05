import type { DiagnosticWarning } from "./types";

function pct(x: number): string {
  return `${x.toFixed(1)}%`;
}

export function buildDiagnosticsWarnings(input: {
  closedTradeCount: number;
  scheduleFrequencyMinutes: number | null;
  metrics: {
    totalReturnPct: number | null;
    sharpeAnnualized: number | null;
    winRatePct: number | null;
  };
  segmentRows: { key: string; label: string; realizedPnl: number; trades: number }[];
  exitReasonRows: { key: string; label: string; realizedPnl: number; trades: number }[];
  manualVsScheduled: { manualWinRate: number | null; scheduledWinRate: number | null; manualN: number; scheduledN: number };
}): DiagnosticWarning[] {
  const out: DiagnosticWarning[] = [];

  if (input.closedTradeCount < 5) {
    out.push({
      severity: "info",
      code: "LOW_SAMPLE",
      title: "Few closed round-trips yet",
      detail:
        "Diagnostics need closed BUY→SELL cycles (FIFO). With fewer than five completed trades, attribution and risk ratios are indicative only.",
    });
  }

  if (input.scheduleFrequencyMinutes != null && input.scheduleFrequencyMinutes > 0 && input.scheduleFrequencyMinutes < 120) {
    out.push({
      severity: "warning",
      code: "HOURLY_STALE_DAILY",
      title: "Scheduler runs more often than daily",
      detail:
        "This strategy uses mostly daily OHLCV features. Hourly (or sub-hourly) scheduled runs may repeat decisions from stale daily signals unless intraday data is enabled. Consider “daily after close” in Agent Automation for tighter alignment with the signal cadence.",
    });
  }

  const negSeg = [...input.segmentRows].filter((r) => r.realizedPnl < 0).sort((a, b) => a.realizedPnl - b.realizedPnl)[0];
  const totalLoss = input.segmentRows.filter((r) => r.realizedPnl < 0).reduce((s, r) => s + r.realizedPnl, 0);
  if (negSeg && totalLoss < 0 && negSeg.realizedPnl / totalLoss >= 0.4 && negSeg.trades >= 2) {
    out.push({
      severity: "warning",
      code: "SEGMENT_DRAG",
      title: `${negSeg.label} drove a large share of realized losses`,
      detail: `Roughly ${pct((negSeg.realizedPnl / totalLoss) * 100)} of realized losses in this window came from segment “${negSeg.label}”. Consider tightening exposure or reviewing entries in that bucket.`,
    });
  }

  const tp = input.exitReasonRows.find((r) => r.key === "take_profit");
  const sl = input.exitReasonRows.find((r) => r.key === "stop_loss");
  if (tp && sl && tp.trades + sl.trades >= 6 && sl.realizedPnl < tp.realizedPnl * -0.5 && sl.trades >= tp.trades) {
    out.push({
      severity: "warning",
      code: "STOP_VS_TARGET",
      title: "Stop-loss exits may be dominating take-profits",
      detail:
        "Realized P&L from stop-loss exits is materially worse than from take-profit exits, with comparable or higher trade counts. Review sell thresholds, trailing give-back, or entry quality.",
    });
  }

  if (
    input.metrics.totalReturnPct != null &&
    input.metrics.totalReturnPct < -3 &&
    input.metrics.sharpeAnnualized != null &&
    input.metrics.sharpeAnnualized < 0
  ) {
    out.push({
      severity: "critical",
      code: "NEGATIVE_RISK_ADJ",
      title: "Negative return with weak risk-adjusted performance",
      detail:
        "Portfolio drawdown and negative Sharpe suggest the current rules may be paying for volatility without compensation. Use attribution tables below before changing thresholds — Sprint 3 backtests will quantify scenarios.",
    });
  }

  const { manualWinRate, scheduledWinRate, manualN, scheduledN } = input.manualVsScheduled;
  if (
    manualWinRate != null &&
    scheduledWinRate != null &&
    manualN >= 4 &&
    scheduledN >= 4 &&
    Math.abs(manualWinRate - scheduledWinRate) >= 25
  ) {
    out.push({
      severity: "info",
      code: "TRIGGER_DELTA",
      title: "Manual vs scheduled win rates diverge",
      detail: `Manual triggers won ~${pct(manualWinRate)} of closed trades vs ~${pct(scheduledWinRate)} for scheduled runs (same window). Sample sizes manual=${manualN}, scheduled=${scheduledN}. Could be timing luck — track over more trades.`,
    });
  }

  return out;
}
