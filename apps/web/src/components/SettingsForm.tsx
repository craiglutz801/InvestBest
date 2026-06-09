"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { AgentRunMonitor } from "@/components/agent-run/AgentRunMonitor";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type SettingsFormValues = {
  startingCash: number;
  maxPositionPct: number;
  maxNewPositionsPerRun: number;
  targetHoldings: number;
  stopLossPct: number;
  takeProfitPct: number;
  minConfidence: number;
  cashReservePct: number;
  runFrequencyMinutes: number;
  newsEnabled: boolean;
  shortingEnabled: boolean;
  defaultSlippagePct: number;
  strategyMode: "rules_v1" | "alpha_v1" | "regression_v1";
  buyScoreThreshold: number;
  sellRiskThreshold: number;
  cooldownHours: number;
  staleQuoteAllowSells: boolean;
  paperStartDate: string;
  paperEndDate: string;
  buyScoreMargin: number;
  confidenceMarginForBuy: number;
  requireMomentumForBuy: boolean;
  maxBuyAnnualVol: number;
  bearScoreThreshold: number;
  confidenceMarginForShort: number;
  shortOnlyInBearRegime: boolean;
  maxShortPositionsPerRun: number;
  buyScoreCoverShortThreshold: number;
};

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  /** Short explanation of what this controls and how the agent uses it. */
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <label className="grid gap-1.5 text-sm">
      <span className="font-medium text-foreground">{label}</span>
      <p className="text-xs leading-relaxed text-muted-foreground">{hint}</p>
      {children}
    </label>
  );
}

const RESET_STARTING_CASH = 100_000;

