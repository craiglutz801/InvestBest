/**
 * Declarative strategy spec for the Karpathy improvement loop (trial + future registry).
 * Mutations are bounded to these fields — agents must not edit arbitrary code.
 */

export type StrategySegmentCaps = Record<string, number>;

export type StrategyBuyScoreWeights = Record<string, number>;

export type StrategySpec = {
  name: string;
  buy_score_weights: StrategyBuyScoreWeights;
  buy_threshold: number;
  sell_risk_threshold: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  cash_reserve_pct: number;
  max_position_pct: number;
  max_new_positions_per_run: number;
  cooldown_hours: number;
  segment_caps: StrategySegmentCaps;
  /** Optional metadata for UI / audit (not used by trial heuristic). */
  evaluation_meta?: {
    versionTag?: string;
    notes?: string;
  };
};
