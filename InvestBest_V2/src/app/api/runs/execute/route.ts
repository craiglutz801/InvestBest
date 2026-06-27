import { NextResponse } from "next/server";
import { runManualSimulation } from "@/lib/simulator";

export const dynamic = "force-dynamic";

export async function POST() {
  try {
    const state = await runManualSimulation();
    return NextResponse.json({ ok: true, portfolio: state });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Simulation failed";
    return NextResponse.json({ ok: false, error: message }, { status: 500 });
  }
}
