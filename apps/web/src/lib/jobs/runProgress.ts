import { prisma } from "@/lib/db";

const MAX_ENTRIES = 250;

export type RunProgressEntry = {
  at: string;
  phase: string;
  message: string;
  detail?: string | null;
};

/** Per-position mark-to-market captured during a run (before / after trades). */
export type HoldingsMarkEntry = {
  ticker: string;
  symbolId: string;
  quantity: number;
  avgCost: number;
  lastPrice: number;
  marketValue: number;
  costBasis: number;
  unrealizedPnl: number;
  unrealizedPct: number;
  /** Daily return approximations from the latest bar series (share price, not position dollar PnL). */
  ret1d: number;
  ret5d: number;
  ret20d: number;
};

/** Parsed `DecisionRun.notesJson` — includes agent metadata and live `progress` steps. */
export type RunNotes = {
  progress?: RunProgressEntry[];
  useMock?: boolean;
  symbols?: number;
  error?: string;
  holdingsMarkBefore?: HoldingsMarkEntry[];
  holdingsMarkAfter?: HoldingsMarkEntry[];
};

export function parseRunNotes(raw: string | null | undefined): RunNotes {
  if (raw == null || raw === "") return {};
  try {
    const o = JSON.parse(raw) as unknown;
    if (typeof o !== "object" || o === null || Array.isArray(o)) return {};
    return o as RunNotes;
  } catch {
    return {};
  }
}

export async function appendRunProgress(
  runId: string,
  phase: string,
  message: string,
  detail?: string | null,
): Promise<void> {
  const row = await prisma.decisionRun.findUnique({
    where: { id: runId },
    select: { notesJson: true },
  });
  const notes = parseRunNotes(row?.notesJson);
  const prev: RunProgressEntry[] = Array.isArray(notes.progress) ? notes.progress : [];
  const entry: RunProgressEntry = {
    at: new Date().toISOString(),
    phase,
    message,
    detail: detail ?? null,
  };
  const next = [...prev, entry];
  notes.progress = next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next;

  await prisma.decisionRun.update({
    where: { id: runId },
    data: { notesJson: JSON.stringify(notes) },
  });
}

/** Append a holdings review block to progress and persist structured marks for the run poll UI. */
export async function appendHoldingsReview(
  runId: string,
  timing: "before" | "after",
  headerMessage: string,
  rowLines: { message: string; detail: string | null }[],
  entries: HoldingsMarkEntry[],
): Promise<void> {
  const row = await prisma.decisionRun.findUnique({
    where: { id: runId },
    select: { notesJson: true },
  });
  const notes = parseRunNotes(row?.notesJson);
  const prev: RunProgressEntry[] = Array.isArray(notes.progress) ? notes.progress : [];
  const at = new Date().toISOString();
  const block: RunProgressEntry[] = [
    { at, phase: "holdings", message: headerMessage, detail: null },
    ...rowLines.map((l) => ({
      at,
      phase: "holdings",
      message: l.message,
      detail: l.detail,
    })),
  ];
  const next = [...prev, ...block];
  notes.progress = next.length > MAX_ENTRIES ? next.slice(-MAX_ENTRIES) : next;
  if (timing === "before") notes.holdingsMarkBefore = entries;
  else notes.holdingsMarkAfter = entries;

  await prisma.decisionRun.update({
    where: { id: runId },
    data: { notesJson: JSON.stringify(notes) },
  });
}
