import type { EarningsEvent, PriceBar, UniverseSymbol } from "@/lib/types";

type YahooChartResponse = {
  chart?: {
    result?: Array<{
      timestamp?: number[];
      indicators?: {
        quote?: Array<{
          close?: Array<number | null>;
        }>;
      };
    }>;
    error?: { description?: string };
  };
};

export const UNIVERSE: UniverseSymbol[] = [
  { symbol: "AAPL", segment: "leadership" },
  { symbol: "MSFT", segment: "leadership" },
  { symbol: "NVDA", segment: "leadership" },
  { symbol: "META", segment: "leadership" },
  { symbol: "AMZN", segment: "leadership" },
  { symbol: "GOOGL", segment: "leadership" },
  { symbol: "AVGO", segment: "leadership" },
  { symbol: "NFLX", segment: "leadership" },
  { symbol: "ORCL", segment: "leadership" },
  { symbol: "TSLA", segment: "leadership" },
  { symbol: "QCOM", segment: "leadership" },
  { symbol: "PLTR", segment: "growth" },
  { symbol: "SNOW", segment: "growth" },
  { symbol: "CRWD", segment: "growth" },
  { symbol: "NOW", segment: "growth" },
  { symbol: "PANW", segment: "growth" },
  { symbol: "SHOP", segment: "growth" },
  { symbol: "MDB", segment: "growth" },
  { symbol: "DDOG", segment: "growth" },
  { symbol: "NET", segment: "growth" },
  { symbol: "ZS", segment: "growth" },
  { symbol: "APP", segment: "growth" },
  { symbol: "UBER", segment: "growth" },
  { symbol: "COST", segment: "quality" },
  { symbol: "JPM", segment: "quality" },
  { symbol: "GE", segment: "quality" },
  { symbol: "CAT", segment: "quality" },
  { symbol: "DE", segment: "quality" },
  { symbol: "RTX", segment: "quality" },
  { symbol: "WMT", segment: "quality" },
  { symbol: "LLY", segment: "quality" },
  { symbol: "V", segment: "quality" },
  { symbol: "MA", segment: "quality" },
  { symbol: "GLD", segment: "defensive" },
  { symbol: "IEF", segment: "defensive" },
  { symbol: "SHY", segment: "defensive" },
  { symbol: "XLV", segment: "defensive" },
  { symbol: "XLP", segment: "defensive" },
];

function toIsoDate(timestampSeconds: number): string {
  return new Date(timestampSeconds * 1000).toISOString().slice(0, 10);
}

export async function fetchDailyCloses(symbol: string, range = "1y"): Promise<PriceBar[]> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${range}&interval=1d&includePrePost=false&events=div%2Csplits`;
  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 InvestBest_V2/0.1",
      Accept: "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch ${symbol}: HTTP ${response.status}`);
  }

  const data = (await response.json()) as YahooChartResponse;
  const result = data.chart?.result?.[0];
  const timestamps = result?.timestamp ?? [];
  const closes = result?.indicators?.quote?.[0]?.close ?? [];

  const bars: PriceBar[] = [];
  for (let index = 0; index < Math.min(timestamps.length, closes.length); index += 1) {
    const close = closes[index];
    if (close == null || !Number.isFinite(close)) {
      continue;
    }

    bars.push({
      date: toIsoDate(timestamps[index]),
      close,
    });
  }

  if (bars.length < 60) {
    throw new Error(`Insufficient history for ${symbol}`);
  }

  return bars;
}

function parseCsv(text: string): string[][] {
  return text
    .trim()
    .split("\n")
    .map((line) => line.split(",").map((cell) => cell.trim().replace(/\r$/, "")));
}

export async function fetchUpcomingEarnings(symbols: string[]): Promise<Map<string, EarningsEvent>> {
  const apiKey = process.env.ALPHA_VANTAGE_API_KEY;
  if (!apiKey) {
    return new Map();
  }

  const url = `https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey=${encodeURIComponent(apiKey)}`;
  const response = await fetch(url, {
    headers: {
      "User-Agent": "Mozilla/5.0 InvestBest_V2/0.1",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    return new Map();
  }

  const csv = await response.text();
  const rows = parseCsv(csv);
  if (rows.length < 2) {
    return new Map();
  }

  const [header, ...dataRows] = rows;
  const symbolIndex = header.indexOf("symbol");
  const reportDateIndex = header.indexOf("reportDate");
  if (symbolIndex === -1 || reportDateIndex === -1) {
    return new Map();
  }

  const wanted = new Set(symbols);
  const events = new Map<string, EarningsEvent>();

  for (const row of dataRows) {
    const symbol = row[symbolIndex];
    const reportDate = row[reportDateIndex];
    if (!symbol || !reportDate || !wanted.has(symbol)) {
      continue;
    }

    const existing = events.get(symbol);
    if (!existing || reportDate < existing.reportDate) {
      events.set(symbol, { symbol, reportDate });
    }
  }

  return events;
}
