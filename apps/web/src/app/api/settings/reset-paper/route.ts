import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { requireDefaultUser } from "@/lib/server/defaultUser";

const RESET_STARTING_CASH = 100_000;

/** Deletes all paper trades, positions, portfolio snapshots, and decision runs; sets starting cash to $100,000. */
export async function POST(req: Request) {
  try {
    const user = await requireDefaultUser();
    const body = (await req.json().catch(() => ({}))) as { acknowledged?: unknown };
    if (body.acknowledged !== true) {
      return jsonError("Body must include acknowledged: true", 400);
    }

    await prisma.$transaction(async (tx) => {
      await tx.paperTrade.deleteMany({ where: { userId: user.id } });
      await tx.paperPosition.deleteMany({ where: { userId: user.id } });
      await tx.portfolioSnapshot.deleteMany({ where: { userId: user.id } });
      await tx.$executeRaw`DELETE FROM "HoldingValueLog" WHERE "userId" = ${user.id}`;
      await tx.positionValuation.deleteMany({ where: { userId: user.id } });
      await tx.quoteSnapshot.deleteMany({ where: { userId: user.id } });
      await tx.decisionRun.deleteMany({ where: { userId: user.id } });
      await tx.appSettings.update({
        where: { userId: user.id },
        data: { startingCash: RESET_STARTING_CASH },
      });
    });

    return jsonOk({ ok: true, startingCash: RESET_STARTING_CASH });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Reset failed", 500);
  }
}
