import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { evaluateBuyBlock } from "@/lib/rules/buyRules";
import { shouldSell } from "@/lib/rules/sellRules";

const schema = readFileSync(join(__dirname, "../../../prisma/schema.prisma"), "utf8");

const healthyBuy = {
  cash: 50_000,
  portfolioValue: 100_000,
  availableForTrade: 20_000,
  cashReservePct: 10,
  minConfidence: 40,
  buyScore: 70,
  buyScoreThreshold: 45,
  confidenceScore: 80,
  alreadyHeld: false,
  features: {
    ret1d: 0,
    ret5d: 0.02,
    ret20d: 0.05,
    distSma20: 0.02,
    distSma50: 0.01,
    rsi14: 55,
    vol20: 0.2,
    volSpike: false,
  },
  maxVolatility: 0.6,
  maxDistFromMean: 0.15,
  onCooldown: false,
};

describe("shipped paper risk defaults remain unchanged", () => {
  it("keeps schema defaults for cash, position, cooldown, stop, and take-profit", () => {
    expect(schema).toMatch(/startingCash\s+Decimal\s+@default\(100000\)/);
    expect(schema).toMatch(/maxPositionPct\s+Decimal\s+@default\(10\)/);
    expect(schema).toMatch(/maxNewPositionsPerRun\s+Int\s+@default\(3\)/);
    expect(schema).toMatch(/stopLossPct\s+Decimal\s+@default\(8\)/);
    expect(schema).toMatch(/takeProfitPct\s+Decimal\s+@default\(15\)/);
    expect(schema).toMatch(/cashReservePct\s+Decimal\s+@default\(10\)/);
    expect(schema).toMatch(/cooldownHours\s+Int\s+@default\(24\)/);
    expect(schema).toMatch(/defaultSlippagePct\s+Decimal\s+@default\(0\.05\)/);
    expect(schema).toMatch(/agentPaused\s+Boolean\s+@default\(false\)/);
  });

  it("enforces cash reserve, holding, and cooldown blocks", () => {
    expect(
      evaluateBuyBlock({
        ...healthyBuy,
        cash: 5_000,
        availableForTrade: 0,
        cashReservePct: 10,
        portfolioValue: 100_000,
      }),
    ).toMatchObject({ blocked: true, reason: "cash_reserve" });
    expect(evaluateBuyBlock({ ...healthyBuy, alreadyHeld: true })).toMatchObject({
      blocked: true,
      reason: "already_held",
    });
    expect(evaluateBuyBlock({ ...healthyBuy, onCooldown: true })).toMatchObject({
      blocked: true,
      reason: "cooldown",
    });
    expect(evaluateBuyBlock(healthyBuy)).toEqual({ blocked: false });
  });

  it("enforces stop-loss and take-profit", () => {
    const stop = shouldSell({
      currentPrice: 91.9,
      avgCost: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      sellRiskScore: 0,
      sellRiskThreshold: 65,
      ret5d: 0,
      rsi: 50,
    });
    expect(stop).toMatchObject({ sell: true, code: "stop_loss" });

    const tp = shouldSell({
      currentPrice: 115,
      avgCost: 100,
      stopLossPct: 8,
      takeProfitPct: 15,
      sellRiskScore: 0,
      sellRiskThreshold: 65,
      ret5d: 0.1,
      rsi: 60,
    });
    expect(tp).toMatchObject({ sell: true, code: "take_profit" });
  });
});
