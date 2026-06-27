import { runScheduledSimulationResult } from "../src/lib/simulator";

async function main() {
  const result = await runScheduledSimulationResult();

  if (result.skipped || !result.run) {
    console.log(JSON.stringify({
      ok: true,
      skipped: true,
      reason: result.reason ?? "Scheduled run skipped.",
      nextPlannedRunAt: result.state.automation.nextPlannedRunAt,
      lastAttemptAt: result.state.automation.lastAttemptAt,
    }));
    return;
  }

  console.log(JSON.stringify({
    ok: true,
    skipped: false,
    runId: result.run.id,
    executedAt: result.run.executedAt,
    buys: result.run.buys,
    sells: result.run.sells,
    equityAfter: result.state.equity,
    cashAfter: result.state.cash,
    note: result.run.note,
    nextPlannedRunAt: result.state.automation.nextPlannedRunAt,
  }));
}

main().catch((error) => {
  console.error(JSON.stringify({
    ok: false,
    error: error instanceof Error ? error.message : "Unknown scheduled tick failure",
  }));
  process.exit(1);
});
