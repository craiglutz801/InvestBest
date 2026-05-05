import type { StrategySpec } from "@/lib/strategy/types";

/** Observable metrics used by composite score & promotion gate (trial + future). */
export type TrialMetrics = {
  totalReturnPct: number;
  sharpeRatio: number;
  maxDrawdown: number;
  /** 0–1 scale, annualized turnover proxy */
  turnover: number;
  /** 0–1 concentration proxy (Herfindahl-style placeholder in trial) */
  concentration: number;
};

export type VariantProposal = {
  name: string;
  hypothesis: string;
  mutationType: "threshold" | "weights" | "risk" | "segment_caps" | "mixed";
  spec: StrategySpec;
};

export type ScoredVariant = {
  proposal: VariantProposal;
  metrics: TrialMetrics;
  compositeScore: number;
  normalized: TrialMetrics;
};

export type TrialRunResult = {
  baseline: StrategySpec;
  baselineMetrics: TrialMetrics;
  baselineComposite: number;
  variants: ScoredVariant[];
  promotion: {
    candidateName: string | null;
    approved: boolean;
    reason: string;
  };
  criticNotes: string[];
  narratorSummary: string;
  dataSource: "portfolio_snapshots" | "synthetic_demo";
  /** When true, challenger metrics use a heuristic sensitivity model, not a full replay. */
  evaluationDisclaimer: string;
};
