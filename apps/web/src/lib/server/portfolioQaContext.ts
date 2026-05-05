import type { buildDashboardPayload } from "@/lib/server/dashboardPayload";

export type DashboardPayload = Awaited<ReturnType<typeof buildDashboardPayload>>;

const MAX_CONTEXT_CHARS = 14_000;

function round(n: number, d = 2) {
  const p = 10 ** d;
  return Math.round(n * p) / p;
}

/**
 * Plain facts about the user's current strategy — the knobs from AppSettings
 * that actually drive buy/sell decisions. Shaped for LLM consumption, not DB.
 */
export type StrategySnapshot = {
  buyScoreThreshold: number;
  sellRiskThreshold: number;
  minConfidence: number;
  stopLossPct: number;
  takeProfitPct: number;
  cashReservePct: number;
  maxPositionPct: number;
  maxNewPositionsPerRun: number;
  cooldownHours: number;
  shortingEnabled: boolean;
};

/**
 * Build a plain-English strategy block for the Q&A context.
 *
 * NOTE: The rule descriptions below are a hand-written mirror of the logic in
 * `@/lib/rules/buyRules.ts` and `@/lib/rules/sellRules.ts`. If those rule sets
 * change meaningfully (new block reasons, different trailing-stop math, etc.)
 * update this copy too, otherwise the Q&A model will answer strategy questions
 * using stale descriptions. The numeric thresholds come from live settings and
 * stay accurate automatically.
 */
export function strategySnapshotToContext(s: StrategySnapshot): string {
  const lines: string[] = [];
  lines.push("### Strategy (current rules)");
  lines.push("");
  lines.push("Thresholds (from user settings):");
  lines.push(`- Buy score threshold: ${round(s.buyScoreThreshold)} (a candidate must score at least this to buy)`);
  lines.push(`- Sell-risk threshold: ${round(s.sellRiskThreshold)} (position sold if sell-risk score meets/exceeds this)`);
  lines.push(`- Min confidence: ${round(s.minConfidence)} (buys blocked below this model confidence)`);
  lines.push(`- Stop-loss: ${round(s.stopLossPct)}% below average cost`);
  lines.push(`- Take-profit: ${round(s.takeProfitPct)}% above average cost`);
  lines.push(`- Cash reserve: ${round(s.cashReservePct)}% of portfolio kept in cash`);
  lines.push(`- Max position size: ${round(s.maxPositionPct)}% of portfolio per symbol`);
  lines.push(`- Max new positions per run: ${s.maxNewPositionsPerRun}`);
  lines.push(`- Cooldown after sell: ${s.cooldownHours}h before the same symbol can be bought again`);
  lines.push(`- Shorting: ${s.shortingEnabled ? "enabled" : "disabled (long-only)"}`);
  lines.push("");
  lines.push("Buy is BLOCKED when any of these fire:");
  lines.push("- cash_reserve: buying would break the cash-reserve floor");
  lines.push("- confidence: model confidence is below min confidence");
  lines.push("- buy_score: candidate's buy score is below the buy threshold");
  lines.push("- already_held: pyramiding is disabled — one entry per symbol");
  lines.push("- volatility: 20-day realised vol is above the allowed ceiling");
  lines.push("- extended_from_mean: price is too far above its 20-day mean (chasing)");
  lines.push("- cooldown: symbol was sold recently and is still in post-sell cooldown");
  lines.push("- liquidity: average dollar volume is below the liquidity floor");
  lines.push("");
  lines.push("Sell is TRIGGERED by the first of these that fires:");
  lines.push("- stop_loss: price is down at least the stop-loss % from average cost");
  lines.push("- take_profit: price is up at least the take-profit % from average cost");
  lines.push(
    "- trailing_stop: once the position peaked at least halfway to take-profit, a ~4% give-back from that recent high locks in gains",
  );
  lines.push("- sell_risk: computed sell-risk score meets or exceeds the sell-risk threshold");
  lines.push("- momentum_break: 5-day return < -4% AND RSI < 45 (trend rolling over)");
  return lines.join("\n");
}

/**
 * Compact, LLM-friendly snapshot of the dashboard payload (truncated for token limits).
 */
