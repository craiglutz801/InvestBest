import { jsonError, jsonOk } from "@/lib/api/http";
import { triggerAgentRun } from "@/lib/scheduler/triggerAgentRun";
import { requireDefaultUser } from "@/lib/server/defaultUser";

export const dynamic = "force-dynamic";
/** Allow the background agent (scheduled via `after`) time to finish on serverless. */
export const maxDuration = 300;

/**
 * Manual "Run Agent Now" endpoint.
 *
 * Strategy Upgrade §1.5 — both the manual button and the scheduler tick MUST flow
 * through `triggerAgentRun`, which acquires the per-user lock, writes
 * `triggerSource = "manual"` on the resulting DecisionRun, and updates
 * AgentScheduleSettings bookkeeping when the pipeline finishes.
 */
export async function POST(req: Request) {
  try {
    const user = await requireDefaultUser();
    const body = (await req.json().catch(() => ({}))) as {
      strategyVersionId?: string;
      searchProfileId?: string;
      dryRun?: boolean;
      force?: boolean;
    };

    const outcome = await triggerAgentRun({
      userId: user.id,
      triggerSource: "manual",
      runMode: body.dryRun ? "dry_run" : "paper_trade",
      strategyVersionId: body.strategyVersionId ?? null,
      searchProfileId: body.searchProfileId ?? null,
      background: false,
      force: Boolean(body.force),
    });
    return jsonOk(outcome);
  } catch (e) {
    return jsonError(e instanceof Error ? e.message : "Run failed", 500);
  }
}
