import type { DiagnosticWarning } from "@/lib/diagnostics/types";
import { cn } from "@/lib/utils";

export function DiagnosticWarnings({ warnings }: { warnings: DiagnosticWarning[] }) {
  if (warnings.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
        No automated warnings for this window. Keep collecting closed trades for richer attribution.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {warnings.map((w, i) => (
        <div
          key={`${w.code}-${i}`}
          className={cn(
            "rounded-lg border px-4 py-3 text-sm",
            w.severity === "critical" &&
              "border-red-500/40 bg-red-500/5 text-foreground dark:border-red-400/30",
            w.severity === "warning" &&
              "border-amber-500/40 bg-amber-500/5 text-foreground dark:border-amber-400/30",
            w.severity === "info" && "border-blue-500/30 bg-blue-500/5 text-foreground dark:border-blue-400/25",
          )}
        >
          <p className="font-medium leading-snug">
            <span className="mr-2 uppercase tracking-wide text-xs text-muted-foreground">{w.severity}</span>
            {w.title}
          </p>
          <p className="mt-1 leading-relaxed text-muted-foreground">{w.detail}</p>
        </div>
      ))}
    </div>
  );
}
