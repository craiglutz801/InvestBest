import { z } from "zod";

/**
 * Twelve Data free tier: ~8 requests/minute on many plans. Default **7.5s** between calls when
 * `TWELVE_DATA_API_KEY` is set and mock mode is off — avoids mass ingest failures without paid plans.
 * Set `TWELVE_DATA_MIN_GAP_MS=0` to disable pacing (e.g. paid tier or batch jobs).
 */
let lastTwelveDataApiAt = 0;

function getTwelveDataGapMs(): number {
  const explicit = process.env.TWELVE_DATA_MIN_GAP_MS;
  if (explicit === "0") return 0;
  if (explicit != null && explicit !== "") {
    const n = Number(explicit);
    if (Number.isFinite(n) && n >= 0) return n;
  }
  if (process.env.USE_MOCK_MARKET_DATA === "true") return 0;
  if (!process.env.TWELVE_DATA_API_KEY) return 0;
  return 7500;
}

async function enforceTwelveDataGap(): Promise<void> {
  const gap = getTwelveDataGapMs();
  if (gap <= 0) return;
  const now = Date.now();
  const elapsed = now - lastTwelveDataApiAt;
  if (elapsed < gap) {
    await new Promise((r) => setTimeout(r, gap - elapsed));
  }
  lastTwelveDataApiAt = Date.now();
}

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

function isLikelyTwelveDataRateLimit(httpStatus: number, message: string): boolean {
  if (httpStatus === 429) return true;
  const m = message.toLowerCase();
  return (
    m.includes("rate") ||
    m.includes("limit") ||
    m.includes("credit") ||
    m.includes("quota") ||
    m.includes("too many") ||
    m.includes("run out")
  );
}

const candleSchema = z.object({
  datetime: z.string(),
  open: z.string(),
  high: z.string(),
  low: z.string(),
  close: z.string(),
  volume: z.string().optional(),
});

const timeSeriesSchema = z.object({
  values: z.array(candleSchema).optional(),
  meta: z.record(z.unknown()).optional(),
});

