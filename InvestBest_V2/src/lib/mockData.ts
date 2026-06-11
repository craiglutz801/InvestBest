import type {
  CandidateIdea,
  Experiment,
  StrategyModel,
  SummaryMetric,
  SystemAlert,
} from "@/lib/types";

export const summaryMetrics: SummaryMetric[] = [
  { label: "Mode", value: "Paper only", tone: "neutral" },
  { label: "Active model", value: "regression_v1_shadow", change: "shadowing V1", tone: "neutral" },
  { label: "Approved models", value: "3", change: "1 incubating", tone: "positive" },
  { label: "Rejected ideas", value: "91%", change: "healthy filter rate", tone: "positive" },
];

export const strategyModels: StrategyModel[] = [
  {
    id: "m1",
    name: "rules_v1_baseline",
    family: "rules",
    stage: "active",
    oosSharpe: 0.62,
    meanIc: 0.01,
    alphaTstat: 0.9,
    maxDrawdownPct: 14.8,
    profitFactor: 1.04,
    notes: "Stable fallback, but weak true edge."
  },
  {
    id: "m2",
    name: "alpha_v1_ranker",
    family: "alpha",
    stage: "active",
    oosSharpe: 0.74,
    meanIc: 0.02,
    alphaTstat: 1.4,
    maxDrawdownPct: 13.1,
    profitFactor: 1.08,
    notes: "Better ranking than rules, but still heuristic."
  },
  {
    id: "m3",
    name: "regression_v1_shadow",
    family: "regression",
    stage: "incubating",
    oosSharpe: 0.96,
    meanIc: 0.04,
    alphaTstat: 2.2,
    maxDrawdownPct: 10.4,
    profitFactor: 1.21,
    notes: "First V2 lane; promising but still proving itself."
  },
  {
    id: "m4",
    name: "commodity_carry_proto",
    family: "factor",
    stage: "rejected",
    oosSharpe: 0.22,
    meanIc: 0.0,
    alphaTstat: 0.4,
    maxDrawdownPct: 19.7,
    profitFactor: 0.93,
    notes: "Failed holdout and overfit smell tests."
  }
];

export const experiments: Experiment[] = [
  {
    id: "e1",
    title: "Regression baseline with 5d forward return",
    hypothesis: "A simple linear baseline can outperform static weighted heuristics on ranking quality.",
    status: "approved",
    holdoutSharpe: 0.96,
    walkForwardPasses: "3 / 4",
    icSummary: "mean IC 0.041",
    bonferroniBar: "cleared"
  },
  {
    id: "e2",
    title: "Leadership-only offensive universe",
    hypothesis: "A narrower offensive universe improves signal density in bullish tapes.",
    status: "running",
    holdoutSharpe: 0.0,
    walkForwardPasses: "pending",
    icSummary: "pending",
    bonferroniBar: "pending"
  },
  {
    id: "e3",
    title: "Pre-earnings exclusion gate",
    hypothesis: "Avoiding names into earnings reduces adverse event noise without killing alpha.",
    status: "queued",
    holdoutSharpe: 0.0,
    walkForwardPasses: "pending",
    icSummary: "pending",
    bonferroniBar: "pending"
  }
];

export const candidateIdeas: CandidateIdea[] = [
  {
    id: "c1",
    symbol: "SNOW",
    family: "momentum",
    stage: "approved",
    thesis: "Leadership continuation after a controlled pullback with improving forward return rank.",
    verdict: "Passed compile, OOS, and walk-forward checks."
  },
  {
    id: "c2",
    symbol: "IEF",
    family: "macro",
    stage: "rejected",
    thesis: "Defensive macro hedge candidate competing with growth longs.",
    verdict: "Rejected in bullish regime due to inferior offensive opportunity set."
  },
  {
    id: "c3",
    symbol: "PLTR",
    family: "event",
    stage: "tested",
    thesis: "Earnings revision plus momentum continuation test case.",
    verdict: "Awaiting holdout and IC review."
  }
];

export const alerts: SystemAlert[] = [
  {
    id: "a1",
    severity: "info",
    title: "Paper mode hard lock",
    detail: "Execution remains paper-pinned in V2 until manual unlock architecture exists.",
    timestamp: "2026-06-10 09:30"
  },
  {
    id: "a2",
    severity: "warning",
    title: "Shadow model divergence",
    detail: "regression_v1_shadow selected different longs than alpha_v1 in 42% of recent runs.",
    timestamp: "2026-06-10 11:05"
  },
  {
    id: "a3",
    severity: "critical",
    title: "No live promotion yet",
    detail: "No V2 model should become primary until walk-forward, HAC, and decay checks are complete.",
    timestamp: "2026-06-10 12:15"
  }
];
