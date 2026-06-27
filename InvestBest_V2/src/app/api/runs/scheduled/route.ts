import { NextResponse } from "next/server";
import { runScheduledSimulation } from "@/lib/simulator";

export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const state = await runScheduledSimulation();
    return NextResponse.json({ ok: true, portfolio: state });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Scheduled simulation failed";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
