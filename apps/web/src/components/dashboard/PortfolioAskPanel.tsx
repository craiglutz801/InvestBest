"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function PortfolioAskPanel({ hasOpenAiKey }: { hasOpenAiKey: boolean }) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    const q = question.trim();
    if (q.length < 3) return;
    setLoading(true);
    setError(null);
    setAnswer(null);
    setModel(null);
    try {
      const res = await fetch("/api/dashboard/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = (await res.json()) as { answer?: string; model?: string; error?: string };
      if (!res.ok) {
        setError(data.error ?? `Request failed (${res.status})`);
        return;
      }
      setAnswer(data.answer ?? "");
      setModel(data.model ?? null);
    } catch {
      setError("Network error — try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Ask about your portfolio</CardTitle>
        <p className="text-sm font-normal text-muted-foreground">
          Natural-language Q&amp;A over your current dashboard data (holdings, P&amp;L, recent trades, agent
          decisions) and the current buy/sell strategy.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasOpenAiKey ? (
          <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:text-amber-100">
            Portfolio Q&amp;A is disabled until you add <strong>OPENAI_API_KEY</strong> to{" "}
            <strong>apps/web/.env</strong> and restart the dev server.
          </p>
        ) : null}

        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="flex-1 text-sm font-medium text-foreground">
            Your question
            <textarea
              className={cn(
                "mt-1.5 flex min-h-[88px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm",
                "ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              )}
              placeholder={'e.g. "Why might I be down lately?", "What is working best?", or "What\u2019s my current strategy for when to buy and sell?"'}
              value={question}
              disabled={!hasOpenAiKey || loading}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  void submit();
                }
              }}
            />
          </label>
          <Button type="button" disabled={!hasOpenAiKey || loading || question.trim().length < 3} onClick={() => void submit()}>
            {loading ? "Thinking…" : "Ask"}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          <kbd className="rounded border border-border px-1">⌘</kbd> / <kbd className="rounded border border-border px-1">Ctrl</kbd>{" "}
          + <kbd className="rounded border border-border px-1">Enter</kbd> to submit.
        </p>

        {error ? (
          <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </p>
        ) : null}

        {answer ? (
          <div className="rounded-md border border-border bg-muted/20 p-4">
            <p className="text-xs text-muted-foreground">
              {model ? `Model: ${model} · ` : null}
              Not financial advice — paper simulation only.
            </p>
            <div className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-foreground">{answer}</div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
