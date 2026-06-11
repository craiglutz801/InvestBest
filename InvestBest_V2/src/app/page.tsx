import { AppShell } from "@/components/AppShell";
import { MetricCard } from "@/components/MetricCard";
import { SectionCard } from "@/components/SectionCard";
import { alerts, experiments, strategyModels, summaryMetrics } from "@/lib/mockData";

export default function HomePage() {
  return (
    <AppShell
      title="A cleaner successor to InvestBest"
      subtitle="InvestBest_V2 is built around research, validation, promotion gates, and model decay detection. It treats trading as a downstream consumer of validated models, not the place where validation happens."
    >
      <div className="grid metrics">
        {summaryMetrics.map((metric) => (
          <MetricCard key={metric.label} metric={metric} />
        ))}
      </div>

      <div className="hero" style={{ marginTop: "1rem" }}>
        <div className="card hero-panel">
          <p className="eyebrow">What V2 changes</p>
          <h2>Research engine first, execution second</h2>
          <p>
            V1 was centered on the paper-trading loop. V2 flips that. Every candidate now belongs to a structured
            lifecycle: hypothesis, backtest, holdout, walk-forward, incubation, activation, and decay. That makes it
            much easier to answer the only question that matters: is the model still earning its right to exist?
          </p>
        </div>
        <div className="card hero-panel">
          <p className="eyebrow">Current priority</p>
          <h2>Promote only what survives the battery</h2>
          <ul className="list">
            <li>Out-of-sample validation before any promotion.</li>
            <li>Walk-forward consistency instead of one lucky backtest.</li>
            <li>Regression/factor lanes that can coexist with V1 instead of replacing it blindly.</li>
            <li>Decay detection so weak models are retired instead of defended.</li>
          </ul>
        </div>
      </div>

      <div className="grid two" style={{ marginTop: "1rem" }}>
        <SectionCard
          title="Model registry"
          description="What is active, what is incubating, and what should never trade again."
        >
          <table className="table">
            <thead>
              <tr>
                <th>Model</th>
                <th>Stage</th>
                <th>OOS Sharpe</th>
                <th>Mean IC</th>
                <th>Notes</th>
              </tr>
            </thead>
            <tbody>
              {strategyModels.map((model) => (
                <tr key={model.id}>
                  <td>
                    <strong>{model.name}</strong>
                    <div className="card-label">{model.family}</div>
                  </td>
                  <td>
                    <span className={`badge ${model.stage}`}>{model.stage}</span>
                  </td>
                  <td>{model.oosSharpe.toFixed(2)}</td>
                  <td>{model.meanIc.toFixed(2)}</td>
                  <td>{model.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>

        <SectionCard
          title="Promotion queue"
          description="Only experiments that clear holdout, walk-forward, and multiple-testing bars should graduate."
        >
          <table className="table">
            <thead>
              <tr>
                <th>Experiment</th>
                <th>Status</th>
                <th>Holdout Sharpe</th>
                <th>Walk-forward</th>
              </tr>
            </thead>
            <tbody>
              {experiments.map((experiment) => (
                <tr key={experiment.id}>
                  <td>
                    <strong>{experiment.title}</strong>
                    <div className="card-label">{experiment.hypothesis}</div>
                  </td>
                  <td>
                    <span className={`badge ${experiment.status}`}>{experiment.status}</span>
                  </td>
                  <td>{experiment.status === "approved" ? experiment.holdoutSharpe.toFixed(2) : "pending"}</td>
                  <td>{experiment.walkForwardPasses}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </SectionCard>
      </div>

      <SectionCard
        title="System posture"
        description="The system should distrust itself by default. Safety and skepticism are design features, not apologies."
      >
        <div className="grid three">
          {alerts.map((alert) => (
            <div key={alert.id} className="note">
              <div style={{ display: "flex", justifyContent: "space-between", gap: "0.8rem", marginBottom: "0.5rem" }}>
                <span className={`badge ${alert.severity}`}>{alert.severity}</span>
                <span className="card-label">{alert.timestamp}</span>
              </div>
              <strong>{alert.title}</strong>
              <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>{alert.detail}</p>
            </div>
          ))}
        </div>
      </SectionCard>
    </AppShell>
  );
}
