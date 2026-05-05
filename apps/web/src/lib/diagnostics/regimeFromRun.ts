import type { MarketRegime } from "@/lib/portfolio/marketRegime";
import { parseRunNotes } from "@/lib/jobs/runProgress";

export function regimeLabelFromRunNotes(notesJson: string | null | undefined): MarketRegime | "unknown" {
  const n = parseRunNotes(notesJson);
  const prog = Array.isArray(n.progress) ? n.progress : [];
  const row = prog.find((p) => p.phase === "regime");
  const text = `${row?.message ?? ""} ${row?.detail ?? ""}`;
  const m = text.match(/Regime:\s*(bullish|neutral|bearish)/i);
  if (!m) return "unknown";
  return m[1]!.toLowerCase() as MarketRegime;
}
