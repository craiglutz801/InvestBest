import type { SummaryMetric } from "@/lib/types";

export function MetricCard({ metric }: { metric: SummaryMetric }) {
  const valueClassName = `metric-value${metric.value.length > 14 ? " compact" : ""}`;

  return (
    <div className="card metric-card">
      <p className="card-label">{metric.label}</p>
      <div className={valueClassName}>{metric.value}</div>
      {metric.change ? <p className={`metric-change ${metric.tone ?? "neutral"}`}>{metric.change}</p> : null}
    </div>
  );
}
