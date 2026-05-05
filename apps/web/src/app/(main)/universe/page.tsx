import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export default async function UniversePage() {
  await requireDefaultUser();
  const segments = await prisma.universeSegment.findMany({
    orderBy: { sortOrder: "asc" },
    include: {
      segmentSymbols: {
        where: { isEnabled: true, symbol: { isActive: true } },
        include: { symbol: true },
        orderBy: { priority: "asc" },
      },
    },
  });

  const totalSymbols = new Set<string>();
  for (const s of segments) {
    for (const ss of s.segmentSymbols) {
      totalSymbols.add(ss.symbol.ticker);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Universe</h1>
        <p className="text-sm text-muted-foreground">
          Curated multi-segment opportunity set scanned each agent run (defense, energy, agriculture, metals, macro
          proxies, and core equities). Toggle segments via the API or seed; v1 UI is read-only.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Unique tickers linked to at least one enabled segment:{" "}
          <span className="font-medium text-foreground">{totalSymbols.size}</span>
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {segments.map((seg) => (
          <Card key={seg.id}>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{seg.name}</CardTitle>
              <p className="text-xs text-muted-foreground">
                <span className="font-mono">{seg.key}</span>
                {seg.isEnabled ? (
                  <span className="ml-2 rounded bg-success/15 px-1.5 py-0.5 text-success">enabled</span>
                ) : (
                  <span className="ml-2 rounded bg-muted px-1.5 py-0.5">disabled</span>
                )}
              </p>
            </CardHeader>
            <CardContent className="space-y-2 text-sm">
              {seg.description ? <p className="text-muted-foreground">{seg.description}</p> : null}
              <p className="text-xs text-muted-foreground">
                Max positions from segment (hint): {seg.maxPositions} · weight: {Number(seg.segmentWeight)}
              </p>
              <div className="max-h-40 overflow-y-auto rounded border border-border/60 bg-muted/20 p-2 font-mono text-[11px] leading-relaxed">
                {seg.segmentSymbols.map((ss) => ss.symbol.ticker).join(", ")}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
