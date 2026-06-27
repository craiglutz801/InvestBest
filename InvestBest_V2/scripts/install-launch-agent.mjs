import { mkdir, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";

const projectDir = process.cwd();
const label = "com.craiglutz.investbest-v2.scheduler";
const launchAgentsDir = path.join(os.homedir(), "Library", "LaunchAgents");
const plistPath = path.join(launchAgentsDir, `${label}.plist`);
const logDir = path.join(projectDir, "data");
const stdoutPath = path.join(logDir, "scheduler.stdout.log");
const stderrPath = path.join(logDir, "scheduler.stderr.log");

const scheduleEntries = Array.from({ length: 7 }, (_, index) => {
  const hour = 6 + index;
  return `
    <dict>
      <key>Weekday</key>
      <integer>1</integer>
      <key>Hour</key>
      <integer>${hour}</integer>
      <key>Minute</key>
      <integer>35</integer>
    </dict>
    <dict>
      <key>Weekday</key>
      <integer>2</integer>
      <key>Hour</key>
      <integer>${hour}</integer>
      <key>Minute</key>
      <integer>35</integer>
    </dict>
    <dict>
      <key>Weekday</key>
      <integer>3</integer>
      <key>Hour</key>
      <integer>${hour}</integer>
      <key>Minute</key>
      <integer>35</integer>
    </dict>
    <dict>
      <key>Weekday</key>
      <integer>4</integer>
      <key>Hour</key>
      <integer>${hour}</integer>
      <key>Minute</key>
      <integer>35</integer>
    </dict>
    <dict>
      <key>Weekday</key>
      <integer>5</integer>
      <key>Hour</key>
      <integer>${hour}</integer>
      <key>Minute</key>
      <integer>35</integer>
    </dict>`;
}).join("\n");

const plist = `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>${label}</string>
    <key>WorkingDirectory</key>
    <string>${projectDir}</string>
    <key>ProgramArguments</key>
    <array>
      <string>/bin/zsh</string>
      <string>-lc</string>
      <string>cd "${projectDir}" &amp;&amp; npm run tick:scheduled</string>
    </array>
    <key>StartCalendarInterval</key>
    <array>
${scheduleEntries}
    </array>
    <key>StandardOutPath</key>
    <string>${stdoutPath}</string>
    <key>StandardErrorPath</key>
    <string>${stderrPath}</string>
    <key>RunAtLoad</key>
    <true/>
  </dict>
</plist>
`;

await mkdir(launchAgentsDir, { recursive: true });
await mkdir(logDir, { recursive: true });
await writeFile(plistPath, plist, "utf8");

try {
  execFileSync("launchctl", ["unload", plistPath], { stdio: "ignore" });
} catch {}

execFileSync("launchctl", ["load", plistPath], { stdio: "inherit" });

console.log(`Installed launch agent at ${plistPath}`);
