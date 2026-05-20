import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buildAgentLogPayload } from "@/lib/server/agentLogPayload";
import { requireDefaultUser } from "@/lib/server/defaultUser";

function money(v: number | null) {
  if (v == null) return "—";
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function delta(v: number | null) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default async function LogsPage() {
  const user = await requireDefaultUser();
  const data = await buildAgentLogPayload(user.id);
  const mockModeActive = data.summary.mockRuns > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Agent Log</h1>
        <p className="text-sm text-muted-foreground">
          Every agent run, with timing, trade counts, cash movement, and portfolio change during that run.
        </p>
      </div>

      {mockModeActive ? (
        <Card className="border-warning/40 bg-warning/5">
          <CardContent className="pt-6 text-sm text-warning-foreground">
            Recent runs are still using mock/synthetic market data. In that mode, buys start slightly negative from
            slippage and then prices remain effectively flat, so this page cannot tell you whether the strategy would
            make money in live markets.
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total runs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">{data.summary.totalRuns}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Scheduled runs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">{data.summary.scheduledRuns}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Completed runs</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold tabular-nums">{data.summary.completedRuns}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Net portfolio change</CardTitle>
          </CardHeader>
          <CardContent>
            <p className={`text-2xl font-semibold tabular-nums ${data.summary.netPortfolioChange >= 0 ? "text-success" : "text-danger"}`}>
              {delta(data.summary.netPortfolioChange)}
            </p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Run history</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-2 pr-3 font-medium">When</th>
                  <th className="pb-2 pr-3 font-medium">Source</th>
                  <th className="pb-2 pr-3 font-medium">Status</th>
                  <th className="pb-2 pr-3 font-medium text-right">Buys</th>
                  <th className="pb-2 pr-3 font-medium text-right">Sells</th>
                  <th className="pb-2 pr-3 font-medium text-right">Cash before</th>
                  <th className="pb-2 pr-3 font-medium text-right">Cash after</th>
                  <th className="pb-2 pr-3 font-medium text-right">Portfolio change</th>
                  <th className="pb-2 font-medium">Details</th>
                </tr>
              </thead>
              <tbody>
                {data.rows.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-10 text-center text-muted-foreground">
                      No agent runs recorded yet.
                    </td>
                  </tr>
                ) : (
                  data.rows.map((row) => (
                    <tr key={row.id} className="border-b border-border/40 align-top">
                      <td className="py-2 pr-3 whitespace-nowrap text-xs text-muted-foreground">
                        <div>{row.startedAt.toLocaleString()}</div>
                        {row.finishedAt ? <div>done {row.finishedAt.toLocaleTimeString()}</div> : null}
                      </td>
                      <td className="py-2 pr-3 capitalize">{row.triggerSource.replaceAll("_", " ")}</td>
                      <td className="py-2 pr-3">
                        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          row.status === "completed"
                            ? "bg-success/10 text-success"
                            : row.status === "failed"
                              ? "bg-danger/10 text-danger"
                              : row.status === "skipped"
                                ? "bg-muted text-muted-foreground"
                                : "bg-warning/10 text-warning"
                        }`}>
                          {row.status}
                        </span>
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{row.buysCount}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{row.sellsCount}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{money(row.cashBefore)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{money(row.cashAfter)}</td>
                      <td className={`py-2 pr-3 text-right tabular-nums ${
                        (row.portfolioChange ?? 0) >= 0 ? "text-success" : "text-danger"
                      }`}>
                        {delta(row.portfolioChange)}
                      </td>
                      <td className="py-2">
                        <Link
                          href={`/decisions/${row.id}/explorer`}
                          className="text-xs text-foreground/90 hover:text-foreground hover:underline"
                        >
                          Open explorer
                        </Link>
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
