"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

export function RunControls() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function run(endpoint: string, successMessage: string) {
    startTransition(async () => {
      setMessage(null);

      const response = await fetch(endpoint, { method: "POST" });
      const payload = (await response.json()) as { ok: boolean; error?: string };

      if (!response.ok || !payload.ok) {
        setMessage(payload.error ?? "Something went wrong.");
        return;
      }

      setMessage(successMessage);
      router.refresh();
    });
  }

  return (
    <div className="controls">
      <button
        type="button"
        className="button button-primary"
        disabled={isPending}
        onClick={() => run("/api/runs/execute", "Manual simulation completed.")}
      >
        {isPending ? "Running..." : "Run $100k simulation"}
      </button>
      <button
        type="button"
        className="button button-secondary"
        disabled={isPending}
        onClick={() => run("/api/portfolio/reset", "Paper portfolio reset to $100,000.")}
      >
        Reset portfolio
      </button>
      <p className="control-help">
        Manual only for now. Each run fetches fresh market data, re-scores the universe, and rebalances the paper book.
      </p>
      {message ? <p className="control-message">{message}</p> : null}
    </div>
  );
}