export type OhlcvBar = {
  time: Date;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

/**
 * Fetch daily time series from Twelve Data.
 * https://twelvedata.com/docs#time-series
 * One automatic retry after ~8.5s on HTTP 429 / rate-limit style errors (free tier).
 */
export async function fetchDailySeries(
  symbol: string,
  apiKey: string,
  outputsize = 120,
): Promise<OhlcvBar[]> {
  let lastErr: Error | undefined;
  for (let attempt = 0; attempt < 2; attempt++) {
    await enforceTwelveDataGap();
    try {
      const u = new URL("https://api.twelvedata.com/time_series");
      u.searchParams.set("symbol", symbol);
      u.searchParams.set("interval", "1day");
      u.searchParams.set("outputsize", String(outputsize));
      u.searchParams.set("apikey", apiKey);

      const res = await fetch(u.toString(), { cache: "no-store" });
      const raw: unknown = await res.json();
      const apiMsg =
        typeof raw === "object" && raw !== null && "message" in raw
          ? String((raw as { message?: unknown }).message ?? "")
          : "";

      if (!res.ok) {
        const errText = `Twelve Data HTTP ${res.status} for ${symbol}${apiMsg ? `: ${apiMsg}` : ""}`;
        if (attempt === 0 && isLikelyTwelveDataRateLimit(res.status, apiMsg)) {
          lastErr = new Error(errText);
          await sleep(8500);
          continue;
        }
        throw new Error(errText);
      }

      const parsed = timeSeriesSchema.safeParse(raw);
      if (!parsed.success || !parsed.data.values?.length) {
        const msg = apiMsg || "no values";
        if (attempt === 0 && isLikelyTwelveDataRateLimit(200, msg)) {
          lastErr = new Error(`Twelve Data ${symbol}: ${msg}`);
          await sleep(8500);
          continue;
        }
        throw new Error(`Twelve Data ${symbol}: ${msg}`);
      }

      return parsed.data.values
        .map((v) => ({
          time: new Date(v.datetime),
          open: Number(v.open),
          high: Number(v.high),
          low: Number(v.low),
          close: Number(v.close),
          volume: Number(v.volume ?? 0),
        }))
        .sort((a, b) => a.time.getTime() - b.time.getTime());
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (attempt === 0 && isLikelyTwelveDataRateLimit(0, msg)) {
        lastErr = e instanceof Error ? e : new Error(msg);
        await sleep(8500);
        continue;
      }
      throw e;
    }
  }
  throw lastErr ?? new Error(`Twelve Data ${symbol}: request failed`);
}

/** Latest quote (last close from daily series) */
export async function fetchLatestClose(symbol: string, apiKey: string): Promise<number> {
  const series = await fetchDailySeries(symbol, apiKey, 5);
  const last = series[series.length - 1];
  if (!last) throw new Error(`No data for ${symbol}`);
  return last.close;
}

const quoteSchema = z.object({
  close: z.string().optional(),
  price: z.string().optional(),
  message: z.string().optional(),
  code: z.number().optional(),
});

/**
 * Last trade / session price from the quote endpoint (moves intraday unlike daily bars).
 * https://twelvedata.com/docs#quote
 */
export async function fetchQuotePrice(symbol: string, apiKey: string): Promise<number> {
  await enforceTwelveDataGap();

  const u = new URL("https://api.twelvedata.com/quote");
  u.searchParams.set("symbol", symbol);
  u.searchParams.set("apikey", apiKey);

  const res = await fetch(u.toString(), { cache: "no-store" });
  const raw: unknown = await res.json();
  const parsed = quoteSchema.safeParse(raw);
  if (!res.ok) {
    const msg = parsed.success ? parsed.data.message : JSON.stringify(raw);
    throw new Error(`Twelve Data quote HTTP ${res.status} for ${symbol}: ${msg}`);
  }
  if (!parsed.success) {
    throw new Error(`Twelve Data quote parse failed for ${symbol}`);
  }
  if (parsed.data.message && parsed.data.code === 401) {
    throw new Error(`Twelve Data quote: ${parsed.data.message}`);
  }
  const s = parsed.data.price ?? parsed.data.close;
  if (s == null) throw new Error(`Twelve Data quote: no price for ${symbol}`);
  const n = Number(s);
  if (!Number.isFinite(n) || n <= 0) throw new Error(`Twelve Data quote: invalid price for ${symbol}`);
  return n;
}

const richQuoteSchema = z.object({
  open: z.string().optional(),
  high: z.string().optional(),
  low: z.string().optional(),
  close: z.string().optional(),
  price: z.string().optional(),
  previous_close: z.string().optional(),
  change: z.string().optional(),
  percent_change: z.string().optional(),
  volume: z.string().optional(),
  is_market_open: z.union([z.boolean(), z.number()]).optional(),
  message: z.string().optional(),
  code: z.number().optional(),
});

export type QuoteDetail = {
  price: number;
  open: number | null;
  high: number | null;
  low: number | null;
  previousClose: number | null;
  change: number | null;
  changePercent: number | null;
  volume: number | null;
  isRealtime: boolean;
  asOfMarketSession: string | null;
};

function num(s: string | undefined): number | null {
  if (s == null || s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function mapQuoteDetail(symbol: string, d: z.infer<typeof richQuoteSchema>): QuoteDetail {
  if (d.message && d.code === 401) throw new Error(d.message);

  const priceS = d.price ?? d.close;
  if (priceS == null) throw new Error(`Twelve Data quote: no price for ${symbol}`);
  const price = Number(priceS);
  if (!Number.isFinite(price) || price <= 0) throw new Error(`Twelve Data quote: invalid price for ${symbol}`);

  const open = num(d.open);
  const high = num(d.high);
  const low = num(d.low);
  const previousClose = num(d.previous_close);
  const change = num(d.change);
  const changePercent = num(d.percent_change);
  const volume = num(d.volume);
  const isOpen =
    typeof d.is_market_open === "boolean" ? d.is_market_open : d.is_market_open === 1;

  return {
    price,
    open,
    high,
    low,
    previousClose,
    change,
    changePercent,
    volume,
    isRealtime: Boolean(isOpen),
    asOfMarketSession: isOpen ? "regular" : "closed",
  };
}

/** Full quote row for `QuoteSnapshot` persistence. */
export async function fetchQuoteDetail(symbol: string, apiKey: string): Promise<QuoteDetail> {
  let lastErr: Error | undefined;
  for (let attempt = 0; attempt < 2; attempt++) {
    await enforceTwelveDataGap();
    try {
      const u = new URL("https://api.twelvedata.com/quote");
      u.searchParams.set("symbol", symbol);
      u.searchParams.set("apikey", apiKey);

      const res = await fetch(u.toString(), { cache: "no-store" });
      const raw: unknown = await res.json();
      const parsed = richQuoteSchema.safeParse(raw);
      const apiMsg = parsed.success ? (parsed.data.message ?? "") : JSON.stringify(raw);

      if (!res.ok) {
        const errText = `Twelve Data quote HTTP ${res.status} for ${symbol}`;
        if (attempt === 0 && isLikelyTwelveDataRateLimit(res.status, apiMsg)) {
          lastErr = new Error(errText);
          await sleep(8500);
          continue;
        }
        throw new Error(errText);
      }
      if (!parsed.success) {
        throw new Error(`Twelve Data quote parse failed for ${symbol}`);
      }
      const d = parsed.data;
      return mapQuoteDetail(symbol, d);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (attempt === 0 && isLikelyTwelveDataRateLimit(0, msg)) {
        lastErr = e instanceof Error ? e : new Error(msg);
        await sleep(8500);
        continue;
      }
      throw e;
    }
  }
  throw lastErr ?? new Error(`Twelve Data quote failed for ${symbol}`);
}
