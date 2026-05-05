import { strategySpecSchema } from "@/lib/strategy/schema";
import { DEFAULT_KARPATHY_BASELINE } from "@/lib/strategy/defaultStrategy";
import type { StrategySpec } from "@/lib/strategy/types";
import type { VariantProposal } from "@/lib/research/types";

const SYSTEM = `You are the Research Planner agent in InvestBest's Karpathy improvement loop.
You ONLY propose changes to the JSON strategy spec fields provided.
You must NOT output code, must NOT mention live trading, must NOT bypass risk guardrails.
Output valid JSON: { "variants": [ { "name": string, "hypothesis": string, "mutationType": "threshold"|"weights"|"risk"|"segment_caps"|"mixed", "spec": StrategySpec } ] }
Provide 1 to 3 variants. Each spec must include all required keys from the baseline structure.
Keep mutations small and single-purpose when possible.`;

/**
 * Optional OpenAI call — returns empty array on failure so callers fall back to deterministic variants.
 */
export async function llmProposeVariants(baseline: StrategySpec): Promise<VariantProposal[]> {
  const key = process.env.OPENAI_API_KEY;
  if (!key) return [];

  try {
    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: process.env.INVESTBEST_KARPATHY_MODEL ?? "gpt-4o-mini",
        temperature: 0.3,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: SYSTEM },
          {
            role: "user",
            content: `Baseline strategy JSON:\n${JSON.stringify(baseline, null, 2)}\n\nPropose improved variants.`,
          },
        ],
      }),
    });

    if (!res.ok) return [];

    const data = (await res.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    const raw = data.choices?.[0]?.message?.content;
    if (!raw) return [];

    const parsed = JSON.parse(raw) as { variants?: unknown[] };
    const out: VariantProposal[] = [];
    for (const v of parsed.variants ?? []) {
      const row = v as Record<string, unknown>;
      const spec = strategySpecSchema.safeParse(row.spec);
      if (!spec.success) continue;
      out.push({
        name: String(row.name ?? "variant"),
        hypothesis: String(row.hypothesis ?? ""),
        mutationType: (row.mutationType as VariantProposal["mutationType"]) ?? "mixed",
        spec: spec.data as StrategySpec,
      });
    }
    return out.slice(0, 5);
  } catch {
    return [];
  }
}

/** Smoke export for tests */
export function baselineForPlanner(): StrategySpec {
  return DEFAULT_KARPATHY_BASELINE;
}
