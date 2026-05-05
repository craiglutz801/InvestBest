import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export default async function TradesPage() {
  const user = await requireDefaultUser();
  const trades = await prisma.paperTrade.findMany({
    where: { userId: user.id },
    orderBy: { executedAt: "desc" },
    take: 200,
    include: { symbol: true },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Trades</h1>
        <p className="text-sm text-muted-foreground">Chronological paper execution log.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">History</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b text-muted-foreground">
                  <th className="pb-2 pr-3 font-medium">When</th>
                  <th className="pb-2 pr-3 font-medium">Symbol</th>
                  <th className="pb-2 pr-3 font-medium">Side</th>
                  <th className="pb-2 pr-3 font-medium text-right">Qty</th>
                  <th className="pb-2 pr-3 font-medium text-right">Price</th>
                  <th className="pb-2 pr-3 font-medium text-right">Gross</th>
                  <th className="pb-2 pr-3 font-medium text-right">Conf.</th>
                  <th className="pb-2 pr-3 font-medium">Horizon</th>
                  <th className="pb-2 pr-3 font-medium text-right">Cash before</th>
                  <th className="pb-2 pr-3 font-medium text-right">Cash after</th>
                  <th className="pb-2 font-medium">Reason</th>
                </tr>
              </thead>
              <tbody>
                {trades.length === 0 ? (
                  <tr>
                    <td colSpan={11} className="py-8 text-center text-muted-foreground">
                      No trades yet.
                    </td>
                  </tr>
                ) : (
                  trades.map((t) => (
                    <tr key={t.id} className="border-b border-border/40">
                      <td className="py-2 pr-3 whitespace-nowrap text-xs text-muted-foreground">
                        {t.executedAt.toLocaleString()}
                      </td>
                      <td className="py-2 pr-3 font-medium">{t.symbol.ticker}</td>
                      <td className="py-2 pr-3">{t.action}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{toNum(t.quantity).toFixed(4)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{toNum(t.price).toFixed(4)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">{toNum(t.grossAmount).toFixed(2)}</td>
                      <td className="py-2 pr-3 text-right tabular-nums">
                        {t.confidenceScore != null ? toNum(t.confidenceScore).toFixed(1) : "—"}
                      </td>
                      <td className="py-2 pr-3 text-xs">{t.expectedHorizon ?? "—"}</td>
                      <td className="py-2 pr-3 text-right tabular-nums text-xs">
                        {t.cashBefore != null ? toNum(t.cashBefore).toFixed(2) : "—"}
                      </td>
                      <td className="py-2 pr-3 text-right tabular-nums text-xs">
                        {t.cashAfter != null ? toNum(t.cashAfter).toFixed(2) : "—"}
                      </td>
                      <td className="py-2 text-muted-foreground">
                        <p className="max-w-sm whitespace-pre-wrap text-xs" title={t.reasonText ?? ""}>
                          {t.reasonText ?? t.reasonCode ?? "—"}
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
