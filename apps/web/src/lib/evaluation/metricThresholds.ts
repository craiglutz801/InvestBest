/** Conservative defaults for the trial promotion gate (not production promotion). */
export const TRIAL_PROMOTION_THRESHOLDS = {
  /** Challenger composite must beat baseline by at least this margin (on normalized 0–1 scale). */
  minCompositeMargin: 0.015,
  /** Challenger max drawdown must not exceed baseline by more than this (absolute dd scale 0–1). */
  maxDrawdownWorsening: 0.03,
  /** Turnover must not increase more than this fraction of baseline turnover. */
  maxTurnoverIncreasePct: 0.35,
};
