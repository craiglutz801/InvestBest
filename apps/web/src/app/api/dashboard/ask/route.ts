import { z } from "zod";
import { jsonError, jsonOk } from "@/lib/api/http";
import { prisma } from "@/lib/db";
import { toNum } from "@/lib/portfolio/math";
import { buildDashboardPayload } from "@/lib/server/dashboardPayload";
import {
  dashboardPayloadToQaContext,
  strategySnapshotToContext,
  type StrategySnapshot,
} from "@/lib/server/portfolioQaContext";
import { requireDefaultUser } from "@/lib/server/defaultUser";

const bodySchema = z.object({
  question: z.string().min(3).max(4000).trim(),
});

const SYSTEM = `You are a concise portfolio analyst for InvestBest, a **paper trading** simulation (not real money, not a broker).
The user message includes a block of structured facts extracted from their dashboard and a Strategy section describing the current buy/sell rules and thresholds. Answer their question using **only** those facts and reasonable inferences (e.g. comparing winners vs losers). If the facts are insufficient, say what is missing.

Rules:
- Use plain language; short paragraphs or bullets.
- Do not invent trades, symbols, or numbers not implied by the data.
- This is educational commentary, not personalized financial, tax, or legal advice. Say so briefly if giving loss/gain interpretation.
- Prefer actionable *observations* tied to the data (e.g. "largest drag is X") over generic investing tips.
- You may also answer questions about the current buy/sell strategy — thresholds, stop-loss / take-profit, cash reserve, cooldown, and which rules block or trigger trades — using the facts in the Strategy section. Quote the user's actual threshold numbers rather than generic ranges.`;

export async function POST(req: Request) {
  try {
    const key = process.env.OPENAI_API_KEY;
    if (!key) {
      return jsonError(
        "OPENAI_API_KEY is not set. Add it to apps/web/.env to enable portfolio Q&A (ChatGPT-style answers).",
        503,
      );
    }

    const json = await req.json().catch(() => null);
    const parsed = bodySchema.safeParse(json);
    if (!parsed.success) {
      return jsonError(parsed.error.flatten().formErrors.join("; ") || "Invalid body", 400);
    }

    const user = await requireDefaultUser();
    const [payload, settings] = await Promise.all([
      buildDashboardPayload(user.id),
      prisma.appSettings.findUnique({ where: { userId: user.id } }),
    ]);
    const dashboardContext = dashboardPayloadToQaContext(payload);

    let strategyContext = "";
    if (settings) {
      const snap: StrategySnapshot = {
        buyScoreThreshold: toNum(settings.buyScoreThreshold),
        sellRiskThreshold: toNum(settings.sellRiskThreshold),
        minConfidence: toNum(settings.minConfidence),
        stopLossPct: toNum(settings.stopLossPct),
        takeProfitPct: toNum(settings.takeProfitPct),
        cashReservePct: toNum(settings.cashReservePct),
        maxPositionPct: toNum(settings.maxPositionPct),
        maxNewPositionsPerRun: settings.maxNewPositionsPerRun,
        cooldownHours: settings.cooldownHours,
        shortingEnabled: settings.shortingEnabled,
      };
      strategyContext = `\n\n${strategySnapshotToContext(snap)}`;
    }
    const context = `${dashboardContext}${strategyContext}`;

    const model =
      process.env.INVESTBEST_OPENAI_MODEL?.trim() ||
      process.env.OPENAI_MODEL?.trim() ||
      "gpt-4o-mini";

    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model,
        temperature: 0.4,
        max_tokens: 1200,
        messages: [
          { role: "system", content: SYSTEM },
          {
            role: "user",
            content: `${context}\n\n---\n\n## User question\n\n${parsed.data.question}`,
          },
        ],
      }),
    });

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      return jsonError(`OpenAI API error (${res.status}): ${errText.slice(0, 200)}`, 502);
    }

    const data = (await res.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    const answer = data.choices?.[0]?.message?.content?.trim();
    if (!answer) {
      return jsonError("Empty response from model.", 502);
    }

    return jsonOk({ answer, model });
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Server error", 500);
  }
}
