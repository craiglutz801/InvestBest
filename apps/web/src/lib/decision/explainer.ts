import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";

type StructuredRun = {
  buysCount: number;
  sellsCount: number;
  buys: { ticker: string; score: number; conf: number }[];
  sells: { ticker: string; reason: string | null }[];
  blockedSample: { ticker: string; reason: string | null }[];
};

function fallbackSummary(s: StructuredRun): string {
  const parts = [
    `Hourly run completed: ${s.buysCount} buy(s), ${s.sellsCount} sell(s).`,
    s.buys.length ? `Opened or added: ${s.buys.map((b) => b.ticker).join(", ")}.` : "",
    s.sells.length ? `Reduced or closed: ${s.sells.map((x) => x.ticker).join(", ")}.` : "",
    "Narrative is template-only (set OPENAI_API_KEY for richer summaries). Rules-based model; not investment advice.",
  ];
  return parts.filter(Boolean).join(" ");
}

async function openAiSummarize(data: StructuredRun): Promise<string | null> {
  const key = process.env.OPENAI_API_KEY;
  if (!key) return null;

  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({
      model: process.env.OPENAI_MODEL ?? "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content:
            "Summarize paper-trading decisions for operators. Use ONLY the JSON facts; do not invent prices or signals. No financial advice; avoid certainty wording. 2–4 sentences.",
        },
        { role: "user", content: JSON.stringify(data) },
      ],
      temperature: 0.2,
      max_tokens: 280,
    }),
  });

  if (!res.ok) return null;
  const json = (await res.json()) as { choices?: { message?: { content?: string } }[] };
  const text = json.choices?.[0]?.message?.content?.trim();
  return text ?? null;
}

/** Persist llmSummary on DecisionRun (OpenAI if configured, else deterministic text). */
export async function writeDecisionExplainerSummary(runId: string): Promise<void> {
  const run = await prisma.decisionRun.findUnique({
    where: { id: runId },
    include: {
      items: { include: { symbol: true }, take: 100 },
    },
  });
  if (!run) return;

  const buys = run.items.filter((i) => i.actionRecommendation === "buy");
  const sells = run.items.filter((i) => i.actionRecommendation === "sell");
  const blocked = run.items.filter((i) => i.blocked);

  const structured: StructuredRun = {
    buysCount: run.buysCount,
    sellsCount: run.sellsCount,
    buys: buys.map((i) => ({
      ticker: i.symbol.ticker,
      score: i.buyScore != null ? toNum(i.buyScore) : 0,
      conf: i.confidenceScore != null ? toNum(i.confidenceScore) : 0,
    })),
    sells: sells.map((i) => ({
      ticker: i.symbol.ticker,
      reason: i.rationaleShort ?? i.blockedReason,
    })),
    blockedSample: blocked.slice(0, 8).map((i) => ({
      ticker: i.symbol.ticker,
      reason: i.blockedReason ?? i.rationaleShort,
    })),
  };

  const ai = await openAiSummarize(structured);
  const summary = ai ?? fallbackSummary(structured);

  await prisma.decisionRun.update({
    where: { id: runId },
    data: { llmSummary: summary },
  });
}
