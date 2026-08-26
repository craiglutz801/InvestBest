import { describe, expect, it } from "vitest";
import {
  dataQualitySkipMessage,
  evaluateBars,
  evaluateQuote,
  MIN_BARS_FOR_TRADE,
} from "./marketDataGate";

function bar(overrides: Partial<{ time: Date; open: number; high: number; low: number; close: number; volume: number }> = {}) {
  return {
    time: new Date("2026-08-25T20:00:00Z"),
    open: 100,
    high: 101,
    low: 99,
    close: 100.5,
    volume: 1_000_000,
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
    const bars = series();
    bars[bars.length - 1] = bar({ time: new Date("2026-08-01T20:00:00Z") });
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
