/**
 * Position-sizing helpers shared by the hourly market agent.
 *
 * These helpers are *purely additive* — when their primary tunable is set to 0 (or null),
 * the multiplier returned is exactly `1` so the agent's existing sizing math is preserved.
 */

/** Trading days per year — used to annualize a stdev-of-log-returns figure. */
export const TRADING_DAYS_PER_YEAR = 252;

/**
 * Compute a multiplier in `[floor, ceil]` so that the dollar size for a buy is scaled
 * inversely to the symbol's annualized vol vs the configured target.
 *
 *   targetAnnualizedVol = 0.18 (18%)
 *   vol20Daily          = 0.025 (2.5% daily stdev) → annualized ≈ 0.397 (40%)
 *   multiplier          = 0.18 / 0.397 ≈ 0.45  → cap at floor (0.25 by default)
 *
 * When `targetAnnualizedVol <= 0` (feature disabled) or `vol20Daily <= 0` (insufficient
 * history) we return `1` so callers can multiply unconditionally.
 */
export function volTargetSizeMultiplier(
  vol20Daily: number | null | undefined,
  targetAnnualizedVol: number | null | undefined,
  options?: { floor?: number; ceil?: number; tradingDays?: number },
): number {
  if (!targetAnnualizedVol || targetAnnualizedVol <= 0) return 1;
  if (!vol20Daily || vol20Daily <= 0 || !Number.isFinite(vol20Daily)) return 1;

  const td = options?.tradingDays ?? TRADING_DAYS_PER_YEAR;
  const floor = options?.floor ?? 0.25;
  const ceil = options?.ceil ?? 1.5;
  const annualizedVol = vol20Daily * Math.sqrt(td);
  if (annualizedVol <= 0) return 1;

  const raw = targetAnnualizedVol / annualizedVol;
  if (!Number.isFinite(raw)) return 1;
  return Math.max(floor, Math.min(ceil, raw));
}

/**
 * Average dollar volume over the last `lookback` bars. Returns 0 if the input is empty
 * or no bars carry a usable `volume`.
 */
export function computeAvgDollarVolume(
  bars: { close: number; volume?: number | null | undefined }[],
  lookback = 20,
): number {
  if (!bars.length) return 0;
  const slice = bars.slice(-lookback);
  let n = 0;
  let sum = 0;
  for (const b of slice) {
    const v = Number(b.volume);
    const px = Number(b.close);
    if (!Number.isFinite(v) || v <= 0) continue;
    if (!Number.isFinite(px) || px <= 0) continue;
    sum += v * px;
    n++;
  }
  return n > 0 ? sum / n : 0;
}

/** Read an optional numeric field off an unknown-shape settings object (Decimal-friendly). */
export function readOptionalNumber<T extends object>(obj: T, key: string): number | undefined {
  const raw = (obj as Record<string, unknown>)[key];
  if (raw == null) return undefined;
  if (typeof raw === "number") return Number.isFinite(raw) ? raw : undefined;
  if (typeof raw === "string") {
    const n = Number(raw);
    return Number.isFinite(n) ? n : undefined;
  }
  if (typeof raw === "object" && raw && "toString" in raw) {
    const n = Number(raw.toString());
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

/** Read an optional string field off an unknown-shape settings object. */
export function readOptionalString<T extends object>(obj: T, key: string): string | undefined {
  const raw = (obj as Record<string, unknown>)[key];
  return typeof raw === "string" && raw.length > 0 ? raw : undefined;
}
