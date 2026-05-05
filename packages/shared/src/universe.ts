/** Curated MVP universe — Build Spec §5 */

export const DEFAULT_STOCK_TICKERS = [
  "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "JPM", "XOM", "UNH",
  "COST", "WMT", "AMD", "NFLX", "BRK.B", "AVGO", "LLY", "GE", "CAT", "CRM",
] as const;

export const DEFAULT_COMMODITY_ETF_TICKERS = ["GLD", "SLV", "USO", "UNG", "DBA"] as const;

export const ALL_DEFAULT_TICKERS = [
  ...DEFAULT_STOCK_TICKERS,
  ...DEFAULT_COMMODITY_ETF_TICKERS,
] as const;
