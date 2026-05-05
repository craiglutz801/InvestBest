import {
  fetchDailySeries,
  fetchQuoteDetail,
  type OhlcvBar,
  type QuoteDetail,
} from "@/lib/data-provider/twelveData";

/**
 * Provider-agnostic surface so Twelve Data can be swapped for another vendor later.
 * @see InvestBest_Cursor_Addendum — §4 Data-provider instruction
 */
export type MarketDataProvider = {
  getTimeSeries(symbol: string, interval: "1day", outputsize: number): Promise<OhlcvBar[]>;
  getQuote(symbol: string): Promise<QuoteDetail>;
};

export function createTwelveDataProvider(apiKey: string): MarketDataProvider {
  return {
    getTimeSeries: (symbol, _interval, outputsize) => fetchDailySeries(symbol, apiKey, outputsize),
    getQuote: (symbol) => fetchQuoteDetail(symbol, apiKey),
  };
}
