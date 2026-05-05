import Link from "next/link";
import { notFound } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScoreBar } from "@/components/ui/ScoreBar";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { requireDefaultUser } from "@/lib/server/defaultUser";
import type { Prisma } from "@prisma/client";

const SORT_FIELDS = ["ticker", "status", "buyScore", "buyRank", "segmentKey"] as const;
type SortField = (typeof SORT_FIELDS)[number];

function orderByFromQuery(sort: string | undefined, dir: string | undefined): Prisma.DecisionRunCandidateOrderByWithRelationInput {
  const d = dir === "desc" ? "desc" : "asc";
  const s = SORT_FIELDS.includes(sort as SortField) ? (sort as SortField) : "ticker";
  if (s === "buyRank") return { buyRank: d };
  return { [s]: d };
}

function fmtNum(v: { toString(): string } | null | undefined, digits = 2): string {
  if (v == null) return "—";
  const n = toNum(v);
  if (!Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ sort?: string; dir?: string }>;
};

export default async function DecisionRunExplorerPage(props: PageProps) {
  const user = await requireDefaultUser();
  const { id } = await props.params;
  const sp = await props.searchParams;
  const sort = sp.sort;
  const dir = sp.dir;

  const run = await prisma.decisionRun.findFirst({
    where: { id, userId: user.id },
  });
  if (!run) notFound();

  const candidates = await prisma.decisionRunCandidate.findMany({
    where: { decisionRunId: id },
    orderBy: orderByFromQuery(sort, dir),
  });

  const q = (s: string, d: "asc" | "desc") => {
    const p = new URLSearchParams();
    if (s !== "ticker" || d !== "asc") {
      p.set("sort", s);
      p.set("dir", d);
    }
    const qs = p.toString();
    return qs ? `?${qs}` : "";
  };

  const th = (label: string, field: SortField) => {
    const active = (sort ?? "ticker") === field;
    const nextDir = active && (dir ?? "asc") === "asc" ? "desc" : "asc";
    return (
      <th className="pb-2 pr-2 font-medium">
        <Link
          href={`/decisions/${id}/explorer${q(field, nextDir)}`}
          className={active ? "text-foreground underline-offset-4 hover:underline" : "text-muted-foreground hover:text-foreground hover:underline"}
        >
          {label}
          {active ? (dir === "desc" ? " ↓" : " ↑") : ""}
        </Link>
      </th>
    );
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <div>
          <p className="text-sm text-muted-foreground">
            <Link href="/decisions" className="hover:text-foreground hover:underline">
              Decisions
            </Link>
            <span className="mx-1.5 text-border">/</span>
            <span className="text-foreground">Candidate explorer</span>
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Run explorer</h1>
          <p className="text-sm text-muted-foreground">
            {run.startedAt.toLocaleString()} · {run.status} · {candidates.length} symbol{candidates.length === 1 ? "" : "s"}
          </p>
        </div>
        <a
          href={`/api/runs/${id}/candidates?format=csv`}
          className="text-sm text-muted-foreground hover:text-foreground hover:underline"
        >
          Download CSV
        </a>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Per-symbol scan</CardTitle>
        </CardHeader>
        <CardContent>
          {candidates.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No candidate rows for this run. Completed runs after this feature ships will populate the grid here.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b text-muted-foreground">
                    {th("Ticker", "ticker")}
                    {th("Segment", "segmentKey")}
                    {th("Status", "status")}
                    <th className="pb-2 pr-2 font-medium text-right">Price</th>
                    <th className="pb-2 pr-2 font-medium text-right">1d</th>
                    <th className="pb-2 pr-2 font-medium text-right">5d</th>
                    <th className="pb-2 pr-2 font-medium text-right">Vol</th>
                    <th className="pb-2 pr-2 font-medium text-right">Buy</th>
                    <th className="pb-2 pr-2 font-medium text-right">Sell risk</th>
                    <th className="pb-2 pr-2 font-medium text-right">Conf.</th>
                    {th("Buy rank", "buyRank")}
                    <th className="pb-2 font-medium">Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.id} className="border-b border-border/40">
                      <td className="py-1.5 pr-2 font-medium">{c.ticker}</td>
                      <td className="py-1.5 pr-2 text-xs text-muted-foreground">{c.segmentKey ?? "—"}</td>
                      <td className="py-1.5 pr-2 capitalize">{c.status.replace(/_/g, " ")}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{fmtNum(c.currentPrice, 4)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{fmtNum(c.ret1d, 3)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{fmtNum(c.ret5d, 3)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{fmtNum(c.volatility20d, 3)}</td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        <ScoreBar value={c.buyScore != null ? toNum(c.buyScore) : null} kind="buy" />
                      </td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        <ScoreBar value={c.sellRiskScore != null ? toNum(c.sellRiskScore) : null} kind="sellRisk" />
                      </td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">
                        <ScoreBar
                          value={c.confidenceScore != null ? toNum(c.confidenceScore) : null}
                          kind="confidence"
                        />
                      </td>
                      <td className="py-1.5 pr-2 text-right tabular-nums">{c.buyRank ?? "—"}</td>
                      <td className="py-1.5 max-w-xs text-xs text-muted-foreground">{c.rejectionReason ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
