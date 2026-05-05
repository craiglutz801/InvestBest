import { Prisma } from "@prisma/client";
import { prisma } from "@/lib/db";

const DEMO_EMAIL = process.env.INVESTBEST_DEMO_EMAIL ?? "demo@investbest.local";

const GENERIC_DB_HINT =
  "Check DATABASE_URL in apps/web/.env, start Postgres, then: npx prisma db push && npm run db:seed";

function prismaFacingHint(e: unknown): string | null {
  if (e instanceof Prisma.PrismaClientInitializationError) {
    return "Cannot initialize Prisma (often DATABASE_URL missing or DB unreachable). " + GENERIC_DB_HINT;
  }
  if (e instanceof Prisma.PrismaClientKnownRequestError) {
    if (["P2021", "P2022", "P2010"].includes(e.code)) {
      return `Prisma ${e.code}: database schema is out of date vs this app version. In apps/web run: npx prisma db push && npm run db:seed`;
    }
    if (["P1001", "P1003", "P1017"].includes(e.code)) {
      return `Prisma ${e.code}: cannot reach the database server. Verify DATABASE_URL and that Postgres is listening.`;
    }
  }
  return null;
}

export async function requireDefaultUser() {
  try {
    const user = await prisma.user.findUnique({ where: { email: DEMO_EMAIL } });
    if (!user) {
      throw new Error(
        `No demo user yet. In apps/web run: npx prisma db push && npm run db:seed (expects DATABASE_URL in .env)`,
      );
    }
    return user;
  } catch (e) {
    if (e instanceof Error && e.message.includes("No demo user yet")) throw e;
    const specific = prismaFacingHint(e);
    const msg = e instanceof Error ? e.message : String(e);
    throw new Error(specific ? `${msg}\n\n${specific}` : `${msg}\n\n${GENERIC_DB_HINT}`);
  }
}

export function demoEmail() {
  return DEMO_EMAIL;
}
