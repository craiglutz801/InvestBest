import { prisma } from "@/lib/db";

/** Symbols enabled via segment links; if none configured, all active symbols (migration / empty segments). */
export async function getTradableSymbols() {
  /** Stale or edge-bundled `@prisma/client` may omit `segmentSymbol` — avoid `undefined.findMany`. */
  const segmentSymbol = (prisma as unknown as { segmentSymbol?: typeof prisma.segmentSymbol }).segmentSymbol;
  if (!segmentSymbol) {
    return prisma.symbol.findMany({
      where: { isActive: true },
      orderBy: { ticker: "asc" },
    });
  }

  const links = await segmentSymbol.findMany({
    where: {
      isEnabled: true,
      universeSegment: { isEnabled: true },
      symbol: { isActive: true },
    },
    include: { symbol: true },
  });

  if (links.length === 0) {
    return prisma.symbol.findMany({
      where: { isActive: true },
      orderBy: { ticker: "asc" },
    });
  }

  const byId = new Map<string, (typeof links)[0]["symbol"]>();
  for (const l of links) {
    byId.set(l.symbol.id, l.symbol);
  }
  return [...byId.values()].sort((a, b) => a.ticker.localeCompare(b.ticker));
}
