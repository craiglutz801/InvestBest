import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AllocationChart } from "@/components/charts/AllocationBar";
import { DrawdownChart } from "@/components/charts/DrawdownChart";
import { EquityBenchmarkChart } from "@/components/charts/EquityBenchmarkChart";
import { DashboardHoldingsPerformance } from "@/components/holdings/DashboardHoldingsPerformance";
import { AgentRunStatusCard } from "@/components/dashboard/AgentRunStatusCard";
import { DiagnosticsSummaryStrip } from "@/components/diagnostics/DiagnosticsSummaryStrip";
import { PortfolioAskPanel } from "@/components/dashboard/PortfolioAskPanel";
import {
  buildDiagnosticsPayload,
  diagnosticsPayloadFailed,
} from "@/lib/diagnostics/buildDiagnosticsPayload";
import { DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS } from "@/lib/diagnostics/constants";
import { buildDashboardPayload } from "@/lib/server/dashboardPayload";
import { requireDefaultUser } from "@/lib/server/defaultUser";
import { cn } from "@/lib/utils";

function Money({ v, className }: { v: number; className?: string }) {
  return <span className={cn("tabular-nums", className)}>${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}</span>;
}

function Pct({ v, className }: { v: number; className?: string }) {
  const pos = v >= 0;
  return (
    <span className={cn("tabular-nums", pos ? "text-success" : "text-danger", className)}>
      {pos ? "+" : ""}
      {v.toFixed(2)}%
    </span>
  );
}

