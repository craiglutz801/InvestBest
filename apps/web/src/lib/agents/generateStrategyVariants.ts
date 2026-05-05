import { strategySpecSchema } from "@/lib/strategy/schema";
import type { StrategySpec } from "@/lib/strategy/types";
import type { VariantProposal } from "@/lib/research/types";
import { llmProposeVariants } from "./researchPlanner";

function clone(s: StrategySpec): StrategySpec {
  return JSON.parse(JSON.stringify(s)) as StrategySpec;
}

function validate(spec: StrategySpec): StrategySpec {
  return strategySpecSchema.parse(spec) as StrategySpec;
}

/** Deterministic fallback variants — small, auditable mutations (addendum §10). */
export function generateDeterministicVariants(baseline: StrategySpec): VariantProposal[] {
  const v1 = clone(baseline);
  v1.name = `${baseline.name}_higher_buy_bar`;
  v1.buy_threshold = Math.min(95, baseline.buy_threshold + 4);
  v1.evaluation_meta = { ...baseline.evaluation_meta, notes: "Raise buy bar — fewer names, lower turnover risk." };

  const v2 = clone(baseline);
  v2.name = `${baseline.name}_tighter_risk`;
  v2.sell_risk_threshold = Math.max(40, baseline.sell_risk_threshold - 5);
  v2.stop_loss_pct = Math.min(0.2, baseline.stop_loss_pct + 0.01);
  v2.evaluation_meta = { ...baseline.evaluation_meta, notes: "Earlier de-risking + slightly wider stop (trial)." };

  const v3 = clone(baseline);
  v3.name = `${baseline.name}_energy_cap`;
  v3.segment_caps = { ...baseline.segment_caps, energy: Math.max(0.1, (baseline.segment_caps.energy ?? 0.25) - 0.1) };
  v3.evaluation_meta = { ...baseline.evaluation_meta, notes: "Reduce energy sleeve concentration." };

  return [
    {
      name: v1.name,
      hypothesis: "Raising the buy score threshold reduces churn and may improve risk-adjusted outcomes.",
      mutationType: "threshold",
      spec: validate(v1),
    },
    {
      name: v2.name,
      hypothesis: "Lowering sell-risk threshold exits weak names sooner; slightly wider stop avoids noise exits.",
      mutationType: "mixed",
      spec: validate(v2),
    },
    {
      name: v3.name,
      hypothesis: "Capping energy exposure reduces sector concentration risk.",
      mutationType: "segment_caps",
      spec: validate(v3),
    },
  ];
}

export async function generateStrategyVariants(
  baseline: StrategySpec,
  options?: { useLlm?: boolean },
): Promise<{ variants: VariantProposal[]; plannerSource: "llm" | "deterministic" }> {
  if (options?.useLlm && process.env.OPENAI_API_KEY) {
    const llm = await llmProposeVariants(baseline);
    if (llm.length > 0) {
      return { variants: llm.map((x) => ({ ...x, spec: validate(x.spec) })), plannerSource: "llm" };
    }
  }
  return { variants: generateDeterministicVariants(baseline), plannerSource: "deterministic" };
}
