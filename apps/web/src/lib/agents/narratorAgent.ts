import type { ScoredVariant } from "@/lib/research/types";
import type { PromotionResult } from "@/lib/promotion/trialPromotionGate";

export function runNarratorAgent(input: {
  baselineName: string;
  baselineComposite: number;
  ranked: ScoredVariant[];
  promotion: PromotionResult;
  plannerSource: "llm" | "deterministic";
}): string {
  const top = input.ranked[0];
  const lines = [
    `Karpathy trial loop — planner: ${input.plannerSource}.`,
    `Baseline "${input.baselineName}" composite (normalized group): ${input.baselineComposite.toFixed(4)}.`,
  ];
  if (top) {
    lines.push(
      `Top challenger "${top.proposal.name}" — composite ${top.compositeScore.toFixed(4)} — ${top.proposal.hypothesis}`,
    );
  }
  lines.push(`Promotion gate: ${input.promotion.approved ? "APPROVED (trial only)" : "REJECTED"} — ${input.promotion.reason}`);
  return lines.join("\n");
}
