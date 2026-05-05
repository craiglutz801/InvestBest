import { z } from "zod";

const weights = z.record(z.string(), z.number());

export const strategySpecSchema = z.object({
  name: z.string().min(1).max(120),
  buy_score_weights: weights,
  buy_threshold: z.number().min(0).max(100),
  sell_risk_threshold: z.number().min(0).max(100),
  stop_loss_pct: z.number().min(0).max(1),
  take_profit_pct: z.number().min(0).max(2),
  cash_reserve_pct: z.number().min(0).max(1),
  max_position_pct: z.number().min(0).max(1),
  max_new_positions_per_run: z.number().int().min(0).max(50),
  cooldown_hours: z.number().int().min(0).max(168 * 4),
  segment_caps: z.record(z.string(), z.number().min(0).max(1)),
  evaluation_meta: z
    .object({
      versionTag: z.string().optional(),
      notes: z.string().optional(),
    })
    .optional(),
});

export type StrategySpecInput = z.input<typeof strategySpecSchema>;
export type StrategySpecOutput = z.output<typeof strategySpecSchema>;
