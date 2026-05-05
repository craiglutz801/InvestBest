import { PositionValueMiniChart } from "@/components/charts/PositionValueMiniChart";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buildHoldingsPayload } from "@/lib/server/holdingsPayload";
import { requireDefaultUser } from "@/lib/server/defaultUser";
import { cn } from "@/lib/utils";

function DeltaPct({ v }: { v: number | null }) {
  if (v == null || Number.isNaN(v)) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <span className={cn("tabular-nums", v >= 0 ? "text-success" : "text-danger")}>
      {v >= 0 ? "+" : ""}
      {v.toFixed(2)}%
    </span>
  );
}

export default async function HoldingsPage() {
  const user = await requireDefaultUser();
  const rows = await buildHoldingsPayload(user.id);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Holdings</h1>
        <p className="text-sm text-muted-foreground">
          Open positions, recent value deltas from stored daily marks, and a small chart of market value since you
          opened (dashed = cost basis).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Positions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-2 pr-3 font-medium">Symbol</th>
                  <th className="pb-2 pr-3 font-medium text-xs">Segment</th>
                  <th className="pb-2 pr-3 font-medium">Type</th>
                  <th className="pb-2 pr-3 font-medium text-right">Qty</th>
                  <th className="pb-2 pr-3 font-medium text-right">Avg</th>
                  <th className="pb-2 pr-3 font-medium text-right">Price</th>
                  <th className="pb-2 pr-3 font-medium text-xs" title="Last live quote time from agent run">
                    Quote
                  </th>
                  <th className="pb-2 pr-3 font-medium text-right">Value</th>
                  <th className="pb-2 pr-3 font-medium text-right">U. P&amp;L</th>
                  <th className="pb-2 pr-3 font-medium text-right">U. %</th>
                  <th className="pb-2 pr-3 text-right font-medium" title="Last two daily marks in DB">
                    DoD
                  </th>
                  <th className="pb-2 pr-3 text-right font-medium" title="Current vs last stored daily close">
                    vs bar
                  </th>
                  <th className="pb-2 pr-3 font-medium">Since open</th>
                  <th className="pb-2 pr-3 font-medium text-right">Buy</th>
                  <th className="pb-2 pr-3 font-medium text-right">Sell risk</th>
                  <th className="pb-2 pr-3 font-medium text-right">Conf.</th>
                  <th className="pb-2 pr-3 font-medium text-right">Exp. 5d</th>
                  <th className="pb-2 pr-3 font-medium">Since</th>
                  <th className="pb-2 font-medium">Note</th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={19} className="py-8 text-center text-muted-foreground">
                      No open positions.
                    </td>
                  </tr>
                ) : (
                  rows.map((r) => (
                    <tr key={r.symbol} className="border-b border-border/40">
                      <td className="py-2 pr-3 font-medium">
                        {r.symbol}
                        {r.isShort ? (
                          <span className="ml-1 align-middle rounded bg-muted px-1 text-[10px] font-medium uppercase text-muted-foreground">
                            short
                          </span>
                        ) : null}
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs text-muted-foreground">
                        {r.segmentKey ?? "—"}
                      </td>
                      <td className="py-2 pr-3 capitalize">{r.assetType}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{r.quantity.toFixed(4)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{r.avgCost.toFixed(2)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{r.currentPrice.toFixed(2)}</td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">
                        {r.lastQuoteAt ? (
                          <span className="tabular-nums">{new Date(r.lastQuoteAt).toLocaleString()}</span>
                        ) : (
                          "—"
                        )}
                        {r.valuationStatus === "stale" ? (
                          <span className="ml-1 rounded bg-amber-500/20 px-1 text-[10px] font-medium text-amber-900 dark:text-amber-200">
                            stale
                          </span>
                        ) : null}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{r.marketValue.toFixed(2)}</td>
                      <td
                        className={`py-2 pr-3 text-right tabular-nums ${r.unrealizedPnl >= 0 ? "text-success" : "text-danger"}`}
                      >
                        {r.unrealizedPnl.toFixed(2)}
                      </td>
                      <td
                        className={`py-2 pr-3 text-right tabular-nums ${r.unrealizedPnlPct >= 0 ? "text-success" : "text-danger"}`}
                      >
                        {r.unrealizedPnlPct.toFixed(2)}%
                      </td>
                      <td className="py-2 pr-3 text-right">
                        <DeltaPct v={r.dayOverDayPct} />
                      </td>
                      <td className="py-2 pr-3 text-right">
                        <DeltaPct v={r.vsLastSnapshotPct} />
                      </td>
                      <td
                        className="py-2 pr-3 align-middle"
                        title="Each point is position value when a run finished. We use the live quote at run end so intraday runs can move; many identical quotes still look flat."
                      >
                        <PositionValueMiniChart points={r.valueHistory} costBasisValue={r.costBasisValue} />
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums">{r.buyScore?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{r.sellRiskScore?.toFixed(1) ?? "—"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{r.confidenceScore?.toFixed(0) ?? "—"}</td>
                      <td className={`py-2 pr-3 text-right tabular-nums ${(r.expectedReturn5d ?? 0) >= 0 ? "text-success" : "text-danger"}`}>
                        {r.expectedReturn5d != null ? `${(r.expectedReturn5d * 100).toFixed(1)}%` : "—"}
                      </td>
                      <td className="py-2 pr-3 text-xs text-muted-foreground">{new Date(r.openedAt).toLocaleDateString()}</td>
                      <td className="py-2 text-muted-foreground">
                        <p className="max-w-[220px] whitespace-pre-wrap text-xs" title={r.lastAgentNote ?? ""}>
                          {r.lastAgentNote ?? "—"}
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
