/**
 * Market-data quality gate.
 *
 * Invalid / missing / stale / partial / non-finite / inconsistent bars or quotes
 * must never create a simulated trade. After provider mapping, bar timestamps
 * must be strictly increasing, and neither bars nor quotes may be materially
 * in the future. Callers record the reason code as an auditable skip / no-trade.
 */

export type BarLike = {
  time: Date | string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
};

export type QuoteLike = {
  price: number;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  previousClose?: number | null;
  volume?: number | null;
  timestamp?: Date | string | number | null;
  asOf?: Date | string | number | null;
};

export type DataQualityReason =
  | "MISSING_BARS"
  | "INSUFFICIENT_BARS"
  | "PARTIAL_SERIES"
  | "NON_FINITE"
  | "NON_POSITIVE_PRICE"
  | "INCONSISTENT_OHLC"
  | "STALE_BARS"
  | "MISSING_QUOTE"
  | "INVALID_QUOTE"
  | "STALE_QUOTE"
  | "INCONSISTENT_QUOTE"
  | "MISSING_QUOTE_TIMESTAMP"
  | "DUPLICATE_BARS"
  | "OUT_OF_ORDER_BARS"
  | "FUTURE_BARS"
  | "FUTURE_QUOTE";

export type DataQualityResult =
  | { ok: true }
  | { ok: false; reason: DataQualityReason; detail: string };

/** Feature engine needs ~22 closes; below that scores are padded/synthetic. */
export const MIN_BARS_FOR_TRADE = 22;

/** `assessMarketRegime` SMA200 window — fewer bars yield a synthetic "neutral" that must not authorize new buys. */
export const MIN_BARS_FOR_REGIME_SMA200 = 200;

/** Daily bars older than this (calendar hours) are treated as stale. Covers weekends + a US holiday. */
export const DEFAULT_MAX_BAR_AGE_HOURS = 120;

/** Quotes with an explicit timestamp older than this are stale. */
export const DEFAULT_MAX_QUOTE_AGE_HOURS = 24;

/** Daily bars can be labeled for the current session/timezone; reject timestamps materially in the future. */
export const DEFAULT_MAX_FUTURE_BAR_HOURS = 36;

/** Intraday quotes may have modest clock skew; reject timestamps materially in the future. */
export const DEFAULT_MAX_FUTURE_QUOTE_HOURS = 2;

function asDate(value: Date | string | number | null | undefined): Date | null {
  if (value == null) return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isFinite(d.getTime()) ? d : null;
}

function isFiniteNumber(n: unknown): n is number {
  return typeof n === "number" && Number.isFinite(n);
}

/** Volume is usable for liquidity / dollar-volume features only when it is a positive finite number. */
export function isVolumeUsable(volume: number | null | undefined): boolean {
  return isFiniteNumber(volume) && volume > 0;
}

function ohlcFields(bar: BarLike): Array<[string, unknown]> {
  return [
    ["open", bar.open],
    ["high", bar.high],
    ["low", bar.low],
    ["close", bar.close],
  ];
}

export function evaluateBars(
  bars: BarLike[] | null | undefined,
  options?: {
    now?: Date;
    minBars?: number;
    maxAgeHours?: number;
    maxFutureHours?: number;
    requireVolume?: boolean;
  },
): DataQualityResult {
  if (bars == null || bars.length === 0) {
    return { ok: false, reason: "MISSING_BARS", detail: "No OHLCV bars were provided." };
  }

  const minBars = options?.minBars ?? MIN_BARS_FOR_TRADE;
  if (bars.length < minBars) {
    return {
      ok: false,
      reason: "INSUFFICIENT_BARS",
      detail: `Series has ${bars.length} bar(s); ${minBars} required before a trade is allowed.`,
    };
  }

  const now = options?.now ?? new Date();
  const maxAgeHours = options?.maxAgeHours ?? DEFAULT_MAX_BAR_AGE_HOURS;
  const maxFutureHours = options?.maxFutureHours ?? DEFAULT_MAX_FUTURE_BAR_HOURS;

  let missingVolume = 0;
  let previousMs: number | null = null;
  for (let i = 0; i < bars.length; i++) {
    const bar = bars[i];
    const t = asDate(bar.time);
    if (!t) {
      return { ok: false, reason: "NON_FINITE", detail: `Bar ${i} has an invalid timestamp.` };
    }

    const ts = t.getTime();
    if (previousMs !== null) {
      if (ts === previousMs) {
        return {
          ok: false,
          reason: "DUPLICATE_BARS",
          detail: `Bar ${i} timestamp ${t.toISOString()} duplicates the previous bar.`,
        };
      }
      if (ts < previousMs) {
        return {
          ok: false,
          reason: "OUT_OF_ORDER_BARS",
          detail: `Bar ${i} timestamp ${t.toISOString()} is before the previous bar.`,
        };
      }
    }
    previousMs = ts;

    if (ts - now.getTime() > maxFutureHours * 3600_000) {
      return {
        ok: false,
        reason: "FUTURE_BARS",
        detail: `Bar ${i} timestamp ${t.toISOString()} is more than ${maxFutureHours}h in the future.`,
      };
    }

    for (const [name, value] of ohlcFields(bar)) {
      if (!isFiniteNumber(value)) {
        return { ok: false, reason: "NON_FINITE", detail: `Bar ${i} ${name} is not a finite number.` };
      }
      if (value <= 0) {
        return { ok: false, reason: "NON_POSITIVE_PRICE", detail: `Bar ${i} ${name}=${value} is not positive.` };
      }
    }

    if (bar.high < bar.low) {
      return { ok: false, reason: "INCONSISTENT_OHLC", detail: `Bar ${i} high ${bar.high} < low ${bar.low}.` };
    }
    if (bar.close > bar.high || bar.close < bar.low) {
      return {
        ok: false,
        reason: "INCONSISTENT_OHLC",
        detail: `Bar ${i} close ${bar.close} is outside high/low [${bar.low}, ${bar.high}].`,
      };
    }
    if (bar.open > bar.high || bar.open < bar.low) {
      return {
        ok: false,
        reason: "INCONSISTENT_OHLC",
        detail: `Bar ${i} open ${bar.open} is outside high/low [${bar.low}, ${bar.high}].`,
      };
    }

    if (bar.volume != null && !isFiniteNumber(bar.volume)) {
      return { ok: false, reason: "NON_FINITE", detail: `Bar ${i} volume is not finite.` };
    }
    // Missing *or* nonpositive volume is unusable. Mapping absent volume to 0 must not look valid.
    if (!isVolumeUsable(bar.volume)) {
      missingVolume++;
    }
  }

  if (options?.requireVolume && missingVolume > 0) {
    return {
      ok: false,
      reason: "PARTIAL_SERIES",
      detail: `${missingVolume} bar(s) are missing usable volume.`,
    };
  }

  const last = bars[bars.length - 1];
  const lastTime = asDate(last.time);
  if (lastTime && now.getTime() - lastTime.getTime() > maxAgeHours * 3600_000) {
    return {
      ok: false,
      reason: "STALE_BARS",
      detail: `Last bar at ${lastTime.toISOString()} is older than ${maxAgeHours}h.`,
    };
  }

  const gapRatio = missingVolume / bars.length;
  if (gapRatio > 0.25) {
    return {
      ok: false,
      reason: "PARTIAL_SERIES",
      detail: `${missingVolume}/${bars.length} bars lack usable volume (>25%).`,
    };
  }

  return { ok: true };
}

