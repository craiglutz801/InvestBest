/** Curated multi-segment tradable universe (paper MVP). Direct commodity futures avoided; ETFs/proxies preferred. */

export const ETF_TICKERS = new Set<string>([
  // Prior commodity / macro ETFs
  "GLD", "SLV", "USO", "UNG", "DBA", "CPER",
  // Defense / aerospace
  "ITA", "XAR",
  // Energy
  "XLE", "XOP", "OIH",
  // Agriculture / ag & softs proxies
  "CORN", "WEAT", "SOYB", "DBA", "CANE", "JO", "NIB",
  // Metals / miners
  "PPLT", "GDX", "GDXJ",
  // Macro / rates / dollar / broad commodity
  "UUP", "TLT", "IEF", "SHY", "DBC", "TIP",
]);

export const UNIVERSE_SEGMENTS = {
  equities_core: {
    name: "Large / liquid equities",
    description: "Diversified US large caps (not majority by count vs thematic segments).",
    tickers: [
      "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "JPM", "XOM", "UNH",
      "COST", "WMT", "AMD", "NFLX", "BRK.B", "AVGO", "LLY", "GE", "CAT", "CRM",
    ] as const,
  },
  software_cloud: {
    name: "Software / cloud leadership",
    description: "Liquid growth and software leaders that often drive risk-on equity tapes.",
    tickers: [
      "SNOW", "PLTR", "CRWD", "PANW", "NOW",
      "ORCL", "MDB", "DDOG", "NET", "SHOP",
    ] as const,
  },
  defense: {
    name: "Defense / aerospace",
    description: "Defense contractors and aerospace / tactical names + sector ETFs.",
    tickers: ["LMT", "NOC", "RTX", "GD", "LHX", "HII", "LDOS", "KTOS", "ITA", "XAR"] as const,
  },
  energy: {
    name: "Energy",
    description: "Integrated / E&P / services + sector & commodity-linked ETFs.",
    tickers: [
      "XOM", "CVX", "COP", "EOG", "SLB", "HAL", "OXY", "MPC",
      "XLE", "USO", "UNG", "XOP", "OIH",
    ] as const,
  },
  agriculture: {
    name: "Agriculture & softs (ETF / ETP)",
    description: "Liquid agricultural commodity proxies.",
    tickers: ["CORN", "WEAT", "SOYB", "DBA", "CANE", "JO", "NIB"] as const,
  },
  metals: {
    name: "Metals & miners",
    description: "Precious metals ETFs, copper proxy, and miner proxies.",
    tickers: ["GLD", "SLV", "PPLT", "CPER", "GDX", "GDXJ"] as const,
  },
  macro: {
    name: "Macro / rates / dollar",
    description: "Regime proxies — features and optional targets.",
    tickers: ["UUP", "TLT", "IEF", "SHY", "DBC", "TIP"] as const,
  },
} as const;

export type SegmentKey = keyof typeof UNIVERSE_SEGMENTS;

const SEGMENT_ORDER: SegmentKey[] = [
  "equities_core",
  "software_cloud",
  "defense",
  "energy",
  "agriculture",
  "metals",
  "macro",
];

/** First matching segment (tickers can appear in more than one list). */
export function primarySegmentKeyForTicker(ticker: string): SegmentKey | null {
  for (const k of SEGMENT_ORDER) {
    if ((UNIVERSE_SEGMENTS[k].tickers as readonly string[]).includes(ticker)) return k;
  }
  return null;
}

/** Unique tickers across all segments (order not preserved). */
export function allSegmentTickers(): string[] {
  const s = new Set<string>();
  for (const seg of Object.values(UNIVERSE_SEGMENTS)) {
    for (const t of seg.tickers) s.add(t);
  }
  return [...s].sort((a, b) => a.localeCompare(b));
}

/** @deprecated use allSegmentTickers */
export const ALL_DEFAULT_TICKERS = allSegmentTickers();

export function assetTypeForTicker(ticker: string): "equity" | "etf" | "commodity_proxy" {
  if (ETF_TICKERS.has(ticker)) return "etf";
  return "equity";
}

export const DEFENSIVE_MACRO_TICKERS = new Set<string>(["IEF", "TLT", "SHY", "TIP", "UUP"]);

export const LEADERSHIP_GROWTH_TICKERS = new Set<string>([
  "NVDA", "MSFT", "AAPL", "AMZN", "META", "GOOGL", "AVGO", "AMD", "TSLA", "NFLX",
  "SNOW", "PLTR", "CRWD", "PANW", "NOW", "ORCL", "MDB", "DDOG", "NET", "SHOP",
]);

const SEGMENT_SCAN_PRIORITY: Record<SegmentKey, number> = {
  software_cloud: 0,
  equities_core: 1,
  defense: 2,
  energy: 3,
  metals: 4,
  agriculture: 5,
  macro: 6,
};

export function isDefensiveMacroTicker(ticker: string): boolean {
  return DEFENSIVE_MACRO_TICKERS.has(ticker);
}

export function isLeadershipGrowthTicker(ticker: string): boolean {
  return LEADERSHIP_GROWTH_TICKERS.has(ticker);
}

export function isCommodityProxySegmentKey(segmentKey: string | null): boolean {
  return segmentKey === "agriculture" || segmentKey === "metals";
}

/**
 * Lower number = scan earlier under capped API budgets.
 * Leadership and software/cloud names get pulled forward so they are not
 * invisible when the universe is truncated for cost / rate-limit reasons.
 */
export function scanPriorityForTicker(ticker: string, segmentKey: string | null): number {
  let score = 100;
  if (isLeadershipGrowthTicker(ticker)) score -= 50;
  if (isDefensiveMacroTicker(ticker)) score += 20;
  if (segmentKey && segmentKey in SEGMENT_SCAN_PRIORITY) {
    score += SEGMENT_SCAN_PRIORITY[segmentKey as SegmentKey] * 10;
  }
  return score;
}
