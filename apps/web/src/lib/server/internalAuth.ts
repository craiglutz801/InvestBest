import type { NextRequest } from "next/server";

/**
 * Internal cron / scheduler auth.
 *
 * Strategy Upgrade §1.2 / §4.2 — internal scheduler endpoints (`hourly-run`,
 * `scheduler-tick`) require a shared secret so random users can't trigger the
 * agent. We accept several header forms for compatibility:
 *
 *   - `Authorization: Bearer <secret>`        (Vercel Cron format)
 *   - `x-investbest-secret: <secret>`         (legacy header used by older cron entries)
 *   - `x-internal-cron-secret: <secret>`      (header named in the upgrade spec)
 *
 * Secret resolution order: `INVESTBEST_INTERNAL_SECRET`, `INTERNAL_CRON_SECRET`,
 * `CRON_SECRET`, `TRIGGER_SECRET_KEY`. In non-production builds, requests are
 * accepted with no secret configured to keep local dev frictionless.
 */
export function internalAuthorized(req: NextRequest): boolean {
  const secret =
    process.env.INVESTBEST_INTERNAL_SECRET ??
    process.env.INTERNAL_CRON_SECRET ??
    process.env.CRON_SECRET ??
    process.env.TRIGGER_SECRET_KEY;
  if (!secret) {
    return process.env.NODE_ENV !== "production";
  }
  const auth = req.headers.get("authorization");
  const bearer = auth?.startsWith("Bearer ") ? auth.slice(7).trim() : null;
  const headerLegacy = req.headers.get("x-investbest-secret");
  const headerSpec = req.headers.get("x-internal-cron-secret");
  return bearer === secret || headerLegacy === secret || headerSpec === secret;
}
