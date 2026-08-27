import { describe, expect, it } from "vitest";
import { assessMarketRegime, regimeAdjustedMaxNew } from "@/lib/portfolio/marketRegime";
import { mapQuoteDetail, parseOptionalVolume, parseProviderTimestamp } from "@/lib/data-provider/twelveData";
import {
  canOpenNewBuysFromBenchmark,
  dataQualitySkipMessage,
  evaluateBars,
  evaluateQuote,
  MIN_BARS_FOR_REGIME_SMA200,
  MIN_BARS_FOR_TRADE,
} from "./marketDataGate";

function bar(overrides: Partial<{ time: Date; open: number; high: number; low: number; close: number; volume: number | null }> = {}) {
  return {
    time: new Date("2026-08-25T20:00:00Z"),
    open: 100,
    high: 101,
    low: 99,
    close: 100.5,
    volume: 1_000_000 as number | null,
    ...overrides,
  };
}

function series(n = MIN_BARS_FOR_TRADE, now = new Date("2026-08-26T16:00:00Z")) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const t = new Date(now);
    t.setUTCDate(t.getUTCDate() - (n - 1 - i));
    out.push(bar({ time: t, close: 100 + i * 0.1, high: 101 + i * 0.1, low: 99, open: 100 }));
  }
  return out;
}

describe("market data quality gate", () => {
  const now = new Date("2026-08-26T16:00:00Z");

  it("accepts a complete recent series", () => {
    expect(evaluateBars(series(), { now })).toEqual({ ok: true });
  });

  it("rejects missing bars", () => {
    expect(evaluateBars([], { now })).toMatchObject({ ok: false, reason: "MISSING_BARS" });
    expect(evaluateBars(null, { now })).toMatchObject({ ok: false, reason: "MISSING_BARS" });
  });

  it("rejects a partial / short series", () => {
    expect(evaluateBars(series(5), { now })).toMatchObject({ ok: false, reason: "INSUFFICIENT_BARS" });
  });

  it("rejects non-finite and non-positive prices", () => {
    const bars = series();
    bars[3] = bar({ time: bars[3].time, close: Number.NaN, high: 101, low: 99, open: 100 });
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "NON_FINITE" });
    bars[3] = bar({ time: bars[3].time, close: -1, high: 101, low: 99, open: 100 });
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "NON_POSITIVE_PRICE" });
  });

  it("rejects inconsistent OHLC", () => {
    const bars = series();
    bars[10] = bar({ time: bars[10].time, open: 100, high: 99, low: 101, close: 100 });
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "INCONSISTENT_OHLC" });
  });

  it("rejects stale last bar", () => {
    // Shift the whole series so timestamps stay strictly increasing; only last-bar age should fail.
    const bars = series(MIN_BARS_FOR_TRADE, new Date("2026-08-01T20:00:00Z"));
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "STALE_BARS" });
  });

  it("rejects a mostly volume-less series as partial", () => {
    const bars = series().map((b, i) => (i < 18 ? { ...b, volume: null } : b));
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "PARTIAL_SERIES" });
  });

  it("rejects invalid, stale, and inconsistent quotes", () => {
    expect(evaluateQuote(null)).toMatchObject({ ok: false, reason: "MISSING_QUOTE" });
    expect(evaluateQuote({ price: 0 })).toMatchObject({ ok: false, reason: "INVALID_QUOTE" });
    expect(evaluateQuote({ price: 10, high: 9, low: 8 })).toMatchObject({
      ok: false,
      reason: "INCONSISTENT_QUOTE",
    });
    expect(
      evaluateQuote(
        { price: 10, timestamp: new Date("2026-08-01T00:00:00Z") },
        { now },
      ),
    ).toMatchObject({ ok: false, reason: "STALE_QUOTE" });
  });

  it("formats a skip/no-trade reason", () => {
    const r = evaluateBars([], { now });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(dataQualitySkipMessage(r)).toMatch(/^MISSING_BARS:/);
  });
});

describe("fail-closed: SPY history shorter than SMA200 must not authorize new buys", () => {
  const now = new Date("2026-08-26T16:00:00Z");

  it("documents the prior bypass: 50–199 bars look neutral and soft mode would allow full buys", () => {
    const partial = series(90, now);
    const quality = evaluateBars(partial, { now, minBars: 50 });
    expect(quality.ok).toBe(true);
    const regime = assessMarketRegime(partial.map((b) => b.close));
    expect(regime.sma200).toBeNull();
    expect(regime.regime).toBe("neutral");
    expect(regimeAdjustedMaxNew(3, regime.regime, "soft").adjusted).toBe(3);
  });

  it("requires 200 validated bars and a real SMA200 before new buys", () => {
    for (const n of [50, 90, 199]) {
      const bars = series(n, now);
      const quality = evaluateBars(bars, { now, minBars: MIN_BARS_FOR_REGIME_SMA200 });
      expect(quality).toMatchObject({ ok: false, reason: "INSUFFICIENT_BARS" });
      const regime = assessMarketRegime(bars.map((b) => b.close));
      expect(canOpenNewBuysFromBenchmark({ barQuality: quality, sma200: regime.sma200 })).toBe(false);
    }

    const enough = series(200, now);
    const quality = evaluateBars(enough, { now, minBars: MIN_BARS_FOR_REGIME_SMA200 });
    expect(quality).toEqual({ ok: true });
    const regime = assessMarketRegime(enough.map((b) => b.close));
    expect(regime.sma200).not.toBeNull();
    expect(canOpenNewBuysFromBenchmark({ barQuality: quality, sma200: regime.sma200 })).toBe(true);
  });
});

