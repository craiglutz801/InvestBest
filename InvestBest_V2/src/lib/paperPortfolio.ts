import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { neon } from "@neondatabase/serverless";
import { getNextScheduledRun } from "@/lib/schedule";
import type { PaperPortfolioState } from "@/lib/types";

const DATA_DIR = path.join(process.cwd(), "data");
const STATE_PATH = path.join(DATA_DIR, "paper-portfolio.json");
const IS_HOSTED_RUNTIME = process.env.VERCEL === "1";
const PORTFOLIO_STATE_KEY = "paper-portfolio";

type GlobalWithPortfolioCache = typeof globalThis & {
  __investbestV2PortfolioState?: PaperPortfolioState;
};

let databaseUrlInUse: string | null = null;
let sqlClient: ReturnType<typeof neon> | null = null;
let tableReadyPromise: Promise<void> | null = null;
let warnedMissingHostedDatabase = false;

function shouldUseProcessCache(): boolean {
  return !IS_HOSTED_RUNTIME && !getDatabaseUrl();
}

function isIgnorableCreateTableRace(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }

  return (
    error.message.includes("pg_type_typname_nsp_index") ||
    error.message.includes("already exists") ||
    error.message.includes("duplicate key value violates unique constraint")
  );
}

function getCachedState(): PaperPortfolioState | undefined {
  if (!shouldUseProcessCache()) {
    return undefined;
  }

  return (globalThis as GlobalWithPortfolioCache).__investbestV2PortfolioState;
}

function setCachedState(state: PaperPortfolioState): void {
  if (!shouldUseProcessCache()) {
    delete (globalThis as GlobalWithPortfolioCache).__investbestV2PortfolioState;
    return;
  }

  (globalThis as GlobalWithPortfolioCache).__investbestV2PortfolioState = state;
}

function getDatabaseUrl(): string | null {
  return (
    process.env.DATABASE_URL?.trim() ||
    process.env.POSTGRES_URL?.trim() ||
    process.env.POSTGRES_PRISMA_URL?.trim() ||
    null
  );
}

function getSqlClient(): ReturnType<typeof neon> | null {
  const databaseUrl = getDatabaseUrl();

  if (!databaseUrl) {
    if (IS_HOSTED_RUNTIME && !warnedMissingHostedDatabase) {
      warnedMissingHostedDatabase = true;
      console.warn(
        "[paperPortfolio] Hosted runtime is missing DATABASE_URL/POSTGRES_URL. Portfolio state will not persist across instances.",
      );
    }
    return null;
  }

  if (!sqlClient || databaseUrlInUse !== databaseUrl) {
    databaseUrlInUse = databaseUrl;
    sqlClient = neon(databaseUrl);
    tableReadyPromise = null;
  }

  return sqlClient;
}

async function ensurePortfolioTable(): Promise<boolean> {
  const sql = getSqlClient();
  if (!sql) {
    return false;
  }

  if (!tableReadyPromise) {
    tableReadyPromise = (async () => {
      try {
        await sql`
          CREATE TABLE IF NOT EXISTS investbest_v2_state (
            state_key TEXT PRIMARY KEY,
            state JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
          )
        `;
      } catch (error) {
        if (!isIgnorableCreateTableRace(error)) {
          throw error;
        }
      }
    })();
  }

  await tableReadyPromise;
  return true;
}

async function loadPortfolioStateFromDatabase(): Promise<PaperPortfolioState | null> {
  if (!(await ensurePortfolioTable())) {
    return null;
  }

  const sql = getSqlClient();
  if (!sql) {
    return null;
  }

  const rows = (await sql`
    SELECT state
    FROM investbest_v2_state
    WHERE state_key = ${PORTFOLIO_STATE_KEY}
    LIMIT 1
  `) as Array<{ state: Partial<PaperPortfolioState> }>;

  if (rows.length === 0) {
    return null;
  }

  return normalizeState(rows[0].state);
}

async function savePortfolioStateToDatabase(state: PaperPortfolioState): Promise<boolean> {
  if (!(await ensurePortfolioTable())) {
    return false;
  }

  const sql = getSqlClient();
  if (!sql) {
    return false;
  }

  const serialized = JSON.stringify(state);

  await sql`
    INSERT INTO investbest_v2_state (state_key, state, updated_at)
    VALUES (
      ${PORTFOLIO_STATE_KEY},
      CAST(${serialized} AS jsonb),
      ${state.updatedAt}
    )
    ON CONFLICT (state_key)
    DO UPDATE SET
      state = EXCLUDED.state,
      updated_at = EXCLUDED.updated_at
  `;

  return true;
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
    const databaseState = await loadPortfolioStateFromDatabase();
    if (databaseState) {
      setCachedState(databaseState);
      return databaseState;
    }
  } catch (error) {
    console.error("[paperPortfolio] Failed to load portfolio state from database.", error);
    throw error;
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

  try {
    if (await savePortfolioStateToDatabase(state)) {
      return;
    }
  } catch (error) {
    console.error("[paperPortfolio] Failed to save portfolio state to database.", error);
    throw error;
  }

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
