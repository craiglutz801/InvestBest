import { AppShell } from "@/components/AppShell";
import { SectionCard } from "@/components/SectionCard";
import { alerts } from "@/lib/mockData";

export default function SystemPage() {
  return (
    <AppShell
      title="System guardrails"
      subtitle="A better investing system should be harder to trust blindly. V2 makes the safety model, model state, and promotion logic explicit."
    >
      <div className="grid two">
        <SectionCard
          title="Guardrail set"
          description="These controls are part of the product, not optional nice-to-haves."
        >
          <ul className="list">
            <li>Paper-mode hard lock by default.</li>
            <li>Promotion gates before any model becomes active.</li>
            <li>Shadow-run and incubation stages before primary allocation.</li>
            <li>Automatic decay handling when live behavior drifts from validated expectations.</li>
            <li>Central audit trail for every state transition.</li>
          </ul>
        </SectionCard>

        <SectionCard
          title="Current watchlist"
          description="If the system misbehaves, V2 should show you where confidence is breaking down."
        >
          <div className="stack">
            {alerts.map((alert) => (
              <div key={alert.id} className="note">
                <span className={`badge ${alert.severity}`}>{alert.severity}</span>
                <p style={{ margin: "0.6rem 0 0.2rem" }}><strong>{alert.title}</strong></p>
                <p style={{ margin: 0, color: "var(--muted)" }}>{alert.detail}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      </div>
    </AppShell>
  );
}