export function SettingsForm({ initial }: { initial: SettingsFormValues }) {
  const router = useRouter();
  const [v, setV] = useState(initial);
  const [msg, setMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setMsg(null);
    try {
      const body: Record<string, unknown> = { ...v };
      body.paperStartDate = v.paperStartDate ? new Date(v.paperStartDate).toISOString() : null;
      body.paperEndDate = v.paperEndDate ? new Date(v.paperEndDate).toISOString() : null;
      const res = await fetch("/api/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      setMsg("Saved.");
      router.refresh();
    } catch (err) {
      setMsg(err instanceof Error ? err.message : "Save failed");
    } finally {
      setLoading(false);
    }
  }

  const inp =
    "w-full rounded-md border border-border bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30";

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Paper trading</CardTitle>
          <p className="text-sm leading-relaxed text-muted-foreground">
            These values drive the hourly paper-trading agent (manual &quot;Run agent now&quot; and scheduled runs).
            V1 engines stay available, and V2 can be introduced incrementally through new strategy modes without
            disturbing the existing paper workflow.
          </p>
        </CardHeader>
        <CardContent>
          <form onSubmit={save} className="grid gap-6 sm:grid-cols-2">
            <Field
              label="Strategy mode"
              hint="Choose between the original rules engine, the alpha foundation ranker, and the new InvestBest v2 regression baseline. Regression v1 is the experimental supervised-model lane and is intended to coexist with V1 while we train and validate it."
            >
              <select
                className={inp}
                value={v.strategyMode}
                onChange={(e) =>
                  setV({ ...v, strategyMode: e.target.value as SettingsFormValues["strategyMode"] })
                }
              >
                <option value="rules_v1">Rules v1</option>
                <option value="alpha_v1">Alpha foundation v1</option>
                <option value="regression_v1">Regression v1 (InvestBest v2)</option>
              </select>
            </Field>
            <Field
              label="Starting cash ($)"
              hint="Notional bankroll when there is no trade history yet (e.g. after reset). Once trades exist, live cash comes from the latest trade balance; this field still sets the baseline for return % and benchmarks."
            >
              <input
                type="number"
                className={inp}
                value={v.startingCash}
                onChange={(e) => setV({ ...v, startingCash: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Max position %"
              hint="Upper cap on a single new buy: position size won’t exceed this percent of total portfolio value at execution time (after recent sells, before new buys in that run)."
            >
              <input
                type="number"
                step="0.1"
                className={inp}
                value={v.maxPositionPct}
                onChange={(e) => setV({ ...v, maxPositionPct: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Max new positions / run"
              hint="Maximum number of new buys the agent may place in one run. It still respects target holdings and available cash."
            >
              <input
                type="number"
                className={inp}
                value={v.maxNewPositionsPerRun}
                onChange={(e) => setV({ ...v, maxNewPositionsPerRun: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Target holdings"
              hint="Soft cap on how many different symbols you want open at once. The agent won’t open new positions if you already hold this many (unless something sells first)."
            >
              <input
                type="number"
                className={inp}
                value={v.targetHoldings}
                onChange={(e) => setV({ ...v, targetHoldings: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Stop loss %"
              hint="Sell a holding if price falls this far below your average cost (unrealized loss). Example: 8 means exit near −8% from cost."
            >
              <input
                type="number"
                step="0.1"
                className={inp}
                value={v.stopLossPct}
                onChange={(e) => setV({ ...v, stopLossPct: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Take profit %"
              hint="Sell a holding if price rises this far above your average cost (unrealized gain). Example: 15 means take profit near +15% from cost."
            >
              <input
                type="number"
                step="0.1"
                className={inp}
                value={v.takeProfitPct}
                onChange={(e) => setV({ ...v, takeProfitPct: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Min confidence (0–100)"
              hint="The rules engine assigns a confidence score (mostly from volatility and data quality). A new buy only happens if that score is at least this value. Higher = stricter, fewer buys."
            >
              <input
                type="number"
                className={inp}
                value={v.minConfidence}
                onChange={(e) => setV({ ...v, minConfidence: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Cash reserve %"
              hint="Fraction of total portfolio value the engine tries to keep in cash. It won’t deploy cash for new buys if doing so would leave you below this buffer (unless rules allow a small trade window)."
            >
              <input
                type="number"
                step="0.1"
                className={inp}
                value={v.cashReservePct}
                onChange={(e) => setV({ ...v, cashReservePct: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Run frequency (minutes)"
              hint="Saved as a scheduling hint (e.g. align with Vercel Cron). The in-app agent does not read this value today—runs are triggered manually or by your deployed cron route."
            >
              <input
                type="number"
                className={inp}
                value={v.runFrequencyMinutes}
                onChange={(e) => setV({ ...v, runFrequencyMinutes: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Default slippage %"
              hint="Simulated execution cost: buys fill slightly above the quote, sells slightly below, by this percentage. Models worse fills than the mid price."
            >
              <input
                type="number"
                step="0.01"
                className={inp}
                value={v.defaultSlippagePct}
                onChange={(e) => setV({ ...v, defaultSlippagePct: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Buy score margin (conviction)"
              hint="Added on top of Buy score threshold for new longs only. Example: threshold 45 + margin 8 ⇒ effective 53. Use a positive margin when you want fewer, higher-conviction buys."
            >
              <input
                type="number"
                step="0.5"
                className={inp}
                value={v.buyScoreMargin}
                onChange={(e) => setV({ ...v, buyScoreMargin: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Extra confidence for longs"
              hint="Raises the minimum confidence score required for new buys only (not shorts). Stacks with Min confidence."
            >
              <input
                type="number"
                step="0.5"
                className={inp}
                value={v.confidenceMarginForBuy}
                onChange={(e) => setV({ ...v, confidenceMarginForBuy: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Require positive momentum for longs"
              hint="When enabled, the agent only buys if both 5d and 20d returns are positive—extra trend confirmation."
            >
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={v.requireMomentumForBuy}
                  onChange={(e) => setV({ ...v, requireMomentumForBuy: e.target.checked })}
                />
                <span className="text-sm">5d and 20d must both be &gt; 0</span>
              </label>
            </Field>
            <Field
              label="Max annual vol for long buys"
              hint="Caps how volatile a name can be to qualify for a long (same vol scale as the rules engine). Lower = calmer names only. Default 0.6 matches the historical built-in cap."
            >
              <input
                type="number"
                step="0.01"
                className={inp}
                value={v.maxBuyAnnualVol}
                onChange={(e) => setV({ ...v, maxBuyAnnualVol: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Buy score threshold"
              hint="Minimum rules-based buy score (0–100) for a symbol to be eligible to buy. Score blends momentum, trend vs moving averages, RSI, volume, and volatility. Higher = only stronger setups. Effective threshold also adds Buy score margin above."
            >
              <input
                type="number"
                step="0.1"
                className={inp}
                value={v.buyScoreThreshold}
                onChange={(e) => setV({ ...v, buyScoreThreshold: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Sell risk threshold"
              hint="If the rules sell-risk score for a holding reaches at least this (0–100), the agent may sell (in addition to stop-loss, take-profit, and a separate momentum/RSI exit rule)."
            >
              <input
                type="number"
                step="0.1"
                className={inp}
                value={v.sellRiskThreshold}
                onChange={(e) => setV({ ...v, sellRiskThreshold: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Cooldown (hours) after sell"
              hint="After you sell a symbol, the agent won’t buy that same symbol again until this many hours have passed—reduces churn in and out of the same name."
            >
              <input
                type="number"
                className={inp}
                value={v.cooldownHours}
                onChange={(e) => setV({ ...v, cooldownHours: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Allow sells when quote is stale"
              hint="If the live quote fails for a holding, the agent blocks sells that run (STALE_DATA_HOLD) so we don’t act on bad prices. Enable this only if you accept selling using the last ingested price."
            >
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={v.staleQuoteAllowSells}
                  onChange={(e) => setV({ ...v, staleQuoteAllowSells: e.target.checked })}
                />
                <span className="text-sm">Allow sells without a fresh quote</span>
              </label>
            </Field>
            <Field
              label="Paper start (local datetime)"
              hint="Optional window start for paper trading reports or future features. The current hourly agent does not block runs outside this range—it’s stored for your records."
            >
              <input
                type="datetime-local"
                className={inp}
                value={v.paperStartDate}
                onChange={(e) => setV({ ...v, paperStartDate: e.target.value })}
              />
            </Field>
            <Field
              label="Paper end (local datetime)"
              hint="Optional window end, paired with paper start. Not enforced by the MVP engine today."
            >
              <input
                type="datetime-local"
                className={inp}
                value={v.paperEndDate}
                onChange={(e) => setV({ ...v, paperEndDate: e.target.value })}
              />
            </Field>
            <Field
              label="Bear score threshold (shorts)"
              hint="Minimum bear conviction score (0–100) to open a short when shorting is enabled. Default is strict (82)."
            >
              <input
                type="number"
                step="0.5"
                className={inp}
                value={v.bearScoreThreshold}
                onChange={(e) => setV({ ...v, bearScoreThreshold: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Extra confidence for shorts"
              hint="Minimum confidence for a short = Min confidence + this value. Keeps shorts rarer than longs when set positive."
            >
              <input
                type="number"
                step="0.5"
                className={inp}
                value={v.confidenceMarginForShort}
                onChange={(e) => setV({ ...v, confidenceMarginForShort: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Short only in bear regime"
              hint="Uses the same SPY trend/regime signal as buys. When enabled, new shorts are allowed only when the assessment is bearish."
            >
              <label className="flex cursor-pointer items-center gap-2">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-border"
                  checked={v.shortOnlyInBearRegime}
                  onChange={(e) => setV({ ...v, shortOnlyInBearRegime: e.target.checked })}
                />
                <span className="text-sm">Require bearish regime</span>
              </label>
            </Field>
            <Field
              label="Max new shorts / run"
              hint="Caps simultaneous new short opens per agent run (separate from Max new positions / run for longs)."
            >
              <input
                type="number"
                className={inp}
                value={v.maxShortPositionsPerRun}
                onChange={(e) => setV({ ...v, maxShortPositionsPerRun: Number(e.target.value) })}
              />
            </Field>
            <Field
              label="Buy score to cover shorts"
              hint="If the rules buy score on a shorted name rises to at least this level, the agent may buy to cover (recovery / sentiment flip)."
            >
              <input
                type="number"
                step="0.5"
                className={inp}
                value={v.buyScoreCoverShortThreshold}
                onChange={(e) => setV({ ...v, buyScoreCoverShortThreshold: Number(e.target.value) })}
              />
            </Field>
            <div className="grid gap-4 sm:col-span-2 sm:grid-cols-2">
              <div className="rounded-md border border-border bg-muted/30 p-3">
                <label className="flex cursor-pointer items-start gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={v.newsEnabled}
                    onChange={(e) => setV({ ...v, newsEnabled: e.target.checked })}
                  />
                  <span>
                    <span className="font-medium text-foreground">News enrichment</span>
                    <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                      Stored for future use. The current rules-based scorer does not ingest headlines; toggling this
                      does not change buy/sell math yet.
                    </span>
                  </span>
                </label>
              </div>
              <div className="rounded-md border border-border bg-muted/30 p-3">
                <label className="flex cursor-pointer items-start gap-3 text-sm">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={v.shortingEnabled}
                    onChange={(e) => setV({ ...v, shortingEnabled: e.target.checked })}
                  />
                  <span>
                    <span className="font-medium text-foreground">Shorting</span>
                    <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                      When enabled, the hourly agent may open shorts (tracked as SHORT trades, marked-to-market like longs)
                      under strict bear-score, confidence, liquidity, and optional SPY bear-regime gates—then cover with
                      COVER trades. Requires separate tuning from longs.
                    </span>
                  </span>
                </label>
              </div>
            </div>
            <div className="sm:col-span-2 flex flex-wrap items-center gap-3">
              <Button type="submit" disabled={loading}>
                {loading ? "Saving…" : "Save settings"}
              </Button>
              {msg ? <span className="text-sm text-muted-foreground">{msg}</span> : null}
            </div>
          </form>
        </CardContent>
      </Card>

      <AgentRunMonitor
        onPaperReset={() => setV((prev) => ({ ...prev, startingCash: RESET_STARTING_CASH }))}
      />
    </div>
  );
}
