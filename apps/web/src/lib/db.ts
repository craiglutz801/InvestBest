import fs from "fs";
import path from "path";

import { PrismaClient } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient | undefined };

/**
 * Next.js loads apps/web/.env but does not override vars already set in the shell.
 * A stale DATABASE_URL (e.g. localhost:5433 from Docker) in ~/.zshrc wins over .env;
 * Prisma then still points at 5433. In development, merge env files the same way Next
 * does and use that URL for the client.
 */
function parseEnvFile(contents: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of contents.split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const eq = t.indexOf("=");
    if (eq === -1) continue;
    const key = t.slice(0, eq).trim();
    let val = t.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    out[key] = val;
  }
  return out;
}

function mergedEnvFromProjectFiles(): Record<string, string> {
  const root = process.cwd();
  const names = [".env.development.local", ".env.local", ".env.development", ".env"];
  const merged: Record<string, string> = {};
  for (const name of names) {
    try {
      const raw = fs.readFileSync(path.join(root, name), "utf8");
      const parsed = parseEnvFile(raw);
      for (const [k, v] of Object.entries(parsed)) {
        if (merged[k] === undefined) merged[k] = v;
      }
    } catch (e) {
      if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
    }
  }
  return merged;
}

function resolveDatabaseUrl(): string {
  const fileEnv =
    process.env.NODE_ENV === "development" ? mergedEnvFromProjectFiles() : undefined;
  const url =
    fileEnv?.["INVESTBEST_DATABASE_URL"]?.trim() ||
    process.env.INVESTBEST_DATABASE_URL?.trim() ||
    fileEnv?.["DATABASE_URL"]?.trim() ||
    process.env.DATABASE_URL?.trim();
  if (!url) {
    throw new Error(
      "DATABASE_URL is not set. Add DATABASE_URL to apps/web/.env (or INVESTBEST_DATABASE_URL to override).",
    );
  }
  return url;
}

export const prisma =
  globalForPrisma.prisma ??
  new PrismaClient({
    log: process.env.NODE_ENV === "development" ? ["error", "warn"] : ["error"],
    datasources: { db: { url: resolveDatabaseUrl() } },
  });

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
