import type { StrategySpec } from "./types";

export type FieldChange = { path: string; from: unknown; to: unknown };

/** Shallow-deep diff for strategy JSON — human-readable audit trail. */
export function diffStrategySpecs(a: StrategySpec, b: StrategySpec): FieldChange[] {
  const out: FieldChange[] = [];
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]) as Set<keyof StrategySpec>;
  for (const k of keys) {
    if (k === "evaluation_meta") continue;
    const va = a[k];
    const vb = b[k];
    if (typeof va === "object" && va !== null && typeof vb === "object" && vb !== null && !Array.isArray(va)) {
      const ak = { ...(va as Record<string, number>) };
      const bk = { ...(vb as Record<string, number>) };
      const sub = new Set([...Object.keys(ak), ...Object.keys(bk)]);
      for (const s of sub) {
        if (ak[s] !== bk[s]) {
          out.push({ path: `${String(k)}.${s}`, from: ak[s], to: bk[s] });
        }
      }
    } else if (JSON.stringify(va) !== JSON.stringify(vb)) {
      out.push({ path: String(k), from: va, to: vb });
    }
  }
  return out;
}

export function formatDiffLines(changes: FieldChange[]): string[] {
  return changes.map((c) => `${c.path}: ${JSON.stringify(c.from)} → ${JSON.stringify(c.to)}`);
}