export function evaluateQuote(
  quote: QuoteLike | null | undefined,
  options?: { now?: Date; maxAgeHours?: number; maxFutureHours?: number; requireTimestamp?: boolean },
): DataQualityResult {
  if (quote == null) {
    return { ok: false, reason: "MISSING_QUOTE", detail: "No quote was provided." };
  }
  if (!isFiniteNumber(quote.price) || quote.price <= 0) {
    return { ok: false, reason: "INVALID_QUOTE", detail: `Quote price ${String(quote.price)} is not a positive finite number.` };
  }

  const optional = [quote.open, quote.high, quote.low, quote.previousClose, quote.volume];
  for (const v of optional) {
    if (v == null) continue;
    if (!isFiniteNumber(v)) {
      return { ok: false, reason: "INVALID_QUOTE", detail: "Quote contains a non-finite optional field." };
    }
  }

  if (isFiniteNumber(quote.high) && isFiniteNumber(quote.low) && quote.high < quote.low) {
    return { ok: false, reason: "INCONSISTENT_QUOTE", detail: `Quote high ${quote.high} < low ${quote.low}.` };
  }
  if (isFiniteNumber(quote.high) && quote.price > quote.high) {
    return { ok: false, reason: "INCONSISTENT_QUOTE", detail: `Quote price ${quote.price} > high ${quote.high}.` };
  }
  if (isFiniteNumber(quote.low) && quote.price < quote.low) {
    return { ok: false, reason: "INCONSISTENT_QUOTE", detail: `Quote price ${quote.price} < low ${quote.low}.` };
  }

  const requireTimestamp = options?.requireTimestamp !== false;
  const ts = asDate(quote.timestamp ?? quote.asOf ?? null);
  if (requireTimestamp && !ts) {
    return {
      ok: false,
      reason: "MISSING_QUOTE_TIMESTAMP",
      detail: "Quote has no authoritative provider timestamp; freshness cannot be verified.",
    };
  }

  const now = options?.now ?? new Date();
  const maxAgeHours = options?.maxAgeHours ?? DEFAULT_MAX_QUOTE_AGE_HOURS;
  const maxFutureHours = options?.maxFutureHours ?? DEFAULT_MAX_FUTURE_QUOTE_HOURS;
  if (ts) {
    if (ts.getTime() - now.getTime() > maxFutureHours * 3600_000) {
      return {
        ok: false,
        reason: "FUTURE_QUOTE",
        detail: `Quote timestamp ${ts.toISOString()} is more than ${maxFutureHours}h in the future.`,
      };
    }
    if (now.getTime() - ts.getTime() > maxAgeHours * 3600_000) {
      return {
        ok: false,
        reason: "STALE_QUOTE",
        detail: `Quote timestamp ${ts.toISOString()} is older than ${maxAgeHours}h.`,
      };
    }
  }

  return { ok: true };
}

/**
 * New buys require a quality-gated benchmark series long enough to compute SMA200.
 * A short series that classifies as "neutral" must not authorize the full buy count.
 */
export function canOpenNewBuysFromBenchmark(input: {
  barQuality: DataQualityResult;
  sma200: number | null | undefined;
}): boolean {
  return input.barQuality.ok && input.sma200 != null && Number.isFinite(input.sma200);
}

export function dataQualitySkipMessage(result: Extract<DataQualityResult, { ok: false }>): string {
  return `${result.reason}: ${result.detail}`;
}
