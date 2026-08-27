import { jsonError, jsonOk } from "@/lib/api/http";
import { settingsUpdateSchema } from "@/lib/api/settingsSchema";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export async function GET() {
  try {
    const user = await requireDefaultUser();
    const s = await prisma.appSettings.findUnique({ where: { userId: user.id } });
    if (!s) return jsonError("Settings not found", 404);
    return jsonOk({
      startingCash: toNum(s.startingCash),
      maxPositionPct: toNum(s.maxPositionPct),
      maxNewPositionsPerRun: s.maxNewPositionsPerRun,
      targetHoldings: s.targetHoldings,
      stopLossPct: toNum(s.stopLossPct),
      takeProfitPct: toNum(s.takeProfitPct),
      minConfidence: toNum(s.minConfidence),
      cashReservePct: toNum(s.cashReservePct),
      runFrequencyMinutes: s.runFrequencyMinutes,
      paperStartDate: s.paperStartDate?.toISOString() ?? null,
      paperEndDate: s.paperEndDate?.toISOString() ?? null,
      agentPaused: Boolean((s as { agentPaused?: boolean }).agentPaused),
      newsEnabled: s.newsEnabled,
      shortingEnabled: s.shortingEnabled,
      defaultSlippagePct: toNum(s.defaultSlippagePct),
      strategyMode: s.strategyMode,
      buyScoreThreshold: toNum(s.buyScoreThreshold),
      sellRiskThreshold: toNum(s.sellRiskThreshold),
      cooldownHours: s.cooldownHours,
      staleQuoteAllowSells: s.staleQuoteAllowSells,
      buyScoreMargin: toNum(s.buyScoreMargin),
      confidenceMarginForBuy: toNum(s.confidenceMarginForBuy),
      requireMomentumForBuy: s.requireMomentumForBuy,
      maxBuyAnnualVol: toNum(s.maxBuyAnnualVol),
      bearScoreThreshold: toNum(s.bearScoreThreshold),
      confidenceMarginForShort: toNum(s.confidenceMarginForShort),
      shortOnlyInBearRegime: s.shortOnlyInBearRegime,
      maxShortPositionsPerRun: s.maxShortPositionsPerRun,
      buyScoreCoverShortThreshold: toNum(s.buyScoreCoverShortThreshold),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}

export async function PUT(req: Request) {
  try {
    const user = await requireDefaultUser();
    const raw = await req.json();
    const parsed = settingsUpdateSchema.safeParse(raw);
    if (!parsed.success) {
      return jsonError(parsed.error.message, 400);
    }
    const b = parsed.data;

    const data: Record<string, unknown> = {};

    if (b.startingCash !== undefined) data.startingCash = b.startingCash;
    if (b.maxPositionPct !== undefined) data.maxPositionPct = b.maxPositionPct;
    if (b.maxNewPositionsPerRun !== undefined) data.maxNewPositionsPerRun = b.maxNewPositionsPerRun;
    if (b.targetHoldings !== undefined) data.targetHoldings = b.targetHoldings;
    if (b.stopLossPct !== undefined) data.stopLossPct = b.stopLossPct;
    if (b.takeProfitPct !== undefined) data.takeProfitPct = b.takeProfitPct;
    if (b.minConfidence !== undefined) data.minConfidence = b.minConfidence;
    if (b.cashReservePct !== undefined) data.cashReservePct = b.cashReservePct;
    if (b.runFrequencyMinutes !== undefined) data.runFrequencyMinutes = b.runFrequencyMinutes;
    if (b.newsEnabled !== undefined) data.newsEnabled = b.newsEnabled;
    if (b.shortingEnabled !== undefined) data.shortingEnabled = b.shortingEnabled;
    if (b.defaultSlippagePct !== undefined) data.defaultSlippagePct = b.defaultSlippagePct;
    if (b.strategyMode !== undefined) data.strategyMode = b.strategyMode;
    if (b.buyScoreThreshold !== undefined) data.buyScoreThreshold = b.buyScoreThreshold;
    if (b.sellRiskThreshold !== undefined) data.sellRiskThreshold = b.sellRiskThreshold;
    if (b.cooldownHours !== undefined) data.cooldownHours = b.cooldownHours;
    if (b.staleQuoteAllowSells !== undefined) data.staleQuoteAllowSells = b.staleQuoteAllowSells;
    if (b.buyScoreMargin !== undefined) data.buyScoreMargin = b.buyScoreMargin;
    if (b.confidenceMarginForBuy !== undefined) data.confidenceMarginForBuy = b.confidenceMarginForBuy;
    if (b.requireMomentumForBuy !== undefined) data.requireMomentumForBuy = b.requireMomentumForBuy;
    if (b.maxBuyAnnualVol !== undefined) data.maxBuyAnnualVol = b.maxBuyAnnualVol;
    if (b.bearScoreThreshold !== undefined) data.bearScoreThreshold = b.bearScoreThreshold;
    if (b.confidenceMarginForShort !== undefined) data.confidenceMarginForShort = b.confidenceMarginForShort;
    if (b.shortOnlyInBearRegime !== undefined) data.shortOnlyInBearRegime = b.shortOnlyInBearRegime;
    if (b.maxShortPositionsPerRun !== undefined) data.maxShortPositionsPerRun = b.maxShortPositionsPerRun;
    if (b.buyScoreCoverShortThreshold !== undefined)
      data.buyScoreCoverShortThreshold = b.buyScoreCoverShortThreshold;
    if (b.paperStartDate !== undefined) {
      data.paperStartDate =
        b.paperStartDate === null || b.paperStartDate === ""
          ? null
          : new Date(b.paperStartDate);
    }
    if (b.paperEndDate !== undefined) {
      data.paperEndDate =
        b.paperEndDate === null || b.paperEndDate === "" ? null : new Date(b.paperEndDate);
    }
    if (b.agentPaused !== undefined) data.agentPaused = b.agentPaused;

    const updated = await prisma.appSettings.update({
      where: { userId: user.id },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      data: data as any,
    });

    return jsonOk({
      id: updated.id,
      ok: true,
      startingCash: toNum(updated.startingCash),
      maxPositionPct: toNum(updated.maxPositionPct),
    });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Error", 500);
  }
}