describe("fail-closed: quotes without a provider timestamp cannot be treated as fresh", () => {
  const now = new Date("2026-08-26T16:00:00Z");

  it("documents the prior bypass: a priced quote with no timestamp used to pass", () => {
    const dropped = mapQuoteDetail("AAPL", { price: "187.50", open: "187.00", high: "188.00", low: "186.50" });
    expect(dropped.timestamp).toBeNull();
    expect(dropped.price).toBe(187.5);
  });

  it("rejects missing or invalid provider timestamps", () => {
    expect(evaluateQuote({ price: 187.5 })).toMatchObject({ ok: false, reason: "MISSING_QUOTE_TIMESTAMP" });
    expect(evaluateQuote({ price: 187.5, timestamp: "not-a-date" })).toMatchObject({
      ok: false,
      reason: "MISSING_QUOTE_TIMESTAMP",
    });
    const mapped = mapQuoteDetail("AAPL", { price: "187.50" });
    expect(evaluateQuote(mapped, { now })).toMatchObject({ ok: false, reason: "MISSING_QUOTE_TIMESTAMP" });
  });

  it("accepts a quote only when the provider timestamp is present and fresh", () => {
    const unixSec = Math.floor(now.getTime() / 1000);
    const mapped = mapQuoteDetail("AAPL", {
      price: "187.50",
      open: "187.00",
      high: "188.00",
      low: "186.50",
      timestamp: unixSec,
      datetime: "2026-08-26 12:00:00",
    });
    expect(mapped.timestamp).toBeInstanceOf(Date);
    expect(evaluateQuote(mapped, { now })).toEqual({ ok: true });
  });
});

describe("fail-closed: missing/nonpositive volume must not look like a valid series", () => {
  const now = new Date("2026-08-26T16:00:00Z");

  it("documents the prior bypass: absent volume coerced to 0", () => {
    const missing: string | undefined = undefined;
    expect(Number(missing ?? 0)).toBe(0);
    expect(parseOptionalVolume(undefined)).toBeNull();
    expect(parseOptionalVolume("")).toBeNull();
    expect(parseOptionalVolume("1e6")).toBe(1_000_000);
  });

  it("treats zero volume as unusable so an all-zero series cannot pass the trade gate", () => {
    const zeros = series().map((b) => ({ ...b, volume: 0 }));
    expect(evaluateBars(zeros, { now })).toMatchObject({ ok: false, reason: "PARTIAL_SERIES" });
  });

  it("still rejects a mostly-null volume series as partial", () => {
    const bars = series().map((b, i) => (i < 18 ? { ...b, volume: null } : b));
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "PARTIAL_SERIES" });
  });
});

describe("fail-closed: bar and quote timestamps must have temporal integrity", () => {
  const now = new Date("2026-08-26T16:00:00Z");

  it("documents the prior bypass: shuffled bars still passed when the last row was recent", () => {
    const bars = series();
    expect(bars[bars.length - 1]!.time.getTime()).toBe(now.getTime());
    const shuffled = [...bars];
    const tmp = shuffled[4]!;
    shuffled[4] = shuffled[5]!;
    shuffled[5] = tmp;
    // Last bar is still `now`; only a chronological check can reject this.
    expect(shuffled[shuffled.length - 1]!.time.getTime()).toBe(now.getTime());
  });

  it("rejects out-of-order bars", () => {
    const bars = series();
    const tmp = bars[8]!;
    bars[8] = bars[9]!;
    bars[9] = tmp;
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "OUT_OF_ORDER_BARS" });
  });

  it("rejects duplicate bar timestamps", () => {
    const bars = series();
    bars[10] = { ...bars[10]!, time: bars[9]!.time };
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "DUPLICATE_BARS" });
  });

  it("rejects a last bar materially in the future", () => {
    const bars = series();
    const future = new Date(now);
    future.setUTCDate(future.getUTCDate() + 7);
    const last = bars[bars.length - 1]!;
    bars[bars.length - 1] = { ...last, time: future };
    expect(evaluateBars(bars, { now })).toMatchObject({ ok: false, reason: "FUTURE_BARS" });
  });

  it("rejects a quote materially in the future", () => {
    expect(
      evaluateQuote({ price: 10, timestamp: new Date("2026-09-02T00:00:00Z") }, { now }),
    ).toMatchObject({ ok: false, reason: "FUTURE_QUOTE" });
  });

  it("still accepts modest clock skew within the future slack", () => {
    const quoteSkew = new Date(now.getTime() + 30 * 60 * 1000);
    expect(evaluateQuote({ price: 10, timestamp: quoteSkew }, { now })).toEqual({ ok: true });
    const bars = series();
    const last = bars[bars.length - 1]!;
    bars[bars.length - 1] = { ...last, time: new Date(now.getTime() + 12 * 3600_000) };
    expect(evaluateBars(bars, { now })).toEqual({ ok: true });
  });
});

describe("parseProviderTimestamp", () => {
  it("prefers unix seconds, then datetime", () => {
    const fromUnix = parseProviderTimestamp({ timestamp: 1_724_688_000 });
    expect(fromUnix?.toISOString()).toBe("2024-08-26T16:00:00.000Z");
    const fromDatetime = parseProviderTimestamp({ datetime: "2026-08-26T15:00:00Z" });
    expect(fromDatetime?.toISOString()).toBe("2026-08-26T15:00:00.000Z");
    expect(parseProviderTimestamp({})).toBeNull();
  });
});
