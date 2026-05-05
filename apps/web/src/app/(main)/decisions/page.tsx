import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export default async function DecisionsPage() {
  const user = await requireDefaultUser();
  const runs = await prisma.decisionRun.findMany({
    where: { userId: user.id },
    orderBy: { startedAt: "desc" },
    take: 40,
    include: {
      items: { include: { symbol: true } },
    },
  });

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Decisions</h1>
        <p className="text-sm text-muted-foreground">Hourly decision runs and per-symbol recommendations.</p>
      </div>

      {runs.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">No runs recorded yet.</CardContent>
        </Card>
      ) : (
        runs.map((run) => (
          <Card key={run.id}>
            <CardHeader>
              <CardTitle className="flex flex-wrap items-baseline justify-between gap-2 text-base">
                <span>
                  Run · {run.startedAt.toLocaleString()}{" "}
                  <span className="font-normal capitalize text-muted-foreground">({run.status})</span>
                </span>
                <span className="flex flex-wrap items-center gap-3 text-sm font-normal text-muted-foreground">
                  <span>
                    universe {run.universeSize} · buys {run.buysCount} · sells {run.sellsCount}
                  </span>
                  <Link
                    href={`/decisions/${run.id}/explorer`}
                    className="text-foreground/90 hover:text-foreground hover:underline"
                  >
                    Explorer
                  </Link>
                </span>
              </CardTitle>
              {run.portfolioValueBefore != null && run.portfolioValueAfter != null ? (
                <p className="text-sm text-muted-foreground">
                  Portfolio ${toNum(run.portfolioValueBefore).toFixed(2)} → ${toNum(run.portfolioValueAfter).toFixed(2)}
                </p>
              ) : null}
              {run.llmSummary ? (
                <p className="text-sm leading-relaxed text-muted-foreground whitespace-pre-wrap">{run.llmSummary}</p>
              ) : null}
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b text-muted-foreground">
                      <th className="pb-2 pr-2 font-medium">Symbol</th>
                      <th className="pb-2 pr-2 font-medium">Rec.</th>
                      <th className="pb-2 pr-2 font-medium">Blocked</th>
                      <th className="pb-2 pr-2 font-medium text-right">Buy</th>
                      <th className="pb-2 pr-2 font-medium text-right">Sell risk</th>
                      <th className="pb-2 pr-2 font-medium text-right">Conf.</th>
                      <th className="pb-2 font-medium">Rationale</th>
                    </tr>
                  </thead>
                  <tbody>
                    {run.items.slice(0, 60).map((it) => (
                      <tr key={it.id} className="border-b border-border/40">
                        <td className="py-1.5 pr-2 font-medium">{it.symbol.ticker}</td>
                        <td className="py-1.5 pr-2 capitalize">{it.actionRecommendation}</td>
                        <td className="py-1.5 pr-2 text-xs">{it.blocked ? it.blockedReason ?? "yes" : "—"}</td>
                        <td className="py-1.5 pr-2 text-right">
                          <ScoreBar value={it.buyScore != null ? toNum(it.buyScore) : null} kind="buy" />
                        </td>
                        <td className="py-1.5 pr-2 text-right">
                          <ScoreBar value={it.sellRiskScore != null ? toNum(it.sellRiskScore) : null} kind="sellRisk" />
                        </td>
                        <td className="py-1.5 pr-2 text-right">
                          <ScoreBar
                            value={it.confidenceScore != null ? toNum(it.confidenceScore) : null}
                            kind="confidence"
                          />
                        </td>
                        <td className="py-1.5 text-muted-foreground">
                          <p className="max-w-lg whitespace-pre-wrap text-xs" title={it.rationaleShort ?? ""}>
                            {it.rationaleShort ?? "—"}
                          </p>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}
