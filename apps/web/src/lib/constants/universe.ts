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
