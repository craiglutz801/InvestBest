export type ModelStage =
  | "candidate"
  | "backtesting"
  | "incubating"
  | "active"
  | "decayed"
  | "rejected";

export type ModelFamily = "rules" | "alpha" | "regression" | "factor";

export type StrategyModel = {
  id: string;
  name: string;
  family: ModelFamily;
  stage: ModelStage;
  oosSharpe: number;
  meanIc: number;
  alphaTstat: number;
  maxDrawdownPct: number;
  profitFactor: number;
  notes: string;
};

export type Experiment = {
  id: string;
  title: string;
  hypothesis: string;
  status: "queued" | "running" | "approved" | "rejected";
  holdoutSharpe: number;
  walkForwardPasses: string;
  icSummary: string;
  bonferroniBar: string;
};

export type CandidateIdea = {
  id: string;
  symbol: string;
  family: string;
  stage: "found" | "compiled" | "tested" | "approved" | "rejected";
  thesis: string;
  verdict: string;
};

export type SystemAlert = {
  id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  detail: string;
  timestamp: string;
};

export type SummaryMetric = {
  label: string;
  value: string;
  change?: string;
  tone?: "positive" | "neutral" | "negative";
};