export function dashboardPayloadToQaContext(d: DashboardPayload): string {
  const s = d.summary;
  const lines: string[] = [];

  lines.push("## InvestBest paper portfolio (facts only — user question follows separately)");
  lines.push("");
  lines.push("### Summary");
  lines.push(
    `- Starting cash: $${round(s.startingCash)} → Total value: $${round(s.totalValue)} (${round(s.totalReturnPct)}% return)`,
  );
  lines.push(`- Cash: $${round(s.cash)} · Invested: $${round(s.invested)}`);
  lines.push(`- Unrealized P&L: $${round(s.unrealizedPnl)} · Realized P&L: $${round(s.realizedPnl)}`);
  if (s.benchmarkReturnPct != null) {
    lines.push(`- SPY benchmark (same-period notion): ${round(s.benchmarkReturnPct)}%`);
  }
  lines.push(`- Open positions: ${s.openPositions} · Max drawdown (from snapshots): ${round(s.maxDrawdownPct)}%`);
  if (s.firstSnapshotAt) lines.push(`- First snapshot: ${s.firstSnapshotAt}`);

  const curve = d.equityCurve;
  if (curve.length > 0) {
    const tail = curve.slice(-24);
    lines.push("");
    lines.push("### Recent equity curve (total portfolio value, last points)");
    for (const p of tail) {
      lines.push(`- ${p.t}: $${round(p.value)}${p.benchmark != null ? ` (bench $${round(p.benchmark)})` : ""}`);
    }
  }

  lines.push("");
  lines.push("### Allocation (open positions by market value)");
  if (d.allocation.length === 0) {
    lines.push("- None (all cash)");
  } else {
    for (const a of d.allocation) {
      lines.push(`- ${a.name}: $${round(a.value)}`);
    }
  }

  lines.push("");
  lines.push("### Top winners / losers (unrealized % on open lots)");
  for (const w of d.topWinners) {
    lines.push(`- Winner ${w.symbol}: ${round(w.unrealizedPct)}% (≈$${round(w.unrealizedPnl)} P&L, MV $${round(w.marketValue)})`);
  }
  for (const l of d.topLosers) {
    lines.push(`- Loser ${l.symbol}: ${round(l.unrealizedPct)}% (≈$${round(l.unrealizedPnl)} P&L, MV $${round(l.marketValue)})`);
  }

  lines.push("");
  lines.push("### Holdings (per-symbol, truncated history)");
  for (const h of d.holdingsPerformance) {
    const tail = h.valueHistory.slice(-4);
    lines.push(
      `- ${h.ticker}: MV $${round(h.marketValue)}, unrealized ${round(h.unrealizedPct)}%, DoD ${h.dayOverDayPct != null ? round(h.dayOverDayPct) + "%" : "n/a"}, vs bar ${h.vsLastSnapshotPct != null ? round(h.vsLastSnapshotPct) + "%" : "n/a"}`,
    );
    if (tail.length) {
      lines.push(`  recent marks: ${tail.map((pt) => `${pt.t}:$${round(pt.value)}`).join(" → ")}`);
    }
  }

  lines.push("");
  lines.push("### Latest buys (paper)");
  for (const t of d.latestBuys) {
    lines.push(`- ${t.ticker} ${t.qty} @ $${round(t.price)} · ${t.at}${t.confidence != null ? ` · conf ${round(t.confidence)}` : ""}`);
  }
  lines.push("");
  lines.push("### Latest sells (paper)");
  for (const t of d.latestSells) {
    const r = t.reason ? String(t.reason).slice(0, 200) : "";
    lines.push(`- ${t.ticker} ${t.qty} @ $${round(t.price)} · ${t.at}${r ? ` · ${r}` : ""}`);
  }

  lines.push("");
  lines.push("### Latest agent decision items (most recent run)");
  for (const it of d.latestDecisionItems.slice(0, 25)) {
    lines.push(
      `- ${it.ticker}: ${it.blocked ? `blocked (${it.blockedReason ?? ""})` : it.action} · buy ${it.buyScore ?? "—"} · sellRisk ${it.sellRisk ?? "—"} · conf ${it.confidence ?? "—"}`,
    );
    if (it.note) lines.push(`  note: ${String(it.note).slice(0, 280)}`);
  }

  if (d.lastRun) {
    lines.push("");
    lines.push("### Last decision run");
    lines.push(`- Status: ${d.lastRun.status} · Started: ${d.lastRun.startedAt}`);
    lines.push(`- Buys: ${d.lastRun.buysCount} · Sells: ${d.lastRun.sellsCount}`);
    if (d.lastRun.llmSummary) {
      lines.push(`- Agent summary: ${String(d.lastRun.llmSummary).slice(0, 1200)}`);
    }
  }

  if (d.discoverySummary) {
    lines.push("");
    lines.push("### Discovery (last completed run)");
    lines.push(`- Profile: ${d.discoverySummary.profileName ?? "—"}`);
    lines.push(`- Stats (JSON): ${JSON.stringify(d.discoverySummary.stats).slice(0, 1500)}`);
  }

  let text = lines.join("\n");
  if (text.length > MAX_CONTEXT_CHARS) {
    text = text.slice(0, MAX_CONTEXT_CHARS) + "\n\n[Context truncated for length.]";
  }
  return text;
}