export default async function DashboardPage() {
  const user = await requireDefaultUser();
  const d = await buildDashboardPayload(user.id);
  let diagnosticsQuick;
  try {
    diagnosticsQuick = await buildDiagnosticsPayload(user.id, {
      windowDays: DEFAULT_DIAGNOSTICS_SUMMARY_WINDOW_DAYS,
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    diagnosticsQuick = diagnosticsPayloadFailed(msg);
  }
  const s = d.summary;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">Paper portfolio overview and latest agent activity.</p>
      </div>

      <AgentRunStatusCard />

      <DiagnosticsSummaryStrip payload={diagnosticsQuick} />

      <PortfolioAskPanel hasOpenAiKey={Boolean(process.env.OPENAI_API_KEY)} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total value</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">
              <Money v={s.totalValue} />
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Return <Pct v={s.totalReturnPct} />
              {s.benchmarkReturnPct != null ? (
                <>
                  {" "}
                  · SPY same-period <Pct v={s.benchmarkReturnPct} />
                </>
              ) : null}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Cash</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">
              <Money v={s.cash} />
            </p>
            <p className="mt-1 text-xs text-muted-foreground">Invested · <Money v={s.invested} /></p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Unrealized P&amp;L</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={cn("text-2xl font-semibold", s.unrealizedPnl >= 0 ? "text-success" : "text-danger")}>
              <Money v={s.unrealizedPnl} />
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Realized ·{" "}
              <span className={s.realizedPnl >= 0 ? "text-success" : "text-danger"}>
                <Money v={s.realizedPnl} />
              </span>
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Agent</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold">{s.openPositions}</p>
            <p className="mt-1 text-xs text-muted-foreground">
              Open positions · Max DD {s.maxDrawdownPct.toFixed(2)}%
            </p>
            {d.lastRun ? (
              <p className="mt-2 text-xs">
                Last run:{" "}
                <span className="font-medium capitalize">{d.lastRun.status}</span> · {d.lastRun.buysCount} buys ·{" "}
                {d.lastRun.sellsCount} sells
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {d.discoverySummary ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Opportunity discovery</CardTitle>
            <p className="text-sm font-normal text-muted-foreground">
              Last completed run · Search profile:{" "}
              <span className="font-medium text-foreground">{d.discoverySummary.profileName ?? "—"}</span>
              {d.discoverySummary.finishedAt ? (
                <>
                  {" "}
                  · {new Date(d.discoverySummary.finishedAt).toLocaleString()}
                </>
              ) : null}
            </p>
          </CardHeader>
          <CardContent>
            <pre className="max-h-52 overflow-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-[11px] leading-relaxed">
              {JSON.stringify(d.discoverySummary.stats, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}

      {d.lastRun?.llmSummary ? (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Agent summary</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-muted-foreground">{d.lastRun.llmSummary}</p>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Equity vs benchmark</CardTitle>
          </CardHeader>
          <CardContent>
            <EquityBenchmarkChart points={d.equityCurve} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Allocation</CardTitle>
          </CardHeader>
          <CardContent className="flex justify-center">
            <AllocationChart data={d.allocation} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Drawdown from peak</CardTitle>
          <p className="text-sm font-normal text-muted-foreground">
            How far below the running portfolio high you&apos;ve been at each snapshot. Lower is worse;
            shallow, short troughs are healthy.
          </p>
        </CardHeader>
        <CardContent>
          <DrawdownChart points={d.drawdownCurve} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Holdings performance</CardTitle>
          <p className="text-sm font-normal text-muted-foreground">
            Position value over time since each open (area). Dashed line is cost basis. DoD compares the last two
            daily marks stored by the agent; &quot;vs bar&quot; is your live quote vs the latest stored daily close.
          </p>
        </CardHeader>
        <CardContent>
          <DashboardHoldingsPerformance rows={d.holdingsPerformance} />
        </CardContent>
      </Card>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Latest buys</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {d.latestBuys.length === 0 ? (
                <li className="text-muted-foreground">No buys yet.</li>
              ) : (
                d.latestBuys.map((t) => (
                  <li key={t.id} className="flex justify-between gap-2 border-b border-border/60 pb-2">
                    <span>
                      <span className="font-medium">{t.ticker}</span>{" "}
                      <span className="text-muted-foreground">
                        {t.qty} @ {t.price.toFixed(2)}
                      </span>
                    </span>
                    <span className="text-xs text-muted-foreground">{new Date(t.at).toLocaleString()}</span>
                  </li>
                ))
              )}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Latest sells</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {d.latestSells.length === 0 ? (
                <li className="text-muted-foreground">No sells yet.</li>
              ) : (
                d.latestSells.map((t) => (
                  <li key={t.id} className="flex justify-between gap-2 border-b border-border/60 pb-2">
                    <span>
                      <span className="font-medium">{t.ticker}</span>{" "}
                      <span className="text-muted-foreground">{t.reason?.slice(0, 48)}</span>
                    </span>
                    <span className="text-xs text-muted-foreground">{new Date(t.at).toLocaleString()}</span>
                  </li>
                ))
              )}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Short activity</CardTitle>
            <p className="text-sm font-normal text-muted-foreground">
              Opens (SHORT) and buy-to-covers when shorting is enabled and bear-score gates pass.
            </p>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {d.latestShortActivity.length === 0 ? (
                <li className="text-muted-foreground">No short trades yet.</li>
              ) : (
                d.latestShortActivity.map((t) => (
                  <li key={t.id} className="flex justify-between gap-2 border-b border-border/60 pb-2">
                    <span>
                      <span className="font-medium">{t.ticker}</span>{" "}
                      <span className="rounded bg-muted px-1 text-[10px] font-medium uppercase text-muted-foreground">
                        {t.action}
                      </span>{" "}
                      <span className="text-muted-foreground">
                        {t.qty} @ {t.price.toFixed(2)}
                      </span>
                    </span>
                    <span className="text-xs text-muted-foreground">{new Date(t.at).toLocaleString()}</span>
                  </li>
                ))
              )}
            </ul>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-success">Top winners</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {d.topWinners.length === 0 ? (
                <li className="text-muted-foreground">No open positions.</li>
              ) : (
                d.topWinners.map((w) => (
                  <li key={w.symbol} className="flex justify-between">
                    <span className="font-medium">{w.symbol}</span>
                    <Pct v={w.unrealizedPct} />
                  </li>
                ))
              )}
            </ul>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-base text-danger">Top losers</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {d.topLosers.length === 0 ? (
                <li className="text-muted-foreground">No open positions.</li>
              ) : (
                d.topLosers.map((w) => (
                  <li key={w.symbol} className="flex justify-between">
                    <span className="font-medium">{w.symbol}</span>
                    <Pct v={w.unrealizedPct} />
                  </li>
                ))
              )}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Today&apos;s latest decisions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Symbol</th>
                  <th className="pb-2 pr-4 font-medium">Action</th>
                  <th className="pb-2 pr-4 font-medium">Buy</th>
                  <th className="pb-2 pr-4 font-medium">Sell risk</th>
                  <th className="pb-2 pr-4 font-medium">Conf.</th>
                  <th className="pb-2 font-medium">Rationale</th>
                </tr>
              </thead>
              <tbody>
                {d.latestDecisionItems.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-4 text-muted-foreground">
                      No decision items yet. Run the hourly agent.
                    </td>
                  </tr>
                ) : (
                  d.latestDecisionItems.map((r, i) => (
                    <tr key={i} className="border-b border-border/40">
                      <td className="py-2 pr-4 font-medium">{r.ticker}</td>
                      <td className="py-2 pr-4 capitalize">
                        {r.blocked ? `skip (${r.blockedReason ?? "blocked"})` : r.action}
                      </td>
                      <td className="py-2 pr-4 tabular-nums">{r.buyScore?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-4 tabular-nums">{r.sellRisk?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-4 tabular-nums">{r.confidence?.toFixed(0) ?? "—"}</td>
                      <td className="py-2 text-muted-foreground">
                        <p className="max-w-lg whitespace-pre-wrap text-xs" title={r.note ?? ""}>
                          {r.note ?? "—"}
                        </p>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
