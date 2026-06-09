import { z } from "zod";

export const settingsUpdateSchema = z.object({
  startingCash: z.number().positive().optional(),
  maxPositionPct: z.number().min(1).max(100).optional(),
  maxNewPositionsPerRun: z.number().int().min(0).max(20).optional(),
  targetHoldings: z.number().int().min(1).max(50).optional(),
  stopLossPct: z.number().min(0.1).max(50).optional(),
  takeProfitPct: z.number().min(0.1).max(200).optional(),
  minConfidence: z.number().min(0).max(100).optional(),
  cashReservePct: z.number().min(0).max(50).optional(),
  runFrequencyMinutes: z.number().int().min(5).optional(),
  paperStartDate: z.union([z.string(), z.null()]).optional(),
  paperEndDate: z.union([z.string(), z.null()]).optional(),
  newsEnabled: z.boolean().optional(),
  shortingEnabled: z.boolean().optional(),
  defaultSlippagePct: z.number().min(0).max(1).optional(),
  strategyMode: z.enum(["rules_v1", "alpha_v1", "regression_v1"]).optional(),
  buyScoreThreshold: z.number().min(0).max(100).optional(),
  sellRiskThreshold: z.number().min(0).max(100).optional(),
  cooldownHours: z.number().int().min(0).max(168).optional(),
  /** When false (default), sells are blocked if the live quote failed (STALE_DATA_HOLD). */
  staleQuoteAllowSells: z.boolean().optional(),
  buyScoreMargin: z.number().min(0).max(40).optional(),
  confidenceMarginForBuy: z.number().min(0).max(40).optional(),
  requireMomentumForBuy: z.boolean().optional(),
  maxBuyAnnualVol: z.number().min(0.05).max(2).optional(),
  bearScoreThreshold: z.number().min(0).max(100).optional(),
  confidenceMarginForShort: z.number().min(0).max(40).optional(),
  shortOnlyInBearRegime: z.boolean().optional(),
  maxShortPositionsPerRun: z.number().int().min(0).max(10).optional(),
  buyScoreCoverShortThreshold: z.number().min(0).max(100).optional(),
});

export type SettingsUpdate = z.infer<typeof settingsUpdateSchema>;
