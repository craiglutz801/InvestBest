import { rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";

const label = "com.craiglutz.investbest-v2.scheduler";
const plistPath = path.join(os.homedir(), "Library", "LaunchAgents", `${label}.plist`);

try {
  execFileSync("launchctl", ["unload", plistPath], { stdio: "ignore" });
} catch {}

await rm(plistPath, { force: true });
console.log(`Removed launch agent ${label}`);
