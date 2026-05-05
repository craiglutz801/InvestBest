"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function MainSegmentError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[InvestBest]", error.digest ?? "no-digest", error.message, error);
  }, [error]);

  const dbHint =
    /P20\d{2}|column|relation|does not exist|schema|PrismaClientKnownRequestError|Can\'t reach database server|ECONNREFUSED/i.test(
      error.message,
    );

  return (
    <div className="mx-auto max-w-2xl space-y-4 px-4 py-16">
      <h1 className="text-2xl font-semibold tracking-tight">Something went wrong</h1>
      <p className="text-sm leading-relaxed text-muted-foreground">
        This page crashed while rendering on the server. The message below is what Next.js could pass through; for the
        full stack trace, check the terminal where <code className="rounded bg-muted px-1 py-0.5 text-xs">npm run dev</code>{" "}
        or your host logs are running.
      </p>
      {error.digest ? (
        <p className="text-xs text-muted-foreground">
          Reference ID: <span className="font-mono">{error.digest}</span>
        </p>
      ) : null}
      <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-muted/40 p-4 text-sm">
        {error.message || "(no message)"}
      </pre>
      {dbHint ? (
        <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-950 dark:text-amber-100">
          <p className="font-medium">Likely database / schema</p>
          <p className="mt-1 text-xs leading-relaxed opacity-90">
            From <code className="rounded bg-background/60 px-1">apps/web</code> run:{" "}
            <code className="rounded bg-background/60 px-1">npx prisma db push</code> then{" "}
            <code className="rounded bg-background/60 px-1">npm run db:seed</code>. Confirm{" "}
            <code className="rounded bg-background/60 px-1">DATABASE_URL</code> in{" "}
            <code className="rounded bg-background/60 px-1">.env</code> points at a running Postgres.
          </p>
        </div>
      ) : null}
      <div className="flex flex-wrap gap-3">
        <Button type="button" onClick={() => reset()}>
          Try again
        </Button>
        <Button type="button" variant="outline" asChild>
          <a href="/dashboard">Go to dashboard</a>
        </Button>
      </div>
    </div>
  );
}
