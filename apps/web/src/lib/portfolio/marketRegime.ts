/**
 * Lightweight market-regime classifier from a benchmark series (typically SPY).
 *
 * The agent already fetches SPY for benchmarking; we reuse the same bars to derive a
 * coarse "bullish / neutral / bearish" signal and use it as a *soft* filter on new buys.
 * No persistence, no schema changes — purely runtime.
 */

export type MarketRegime = "bullish" | "neutral" | "bearish";

export type MarketRegimeAssessment = {
  regime: MarketRegime;
  /** Last close used for the assessment. */
  lastClose: number;
  /** SMA(200) when computable, otherwise null. */
  sma200: number | null;
  /** SMA(50) when computable, otherwise null. */
  sma50: number | null;
  /** Distance from SMA(200) as a fraction (e.g., -0.04 = 4% below). */
  distSma200: number | null;
  /** Human-readable one-line summary suitable for run progress logs. */
  summary: string;
};

function sma(values: number[], window: number): number | null {
  if (values.length < window) return null;
  const slice = values.slice(-window);
  return slice.reduce((a, b) => a + b, 0) / window;
}

/**
 * Classify the current regime from a series of closes.
 *
 * Rules (coarse but well-tested in practice):
 *   - bullish  : last > SMA200 AND SMA50 > SMA200 (or SMA50 unavailable but last > SMA200)
 *   - bearish  : last < SMA200 AND SMA50 < SMA200 (or SMA50 unavailable but last < SMA200 by > 1%)
 *   - neutral  : everything else, including insufficient data (defaults to neutral, no filtering)
 */
export function assessMarketRegime(closes: number[]): MarketRegimeAssessment {
  const last = closes.length > 0 ? closes[closes.length - 1] : 0;
  const sma200 = sma(closes, 200);
  const sma50 = sma(closes, 50);
  const distSma200 = sma200 ? (last - sma200) / sma200 : null;

  let regime: MarketRegime = "neutral";
  if (sma200 != null) {
    const aboveLong = last > sma200;
    const belowLong = last < sma200;
    if (sma50 != null) {
      if (aboveLong && sma50 > sma200) regime = "bullish";
      else if (belowLong && sma50 < sma200) regime = "bearish";
    } else {
      if (aboveLong) regime = "bullish";
      else if (belowLong && distSma200 != null && distSma200 < -0.01) regime = "bearish";
    }
  }

  const distPct = distSma200 != null ? `${distSma200 >= 0 ? "+" : ""}${(distSma200 * 100).toFixed(1)}%` : "n/a";
  const summary =
    sma200 == null
      ? `Regime: neutral (insufficient SPY history for SMA200)`
      : `Regime: ${regime} · SPY ${last.toFixed(2)} vs SMA200 ${sma200.toFixed(2)} (${distPct})`;

  return { regime, lastClose: last, sma200, sma50, distSma200, summary };
}

export type RegimeFilterMode = "off" | "soft" | "strict";

/**
 * Apply the regime as a throttle on new buys per run. Only ever reduces, never increases.
 *
 *  - off    : pass-through (disable the filter entirely)
 *  - soft   : bullish/neutral → pass-through; bearish → halve maxNew (floor 0)
 *  - strict : bullish → pass-through; neutral → halve maxNew; bearish → 0
 *
 * Mode resolution: `mode` argument wins, otherwise `INVESTBEST_REGIME_FILTER` env var ("off"
 * disables, "strict" enables strict mode), otherwise falls back to "soft".
 */
export function regimeAdjustedMaxNew(
  maxNew: number,
  regime: MarketRegime,
  modeOrEnvFlag?: RegimeFilterMode | string,
): { adjusted: number; throttled: boolean; mode: RegimeFilterMode } {
  const raw = (modeOrEnvFlag ?? process.env.INVESTBEST_REGIME_FILTER ?? "soft").toLowerCase();
  const mode: RegimeFilterMode =
    raw === "off" ? "off" : raw === "strict" ? "strict" : "soft";

  if (mode === "off") return { adjusted: maxNew, throttled: false, mode };

  if (mode === "strict") {
    if (regime === "bullish") return { adjusted: maxNew, throttled: false, mode };
    if (regime === "neutral") {
      const adjusted = Math.max(0, Math.floor(maxNew / 2));
      return { adjusted, throttled: adjusted < maxNew, mode };
    }
    return { adjusted: 0, throttled: maxNew > 0, mode };
  }

  if (regime !== "bearish") return { adjusted: maxNew, throttled: false, mode };
  const adjusted = Math.max(0, Math.floor(maxNew / 2));
  return { adjusted, throttled: adjusted < maxNew, mode };
}
