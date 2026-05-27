import { prisma } from "../src/lib/db";
import { runSchedulerTick } from "../src/lib/jobs/hourlyAgentScheduler";

function readArg(name: string): string | undefined {
  const prefix = `${name}=`;
  const hit = process.argv.slice(2).find((arg) => arg.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : undefined;
}

async function main() {
  const userId = readArg("--userId");
  const result = await runSchedulerTick({
    userId,
    background: false,
  });

  console.log(JSON.stringify(result, null, 2));

  const failed = result.decisions.filter((decision) => {
    const outcome = decision.outcome;
    return "status" in outcome && (outcome.status === "failed" || outcome.status === "started");
  });

  if (failed.length > 0) {
    process.exitCode = 1;
  }
}

main()
  .catch((error) => {
    console.error("[agent:tick] failed", error);
    process.exitCode = 1;
  })
  .finally(async () => {
    await prisma.$disconnect().catch(() => undefined);
  });
