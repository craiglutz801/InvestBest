import { AppShell } from "@/components/AppShell";
import { SectionCard } from "@/components/SectionCard";
import { experiments } from "@/lib/mockData";

export default function ExperimentsPage() {
  return (
    <AppShell
      title="Experiment ledger"
      subtitle="Every model idea should leave behind a readable trail: hypothesis, test window, validation outcome, and promotion verdict."
    >
      <div className="stack">
        {experiments.map((experiment) => (
          <SectionCard
            key={experiment.id}
            title={experiment.title}
            description={experiment.hypothesis}
          >
            <div className="grid three">
              <div className="note">
                <span className={`badge ${experiment.status}`}>{experiment.status}</span>
                <p style={{ margin: "0.65rem 0 0", color: "var(--muted)" }}>
                  Promotion should depend on measured evidence, never on excitement.
                </p>
              </div>
              <div className="note">
                <strong>Walk-forward</strong>
                <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>{experiment.walkForwardPasses}</p>
              </div>
              <div className="note">
                <strong>IC / correction</strong>
                <p style={{ margin: "0.45rem 0 0", color: "var(--muted)" }}>
                  {experiment.icSummary} · {experiment.bonferroniBar}
                </p>
              </div>
            </div>
          </SectionCard>
        ))}
      </div>
    </AppShell>
  );
}
