import type { getTradableSymbols } from "@/lib/server/tradableSymbols";

export type TradableSymbolRow = Awaited<ReturnType<typeof getTradableSymbols>>[number];

/** Open lots first (better UX in logs); used for mock mode too (no API cap). */
export function orderUniverseHoldingsFirst(
  all: TradableSymbolRow[],
  heldSymbolIds: Set<string>,
): TradableSymbolRow[] {
  const held = all.filter((s) => heldSymbolIds.has(s.id)).sort((a, b) => a.ticker.localeCompare(b.ticker));
  const rest = all.filter((s) => !heldSymbolIds.has(s.id)).sort((a, b) => a.ticker.localeCompare(b.ticker));
  return [...held, ...rest];
}

/**
 * Free-tier friendly universe for one agent run:
 * - Open holdings first (so API budget is spent on positions you actually hold).
 * - Cap total symbols (Twelve Data free tier: few calls/minute and daily credits).
 *
 * `INVESTBEST_MAX_UNIVERSE_SYMBOLS`:
 * - unset → default cap **28** (reasonable for free tier + default pacing).
 * - `0` → no cap (full tradable list; may hit rate limits without a paid plan).
 * - positive number → explicit cap.
 */
export function prepareUniverseForFreeTier(
  all: TradableSymbolRow[],
  heldSymbolIds: Set<string>,
): { symbols: TradableSymbolRow[]; detail: string | null } {
  const ordered = orderUniverseHoldingsFirst(all, heldSymbolIds);
  const held = all.filter((s) => heldSymbolIds.has(s.id));
  const rest = all.filter((s) => !heldSymbolIds.has(s.id));

  const raw = process.env.INVESTBEST_MAX_UNIVERSE_SYMBOLS;
  let maxSymbols: number | null;
  if (raw === "0") {
    maxSymbols = null;
  } else if (raw === undefined || raw === "") {
    maxSymbols = 28;
  } else {
    const n = Number(raw);
    maxSymbols = Number.isFinite(n) && n > 0 ? Math.floor(n) : 28;
  }

  if (maxSymbols == null || ordered.length <= maxSymbols) {
    const detail =
      held.length > 0
        ? `Scan order: ${held.length} open holding(s) first, then ${rest.length} other symbol(s).`
        : null;
    return { symbols: ordered, detail };
  }

  if (held.length >= maxSymbols) {
    const taken = held.slice(0, maxSymbols);
    return {
      symbols: taken,
      detail: `Universe capped at ${maxSymbols} symbols (free-tier friendly). Only open holdings fit the cap — expand INVESTBEST_MAX_UNIVERSE_SYMBOLS or set to 0 for full list (needs API headroom).`,
    };
  }

  const restSlots = maxSymbols - held.length;
  const symbols = [...held, ...rest.slice(0, restSlots)];
  return {
    symbols,
    detail: `Universe capped at ${maxSymbols} symbols (${held.length} holding(s) + ${restSlots} others). Set INVESTBEST_MAX_UNIVERSE_SYMBOLS=0 for no cap.`,
  };
}
