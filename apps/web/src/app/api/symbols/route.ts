import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";
import { z } from "zod";

export async function GET() {
  try {
    await requireDefaultUser();
    const symbols = await prisma.symbol.findMany({ orderBy: { ticker: "asc" } });
    return jsonOk({
      symbols: symbols.map((s) => ({
        id: s.id,
        ticker: s.ticker,
        name: s.name,
        assetType: s.assetType,
        exchange: s.exchange,
        isActive: s.isActive,
        dataProviderSymbol: s.dataProviderSymbol,
      })),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}

const putSchema = z.object({
  updates: z.array(
    z.object({
      ticker: z.string().min(1),
      isActive: z.boolean(),
    }),
  ),
});

export async function PUT(req: Request) {
  try {
    await requireDefaultUser();
    const raw = await req.json();
    const parsed = putSchema.safeParse(raw);
    if (!parsed.success) return jsonError(parsed.error.message, 400);

    for (const u of parsed.data.updates) {
      await prisma.symbol.updateMany({
        where: { ticker: u.ticker },
        data: { isActive: u.isActive },
      });
    }

    return jsonOk({ ok: true, count: parsed.data.updates.length });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
