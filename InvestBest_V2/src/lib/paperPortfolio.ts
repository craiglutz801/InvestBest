import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { getNextScheduledRun } from "@/lib/schedule";
import type { PaperPortfolioState } from "@/lib/types";

const DATA_DIR = path.join(process.cwd(), "data");
const STATE_PATH = path.join(DATA_DIR, "paper-portfolio.json");
const IS_HOSTED_RUNTIME = process.env.VERCEL === "1";

type GlobalWithPortfolioCache = typeof globalThis & {
  __investbestV2PortfolioState?: PaperPortfolioState;
};

function getCachedState(): PaperPortfolioState | undefined {
  return (globalThis as GlobalWithPortfolioCache).__investbestV2PortfolioState;
}

function setCachedState(state: PaperPortfolioState): void {
  (globalThis as GlobalWithPortfolioCache).__investbestV2PortfolioState = state;
}

function createInitialState(): PaperPortfolioState {
  return {
    updatedAt: new Date().toISOString(),
    startingCash: 100000,
    cash: 100000,
    equity: 100000,
    benchmarkSymbol: "SPY",
    benchmarkStartPrice: null,
    benchmarkCurrentPrice: null,
    holdings: [],
    trades: [],
    runHistory: [],
    latestCandidates: [],
    lastRegime: "neutral",
    automation: {
      enabled: true,
      cadence: "hourly",
      marketHoursOnly: true,
      marketDaysOnly: true,
      lastAttemptAt: null,
      lastCompletedAt: null,
      nextPlannedRunAt: getNextScheduledRun()?.toISOString() ?? null,
      launchAgentLabel: "com.craiglutz.investbest-v2.scheduler",
    },
  };
}

function normalizeState(parsed: Partial<PaperPortfolioState>): PaperPortfolioState {
  const base = createInitialState();

  return {
    ...base,
    ...parsed,
    holdings: (parsed.holdings ?? []).map((holding) => ({
      ...holding,
      openedAt: holding.openedAt ?? parsed.updatedAt ?? base.updatedAt,
      highWaterMark: holding.highWaterMark ?? holding.lastPrice,
      daysHeld: holding.daysHeld ?? 0,
    })),
    automation: {
      ...base.automation,
      ...parsed.automation,
    },
  };
}

export async function loadPortfolioState(): Promise<PaperPortfolioState> {
  const cached = getCachedState();
  if (cached) {
    return normalizeState(cached);
  }

  try {
    const raw = await readFile(STATE_PATH, "utf8");
    const parsed = JSON.parse(raw) as Partial<PaperPortfolioState>;
    const normalized = normalizeState(parsed);
    setCachedState(normalized);
    return normalized;
  } catch {
    const initialState = createInitialState();
    setCachedState(initialState);
    if (!IS_HOSTED_RUNTIME) {
      await savePortfolioState(initialState);
    }
    return initialState;
  }
}

export async function savePortfolioState(state: PaperPortfolioState): Promise<void> {
  setCachedState(state);
  if (IS_HOSTED_RUNTIME) {
    return;
  }
  await mkdir(DATA_DIR, { recursive: true });
  await writeFile(STATE_PATH, `${JSON.stringify(state, null, 2)}\n`, "utf8");
}

export async function resetPortfolioState(): Promise<PaperPortfolioState> {
  const initialState = createInitialState();
  await savePortfolioState(initialState);
  return initialState;
}
