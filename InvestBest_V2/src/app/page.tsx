import { AppShell } from "@/components/AppShell";
import { MetricCard } from "@/components/MetricCard";
import { RunControls } from "@/components/RunControls";
import { SectionCard } from "@/components/SectionCard";
import { getDashboardSnapshot } from "@/lib/dashboard";
import { alerts, strategyModels } from "@/lib/mockData";
import type { SummaryMetric } from "@/lib/types";

export const dynamic = "force-dynamic";

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number): string {
  return `${value >= 0 ? "+" : ""}${(value * 100).toFixed(2)}%`;
}

function formatTimestamp(value: string | null): string {
  if (!value) {
    return "not yet";
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "short",
    timeStyle: "medium",
    timeZone: "America/Los_Angeles",
  }).format(new Date(value));
}

export default async function HomePage() {
  const snapshot = await getDashboardSnapshot();
  const { portfolio } = snapshot;
  const latestRun = portfolio.runHistory[0] ?? null;

  const summaryMetrics: SummaryMetric[] = [
    { label: "Mode", value: "Paper only", tone: "neutral" },
    { label: "Cash", value: formatCurrency(portfolio.cash), tone: "neutral" },
    {
      label: "Portfolio equity",
      value: formatCurrency(portfolio.equity),
      change: formatPercent(snapshot.totalReturnPct),
      tone: snapshot.totalReturnPct >= 0 ? "positive" : "negative",
    },
    {
      label: "Active model",
      value: snapshot.activeModel,
      change: `${portfolio.lastRegime} regime`,
      tone: "neutral",
    },
    {
      label: "Automation",
      value: portfolio.automation.enabled ? "Armed" : "Off",
      change: portfolio.automation.nextPlannedRunAt
        ? `next ${new Date(portfolio.automation.nextPlannedRunAt).toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit",
            timeZone: "America/Los_Angeles",
          })}`
        : "no next run",
      tone: portfolio.automation.enabled ? "positive" : "negative",
    },
  ];

  return (
    <AppShell
      title="A research-first simulator that actually runs"
      subtitle="V2 now has a live manual paper-simulation loop: fetch real market data, score a curated universe, rebalance a $100,000 paper book, and log every run before we automate anything."
    >
      <div className="grid metrics">
        {summaryMetrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </div>

      <div className="hero" style={{ marginTop: "1rem" }}>
        <div className="card hero-panel">
          <p className="eyebrow">How it runs</p>
          <h2>Manual execution first, then automation</h2>
          <p>
            Each run pulls fresh daily market data, classifies the market regime, scores the universe with the current
            regression-style ranker, and rebalances an equal-weight paper book with a 10% cash reserve. We are doing
            this manually first so we can trust the mechanics before adding schedules.
          </p>
        </div>
        <div className="card hero-panel">
          <p className="eyebrow">Try it now</p>
          <h2>Start with $100k of fake money</h2>
          <RunControls />
        </div>
      </div>

      <div className="grid two" style={{ marginTop: "1rem" }}>
        <SectionCard
          title="Automation status"
          description="V2 scheduled runs can come from a hosted cron trigger and write into the same shared paper portfolio."
        >
          <div className="grid two">
            <div className="note">
              <strong className="strong">Schedule</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                Weekdays at 6:35 AM through 12:35 PM Pacific, once per hour during the trading day.
              </p>
            </div>
            <div className="note">
              <strong className="strong">Shared state</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                Manual and scheduled runs write to the same persisted paper portfolio state and run history.
              </p>
            </div>
            <div className="note">
              <strong className="strong">Last scheduled attempt</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                {formatTimestamp(portfolio.automation.lastAttemptAt)}
              </p>
            </div>
            <div className="note">
              <strong className="strong">Next planned run</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                {formatTimestamp(portfolio.automation.nextPlannedRunAt)}
              </p>
            </div>
          </div>
        </SectionCard>

        <SectionCard
          title="Recent execution mix"
          description="Manual runs are still useful for testing, but scheduled runs should take over during the day."
        >
          <div className="stack">
            <div className="note">
              <strong className="strong">Last scheduled completion</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                {formatTimestamp(portfolio.automation.lastCompletedAt)}
              </p>
            </div>
            <div className="note">
              <strong className="strong">Latest run source</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                {latestRun ? latestRun.source : "no runs yet"}
              </p>
            </div>
            <div className="note">
              <strong className="strong">What automation does</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                It re-scores the universe, rebalances the portfolio, and persists trades, run history, equity, and
                ranked candidates without needing the browser open.
              </p>
            </div>
          </div>
        </SectionCard>
      </div>

      <div className="grid two" style={{ marginTop: "1rem" }}>
        <SectionCard
          title="Current holdings"
          description="The live paper portfolio after the most recent completed run."
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Segment</th>
                  <th>Shares</th>
                  <th>Last</th>
                  <th>Value</th>
                  <th>Unrealized</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.holdings.length === 0 ? (
                  <tr>
                    <td colSpan={6}>No positions yet. Run the $100k simulation to create the first paper portfolio.</td>
                  </tr>
                ) : (
                  portfolio.holdings.map((position) => (
                    <tr key={position.symbol}>
                      <td><strong className="strong">{position.symbol}</strong></td>
                      <td>{position.segment}</td>
                      <td>{position.shares.toFixed(3)}</td>
                      <td>{formatCurrency(position.lastPrice)}</td>
                      <td>{formatCurrency(position.marketValue)}</td>
                      <td className={position.unrealizedPnl >= 0 ? "positive-text" : "negative-text"}>
                        {formatCurrency(position.unrealizedPnl)} · {formatPercent(position.unrealizedPnlPct)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <SectionCard
          title="Latest ranked candidates"
          description="What the current model wanted most recently, even if the portfolio was already aligned."
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Segment</th>
                  <th>Score</th>
                  <th>5d</th>
                  <th>20d</th>
                  <th>Trend</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.latestCandidates.length === 0 ? (
                  <tr>
                    <td colSpan={6}>No candidate ranking yet. The first run will populate this panel.</td>
                  </tr>
                ) : (
                  portfolio.latestCandidates.map((candidate) => (
                    <tr key={candidate.symbol}>
                      <td><strong className="strong">{candidate.symbol}</strong></td>
                      <td>{candidate.segment}</td>
                      <td>{candidate.score.toFixed(3)}</td>
                      <td className={candidate.return5d >= 0 ? "positive-text" : "negative-text"}>{formatPercent(candidate.return5d)}</td>
                      <td className={candidate.return20d >= 0 ? "positive-text" : "negative-text"}>{formatPercent(candidate.return20d)}</td>
                      <td className={candidate.trend50d >= 0 ? "positive-text" : "negative-text"}>{formatPercent(candidate.trend50d)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </SectionCard>
      </div>

      <div className="grid two" style={{ marginTop: "1rem" }}>
        <SectionCard
          title="Run history"
          description="Every manual run is persisted so we can inspect if the system is improving or just churning."
        >
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>When</th>
                  <th>Status</th>
                  <th>Regime</th>
                  <th>Buys</th>
                  <th>Sells</th>
                  <th>Change</th>
                </tr>
              </thead>
              <tbody>
                {portfolio.runHistory.length === 0 ? (
                  <tr>
                    <td colSpan={6}>No runs yet. Use the control panel above to execute the first simulation.</td>
                  </tr>
                ) : (
                  portfolio.runHistory.slice(0, 12).map((run) => (
                    <tr key={run.id}>
                      <td>
                        <strong className="strong">{formatTimestamp(run.executedAt)}</strong>
                        <div className="card-label">{run.note}</div>
                      </td>
                      <td><span className={`badge ${run.status}`}>{run.status}</span></td>
                      <td>{run.regime}</td>
                      <td>{run.buys}</td>
                      <td>{run.sells}</td>
                      <td className={run.portfolioChange >= 0 ? "positive-text" : "negative-text"}>
                        {formatCurrency(run.portfolioChange)}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </SectionCard>

        <SectionCard
          title="Execution posture"
          description="The system still distrusts itself by default. The simulator is real; the promotion logic remains skeptical."
        >
          <div className="stack">
            <div className="note">
              <strong className="strong">What it does today</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                Pulls real Yahoo Finance daily bars, ranks a curated universe, and rebalances a paper-only portfolio.
              </p>
            </div>
            <div className="note">
              <strong className="strong">What it does not do yet</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                No automation, no walk-forward training loop, and no live capital. Those come after we trust the
                current mechanics.
              </p>
            </div>
            {latestRun ? (
              <div className="note">
                <strong className="strong">Latest run summary</strong>
                <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                  {latestRun.model} ran in a {latestRun.regime} tape across {latestRun.universeSize} names with{" "}
                  {latestRun.buys} buys and {latestRun.sells} sells.
                </p>
              </div>
            ) : null}
          </div>
        </SectionCard>
      </div>

      <SectionCard
        title="Research posture"
        description="The manual simulator is only the first consumer. The real V2 edge still depends on better validation and model governance."
      >
        <div className="grid two">
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Stage</th>
                  <th>OOS Sharpe</th>
                  <th>Mean IC</th>
                </tr>
              </thead>
              <tbody>
                {strategyModels.map((model) => (
                  <tr key={model.id}>
                    <td>
                      <strong className="strong">{model.name}</strong>
                      <div className="card-label">{model.notes}</div>
                    </td>
                    <td><span className={`badge ${model.stage}`}>{model.stage}</span></td>
                    <td>{model.oosSharpe.toFixed(2)}</td>
                    <td>{model.meanIc.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="grid">
            {alerts.map((alert) => (
              <div key={alert.id} className="note">
                <div style={{ display: "flex", justifyContent: "space-between", gap: "0.8rem", marginBottom: "0.5rem" }}>
                  <span className={`badge ${alert.severity}`}>{alert.severity}</span>
                  <span className="card-label">{alert.timestamp}</span>
                </div>
                <strong className="strong">{alert.title}</strong>
                <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>{alert.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </SectionCard>
    </AppShell>
  );
}
