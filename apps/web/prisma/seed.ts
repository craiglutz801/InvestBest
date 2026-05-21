import { PrismaClient } from "@prisma/client";
import {
  UNIVERSE_SEGMENTS,
  allSegmentTickers,
  assetTypeForTicker,
  primarySegmentKeyForTicker,
  type SegmentKey,
} from "../src/lib/constants/universe";

const prisma = new PrismaClient();

const DEMO_EMAIL = process.env.INVESTBEST_DEMO_EMAIL ?? "demo@investbest.local";

/** Twelve Data often expects BRK.B with dot; some feeds use BRK/B */
const DATA_PROVIDER_OVERRIDES: Record<string, string> = {
  "BRK.B": "BRK.B",
};

const DEFAULT_SEARCH_PROFILE = {
  version: 1,
  universe: { enabledSegmentKeys: Object.keys(UNIVERSE_SEGMENTS) },
  opportunity: { momentumBias: "medium", meanReversionBias: "low", defensivePosture: "medium" },
  risk: { minConfidence: 40 },
  timing: { horizon: "3-10d", rebalanceAggressiveness: "normal" },
};

async function main() {
  const user = await prisma.user.upsert({
    where: { email: DEMO_EMAIL },
    create: { email: DEMO_EMAIL },
    update: {},
  });

  let sort = 0;
  const segmentIds: Partial<Record<SegmentKey, string>> = {};
  for (const key of Object.keys(UNIVERSE_SEGMENTS) as SegmentKey[]) {
    const def = UNIVERSE_SEGMENTS[key];
    const row = await prisma.universeSegment.upsert({
      where: { key },
      create: {
        key,
        name: def.name,
        description: def.description,
        isEnabled: true,
        segmentWeight: 1,
        maxPositions: 8,
        sortOrder: sort++,
      },
      update: { name: def.name, description: def.description },
    });
    segmentIds[key] = row.id;
  }

  for (const ticker of allSegmentTickers()) {
    const dp = DATA_PROVIDER_OVERRIDES[ticker] ?? ticker;
    const pk = primarySegmentKeyForTicker(ticker);
    await prisma.symbol.upsert({
      where: { ticker },
      create: {
        ticker,
        name: ticker,
        assetType: assetTypeForTicker(ticker),
        exchange: "US",
        isActive: true,
        dataProviderSymbol: dp,
        segmentKey: pk,
      },
      update: {
        dataProviderSymbol: dp,
        isActive: true,
        segmentKey: pk,
      },
    });
  }

  for (const key of Object.keys(UNIVERSE_SEGMENTS) as SegmentKey[]) {
    const def = UNIVERSE_SEGMENTS[key];
    const segId = segmentIds[key];
    if (!segId) continue;
    for (const ticker of def.tickers) {
      const sym = await prisma.symbol.findUnique({ where: { ticker } });
      if (!sym) continue;
      await prisma.segmentSymbol.upsert({
        where: {
          universeSegmentId_symbolId: { universeSegmentId: segId, symbolId: sym.id },
        },
        create: {
          universeSegmentId: segId,
          symbolId: sym.id,
          isEnabled: true,
          priority: 0,
        },
        update: {},
      });
    }
  }

  let searchProfile = await prisma.searchProfile.findFirst({
    where: { userId: user.id, isDefault: true },
  });
  if (!searchProfile) {
    searchProfile = await prisma.searchProfile.create({
      data: {
        userId: user.id,
        name: "Default",
        isDefault: true,
        profileJson: JSON.stringify(DEFAULT_SEARCH_PROFILE),
      },
    });
  }

  const appSettings = await prisma.appSettings.upsert({
    where: { userId: user.id },
    create: {
      userId: user.id,
      startingCash: 100_000,
      maxPositionPct: 10,
      maxNewPositionsPerRun: 3,
      targetHoldings: 12,
      stopLossPct: 8,
      takeProfitPct: 15,
      minConfidence: 40,
      cashReservePct: 10,
      runFrequencyMinutes: 60,
      newsEnabled: false,
      shortingEnabled: false,
      defaultSlippagePct: 0.05,
      strategyMode: "rules_v1",
      buyScoreThreshold: 45,
      sellRiskThreshold: 65,
      cooldownHours: 24,
      staleQuoteAllowSells: false,
      searchProfileId: searchProfile.id,
    },
    update: { searchProfileId: searchProfile.id },
  });

  // Strategy Upgrade §2 — seed Agent Automation defaults that mirror runFrequencyMinutes.
  // Created lazily so existing demo accounts pick up scheduler settings on next seed.
  const defaultFrequency =
    Number(process.env.DEFAULT_AGENT_RUN_FREQUENCY_MINUTES) || appSettings.runFrequencyMinutes || 60;
  const defaultTimezone = process.env.DEFAULT_SCHEDULE_TIMEZONE ?? "America/Denver";
  const defaultEnabled = process.env.ENABLE_AGENT_SCHEDULER !== "false";
  await prisma.agentScheduleSettings.upsert({
    where: { userId: user.id },
    create: {
      userId: user.id,
      enabled: defaultEnabled,
      schedulePreset: "hourly",
      frequencyMinutes: defaultFrequency,
      timezone: defaultTimezone,
      runOnlyDuringMarketHours: process.env.ENABLE_MARKET_HOURS_ONLY === "true",
      runOnMarketDaysOnly: true,
      skipIfRunAlreadyActive: true,
      maxRunDurationMinutes: Number(process.env.AGENT_RUN_LOCK_TIMEOUT_MINUTES) || 30,
      retryFailedRuns: false,
      maxRetries: 0,
    },
    update: {},
  });

  console.log(
    "Seed OK:",
    DEMO_EMAIL,
    allSegmentTickers().length,
    "symbols,",
    Object.keys(UNIVERSE_SEGMENTS).length,
    "segments",
  );
}

main()
  .then(() => prisma.$disconnect())
  .catch((e) => {
    console.error(e);
    prisma.$disconnect();
    process.exit(1);
  });
