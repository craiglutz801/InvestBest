import { describe, expect, it } from "vitest";
import {
  computeAvgDollarVolume,
  readOptionalNumber,
  readOptionalString,
  volTargetSizeMultiplier,
} from "./sizing";

describe("volTargetSizeMultiplier", () => {
  it("returns 1 when feature is disabled (target = 0)", () => {
    expect(volTargetSizeMultiplier(0.02, 0)).toBe(1);
    expect(volTargetSizeMultiplier(0.02, undefined)).toBe(1);
    expect(volTargetSizeMultiplier(0.02, null)).toBe(1);
  });

  it("returns 1 when vol is missing or non-positive (insufficient history)", () => {
    expect(volTargetSizeMultiplier(0, 0.18)).toBe(1);
    expect(volTargetSizeMultiplier(null, 0.18)).toBe(1);
    expect(volTargetSizeMultiplier(undefined, 0.18)).toBe(1);
    expect(volTargetSizeMultiplier(Number.NaN, 0.18)).toBe(1);
  });

  it("scales DOWN for high-vol names (annualized vol > target)", () => {
    // vol20 = 4% daily ⇒ annualized ≈ 63%. 18%/63% ≈ 0.29 → above 0.25 floor
    const m = volTargetSizeMultiplier(0.04, 0.18);
    expect(m).toBeLessThan(1);
    expect(m).toBeGreaterThanOrEqual(0.25);
    expect(m).toBeLessThan(0.4);
  });

  it("scales UP for low-vol names (annualized vol < target), capped at ceil", () => {
    // vol20 = 0.5% daily ⇒ annualized ≈ 7.9%. 18%/7.9% ≈ 2.27 → capped at 1.5
    const m = volTargetSizeMultiplier(0.005, 0.18);
    expect(m).toBe(1.5);
  });

  it("respects custom floor/ceil", () => {
    const m = volTargetSizeMultiplier(0.04, 0.18, { floor: 0.1, ceil: 1 });
    expect(m).toBeGreaterThanOrEqual(0.1);
    expect(m).toBeLessThanOrEqual(1);
  });
});

describe("computeAvgDollarVolume", () => {
  it("averages price × volume over the lookback window", () => {
    const bars = [
      { close: 100, volume: 1_000_000 },
      { close: 101, volume: 500_000 },
      { close: 102, volume: 750_000 },
    ];
    const avg = computeAvgDollarVolume(bars, 10);
    const expected = (100 * 1e6 + 101 * 5e5 + 102 * 7.5e5) / 3;
    expect(avg).toBeCloseTo(expected, 2);
  });

  it("ignores bars with missing/zero volume", () => {
    const bars = [
      { close: 100, volume: 0 },
      { close: 100, volume: undefined },
      { close: 100, volume: 1_000_000 },
    ];
    expect(computeAvgDollarVolume(bars, 10)).toBe(100 * 1e6);
  });

  it("returns 0 on empty input or all-skipped bars", () => {
    expect(computeAvgDollarVolume([], 10)).toBe(0);
    expect(
      computeAvgDollarVolume([{ close: 0, volume: 1 }, { close: 100, volume: -1 }], 10),
    ).toBe(0);
  });
});

describe("readOptionalNumber / readOptionalString", () => {
  it("reads numbers, numeric strings, and Decimal-like objects", () => {
    expect(readOptionalNumber({ a: 5 }, "a")).toBe(5);
    expect(readOptionalNumber({ a: "1.25" }, "a")).toBe(1.25);
    expect(readOptionalNumber({ a: { toString: () => "9.5" } as object }, "a")).toBe(9.5);
    expect(readOptionalNumber({ a: null }, "a")).toBeUndefined();
    expect(readOptionalNumber({}, "a")).toBeUndefined();
    expect(readOptionalNumber({ a: "not-a-number" }, "a")).toBeUndefined();
  });

  it("reads strings only when present and non-empty", () => {
    expect(readOptionalString({ m: "soft" }, "m")).toBe("soft");
    expect(readOptionalString({ m: "" }, "m")).toBeUndefined();
    expect(readOptionalString({ m: 123 }, "m")).toBeUndefined();
    expect(readOptionalString({}, "m")).toBeUndefined();
  });
});
