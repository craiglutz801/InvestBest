import type { StrategySpec } from "./types";

/** Default baseline aligned with `InvestBest_Karpathy_Loop_Addendum.md` §9 example. */
export const DEFAULT_KARPATHY_BASELINE: StrategySpec = {
  name: "baseline_v1",
  buy_score_weights: {
    momentum_5d: 0.25,
    momentum_20d: 0.2,
    rsi_reversion: 0.1,
    volatility_penalty: -0.15,
    liquidity_score: 0.1,
    benchmark_regime: 0.2,
  },
  buy_threshold: 62,
  sell_risk_threshold: 70,
  stop_loss_pct: 0.08,
  take_profit_pct: 0.16,
  cash_reserve_pct: 0.1,
  max_position_pct: 0.08,
  max_new_positions_per_run: 3,
  cooldown_hours: 24,
  segment_caps: {
    defense: 0.25,
    energy: 0.25,
    agriculture: 0.2,
    metals: 0.2,
    broad_equities: 0.4,
  },
  evaluation_meta: {
    versionTag: "baseline_v1",
    notes: "Shipped default for Karpathy trial loop — not wired to live hourly agent yet.",
  },
};
