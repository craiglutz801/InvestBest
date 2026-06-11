import { AppShell } from "@/components/AppShell";
import { SectionCard } from "@/components/SectionCard";
import { candidateIdeas } from "@/lib/mockData";

export default function CandidatesPage() {
  return (
    <AppShell
      title="Candidate pipeline"
      subtitle="Ideas should be cheap to generate and cheap to reject. The pipeline should make that visible instead of burying it."
    >
      <SectionCard
        title="From symbol idea to validated model input"
        description="Candidates are not trades. They are hypotheses waiting to earn the right to become experiments."
      >
        <table className="table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Family</th>
              <th>Stage</th>
              <th>Thesis</th>
              <th>Verdict</th>
            </tr>
          </thead>
          <tbody>
            {candidateIdeas.map((candidate) => (
              <tr key={candidate.id}>
                <td><strong>{candidate.symbol}</strong></td>
                <td>{candidate.family}</td>
                <td><span className={`badge ${candidate.stage}`}>{candidate.stage}</span></td>
                <td>{candidate.thesis}</td>
                <td>{candidate.verdict}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>
    </AppShell>
  );
}
