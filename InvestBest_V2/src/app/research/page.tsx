import { AppShell } from "@/components/AppShell";
import { SectionCard } from "@/components/SectionCard";

export default function ResearchPage() {
  return (
    <AppShell
      title="Research battery"
      subtitle="V2 should win by being more honest than V1. The core question is not whether a signal can look good, but whether it survives repeated attempts to prove it false."
    >
      <div className="grid two">
        <SectionCard
          title="Validation stack"
          description="Every serious candidate passes through the same battery before it can affect a portfolio."
        >
          <ul className="list">
            <li>Strict holdout split for true out-of-sample evaluation.</li>
            <li>Walk-forward windows instead of one static train/test cut.</li>
            <li>Information Coefficient stability, not just return vanity.</li>
            <li>Newey-West / HAC-corrected alpha t-statistics.</li>
            <li>Bonferroni-style multiple-testing discipline by experiment family.</li>
          </ul>
        </SectionCard>

        <SectionCard
          title="What changes from V1"
          description="The research layer becomes a first-class citizen rather than an afterthought."
        >
          <ul className="list">
            <li>Candidate data is exported as training rows, not just used for one live decision.</li>
            <li>Models are versioned and compared instead of quietly replacing each other.</li>
            <li>Promotion and decay become explicit states.</li>
            <li>The app tells you what is not working with the same honesty it uses for what is working.</li>
          </ul>
        </SectionCard>
      </div>

      <SectionCard
        title="Recommended build sequence"
        description="This is the order that makes V2 genuinely stronger rather than just more complicated."
      >
        <table className="table">
          <thead>
            <tr>
              <th>Phase</th>
              <th>Goal</th>
              <th>Why it matters</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>1</td>
              <td>Dataset + training rows</td>
              <td>Without a proper dataset, regression and factor ideas are still storytelling.</td>
            </tr>
            <tr>
              <td>2</td>
              <td>Walk-forward engine</td>
              <td>Lets us measure whether a signal survives outside the exact period it was fitted on.</td>
            </tr>
            <tr>
              <td>3</td>
              <td>Model registry and promotion gates</td>
              <td>Stops accidental replacement of the active engine with a prettier but weaker challenger.</td>
            </tr>
            <tr>
              <td>4</td>
              <td>Decay monitor</td>
              <td>Lets the system retire weak models automatically instead of clinging to them.</td>
            </tr>
          </tbody>
        </table>
      </SectionCard>
    </AppShell>
  );
}
