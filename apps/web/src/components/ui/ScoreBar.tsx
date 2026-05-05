import { cn } from "@/lib/utils";

export type ScoreBarKind = "buy" | "sellRisk" | "confidence";

export type ScoreBarProps = {
  /** Numeric score in [0, 100]. Pass null/undefined to render an em-dash placeholder. */
  value: number | null | undefined;
  kind: ScoreBarKind;
  className?: string;
  /** Width of the rendered bar; defaults to 56px which fits comfortably in dense tables. */
  widthPx?: number;
};

/**
 * Compact horizontal bar + numeric label for a 0–100 score.
 *
 * Color semantics:
 *  - buy        : higher = better (green) → red at low buy scores
 *  - sellRisk   : higher = worse (red)  → green at low risk
 *  - confidence : higher = better (green) → amber at moderate, gray at low
 *
 * Pure presentational: no state, no side effects. Safe to drop into any table cell.
 */
export function ScoreBar({ value, kind, className, widthPx = 56 }: ScoreBarProps) {
  if (value == null || Number.isNaN(value)) {
    return <span className="text-muted-foreground">—</span>;
  }

  const v = Math.max(0, Math.min(100, value));
  const fillColor = pickColor(v, kind);
  const trackColor = "bg-muted";

  return (
    <div className={cn("inline-flex items-center gap-1.5 align-middle", className)}>
      <div
        className={cn("relative h-1.5 overflow-hidden rounded-full", trackColor)}
        style={{ width: widthPx }}
        aria-hidden
      >
        <div className={cn("absolute inset-y-0 left-0 rounded-full", fillColor)} style={{ width: `${v}%` }} />
      </div>
      <span className="tabular-nums text-xs">{v.toFixed(0)}</span>
    </div>
  );
}

function pickColor(v: number, kind: ScoreBarKind): string {
  if (kind === "buy") {
    if (v >= 70) return "bg-emerald-500";
    if (v >= 50) return "bg-emerald-400/80";
    if (v >= 30) return "bg-amber-400";
    return "bg-rose-400";
  }
  if (kind === "sellRisk") {
    if (v >= 70) return "bg-rose-500";
    if (v >= 50) return "bg-amber-500";
    if (v >= 30) return "bg-amber-300";
    return "bg-emerald-400";
  }
  if (v >= 70) return "bg-emerald-500";
  if (v >= 50) return "bg-emerald-400/70";
  if (v >= 30) return "bg-amber-400";
  return "bg-muted-foreground/40";
}
