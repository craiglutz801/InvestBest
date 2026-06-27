import { NextResponse } from "next/server";
import { resetPortfolioState } from "@/lib/paperPortfolio";

export const dynamic = "force-dynamic";

export async function POST() {
  const state = await resetPortfolioState();
  return NextResponse.json({ ok: true, portfolio: state });
}
