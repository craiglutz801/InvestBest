import { NextResponse } from "next/server";
import { runScheduledSimulation } from "@/lib/simulator";

export const dynamic = "force-dynamic";

function cronAuthorized(request: Request): boolean {
  const secret = process.env.CRON_SECRET?.trim();

  if (!secret) {
    return true;
  }

  return request.headers.get("authorization") === `Bearer ${secret}`;
}

async function handleScheduledRun() {
  try {
    const state = await runScheduledSimulation();
    return NextResponse.json({ ok: true, portfolio: state });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Scheduled simulation failed";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}

export async function GET(request: Request) {
  if (!cronAuthorized(request)) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }

  return handleScheduledRun();
}

export async function POST(request: Request) {
  if (!cronAuthorized(request)) {
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  }

  return handleScheduledRun();
}
