import { jsonError, jsonOk } from "@/lib/api/http";
import { buildRegressionDataset } from "@/lib/research/buildRegressionDataset";
import { internalAuthorized } from "@/lib/server/internalAuth";
import type { NextRequest } from "next/server";

export async function GET(req: NextRequest) {
  if (!internalAuthorized(req)) {
    return jsonError("Unauthorized", 401);
  }

  const url = new URL(req.url);
  const lookaheadBars = Number(url.searchParams.get("lookaheadBars") ?? "5");
  const maxRowsPerSymbol = Number(url.searchParams.get("maxRowsPerSymbol") ?? "250");
  const sinceRaw = url.searchParams.get("since");
  const since =
    sinceRaw && !Number.isNaN(Date.parse(sinceRaw)) ? new Date(sinceRaw) : null;

  const dataset = await buildRegressionDataset({
    lookaheadBars: Number.isFinite(lookaheadBars) ? lookaheadBars : 5,
    maxRowsPerSymbol: Number.isFinite(maxRowsPerSymbol) ? maxRowsPerSymbol : 250,
    since,
  });

  return jsonOk(dataset);
}
