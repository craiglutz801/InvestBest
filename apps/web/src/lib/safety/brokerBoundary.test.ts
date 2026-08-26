import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  ACTIVE_APP_BROKER_POLICY,
  assertNoLiveBrokerCapability,
  FORBIDDEN_ACTIVE_APP_BROKER_PATTERNS,
  scanForForbiddenBrokerUsage,
} from "./brokerBoundary";

const SRC_ROOT = join(__dirname, "../..");

function walkTsFiles(dir: string, acc: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    if (name === "safety" && dir.endsWith("lib")) {
      // Skip this package's own policy strings / tests.
      const nested = join(dir, name);
      if (statSync(nested).isDirectory()) continue;
    }
    const full = join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walkTsFiles(full, acc);
    else if (name.endsWith(".ts") || name.endsWith(".tsx")) acc.push(full);
  }
  return acc;
}

describe("active app broker boundary", () => {
  it("does not enable live orders or a broker SDK", () => {
    expect(ACTIVE_APP_BROKER_POLICY.liveOrdersAllowed).toBe(false);
    expect(ACTIVE_APP_BROKER_POLICY.brokerSdkAllowed).toBe(false);
    expect(ACTIVE_APP_BROKER_POLICY.supportedExecutionMode).toBe("paper");
    expect(() => assertNoLiveBrokerCapability()).not.toThrow();
  });

  it("detects forbidden broker identifiers in a sample", () => {
    expect(scanForForbiddenBrokerUsage('import alpaca from "@alpacahq/alpaca-trade-api"')).toContain(
      "@alpacahq/alpaca-trade-api",
    );
    expect(scanForForbiddenBrokerUsage("const x = 1")).toEqual([]);
  });

  it("scans the active web runtime for live-broker / order paths", () => {
    const files = walkTsFiles(SRC_ROOT);
    const hits: Array<{ file: string; pattern: string }> = [];
    for (const file of files) {
      if (file.includes("/safety/")) continue;
      const src = readFileSync(file, "utf8");
      for (const pattern of FORBIDDEN_ACTIVE_APP_BROKER_PATTERNS) {
        if (src.toLowerCase().includes(pattern.toLowerCase())) {
          hits.push({ file, pattern });
        }
      }
    }
    expect(hits).toEqual([]);
  });
});
