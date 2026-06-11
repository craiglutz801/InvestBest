import { AppShell } from "@/components/AppShell";
import { SectionCard } from "@/components/SectionCard";

export default function ChatPage() {
  return (
    <AppShell
      title="Grounded chat"
      subtitle="V2 chat should explain system state, model evidence, and promotion decisions from stored data. It should not invent numbers or manufacture confidence."
    >
      <div className="grid two">
        <SectionCard
          title="What chat should answer"
          description="Useful, grounded questions over portfolio, experiments, and validation history."
        >
          <ul className="list">
            <li>Why was this candidate rejected?</li>
            <li>Which active model is strongest on out-of-sample stats?</li>
            <li>Is the incubating regression model still beating the baseline in shadow mode?</li>
            <li>Which experiment family is failing most often, and why?</li>
          </ul>
        </SectionCard>

        <SectionCard
          title="What chat must never do"
          description="LLMs can summarize and navigate. They should not be trusted for money math."
        >
          <ul className="list">
            <li>Never generate position sizes.</li>
            <li>Never fabricate validation metrics.</li>
            <li>Never approve a model without deterministic evidence.</li>
            <li>Never imply live-trading readiness from paper-only results.</li>
          </ul>
        </SectionCard>
      </div>
    </AppShell>
  );
}
