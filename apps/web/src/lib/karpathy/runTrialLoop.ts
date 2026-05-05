import { runCriticAgent } from "@/lib/agents/criticAgent";
import { runNarratorAgent } from "@/lib/agents/narratorAgent";
import { generateStrategyVariants } from "@/lib/agents/generateStrategyVariants";
import { compositeScore, normalizeMetricsGroup } from "@/lib/evaluation/compositeScore";
import {
  DEMO_BASELINE_METRICS,
  metricsFromEquitySnapshots,
} from "@/lib/evaluation/trialMetricsFromEquity";
import { applyTrialSensitivity } from "@/lib/evaluation/trialSensitivity";
import { runTrialPromotionGate } from "@/lib/promotion/trialPromotionGate";
import type { ScoredVariant, TrialMetrics, TrialRunResult } from "@/lib/research/types";
import { DEFAULT_KARPATHY_BASELINE } from "@/lib/strategy/defaultStrategy";
import type { StrategySpec } from "@/lib/strategy/types";

export type RunTrialLoopInput = {
  /** When set, load equity from DB (read-only) for baseline metrics. */
  portfolioSnapshots?: { totalValue: { toString(): string } }[];
  baseline?: StrategySpec;
  useLlm?: boolean;
};

const DISCLAIMER =
  "Trial evaluation uses (1) real snapshot-derived metrics when available, plus (2) a bounded sensitivity model for challengers — not a full historical replay. Promotion here does not change live settings or the hourly agent.";

export async function runKarpathyTrialLoop(input: RunTrialLoopInput = {}): Promise<TrialRunResult> {
  const baseline = input.baseline ?? DEFAULT_KARPATHY_BASELINE;

  let baselineMetrics: TrialMetrics;
  let dataSource: "portfolio_snapshots" | "synthetic_demo";

  if (input.portfolioSnapshots && input.portfolioSnapshots.length >= 2) {
    baselineMetrics = metricsFromEquitySnapshots(input.portfolioSnapshots);
    dataSource = "portfolio_snapshots";
  } else {
    baselineMetrics = DEMO_BASELINE_METRICS;
    dataSource = "synthetic_demo";
  }

  const { variants: proposals, plannerSource } = await generateStrategyVariants(baseline, {
    useLlm: input.useLlm,
  });

  const rawRows: TrialMetrics[] = [
    baselineMetrics,
    ...proposals.map((p) => applyTrialSensitivity(baselineMetrics, baseline, p.spec)),
  ];

  const normalized = normalizeMetricsGroup(rawRows);
  const baselineNorm = normalized[0]!;
  const baselineComposite = compositeScore(baselineNorm);

  const scored: ScoredVariant[] = proposals.map((p, i) => {
    const norm = normalized[i + 1]!;
    return {
      proposal: p,
      metrics: rawRows[i + 1]!,
      compositeScore: compositeScore(norm),
      normalized: norm,
    };
  });

  const promotion = runTrialPromotionGate(baselineComposite, baselineMetrics, scored);
  const ranked = [...scored].sort((a, b) => b.compositeScore - a.compositeScore);
  const best = ranked[0];

  const criticNotes =
    best && promotion.candidateName
      ? runCriticAgent({
          baseline: baselineMetrics,
          candidate: best.metrics,
          candidateName: best.proposal.name,
        })
      : ["No challenger scored."];

  const narratorSummary = runNarratorAgent({
    baselineName: baseline.name,
    baselineComposite,
    ranked,
    promotion,
    plannerSource,
  });

  return {
    baseline,
    baselineMetrics,
    baselineComposite,
    variants: scored,
    promotion: {
      candidateName: promotion.candidateName,
      approved: promotion.approved,
      reason: promotion.reason,
    },
    criticNotes,
    narratorSummary,
    dataSource,
    evaluationDisclaimer: DISCLAIMER,
  };
}
