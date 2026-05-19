export type RotationCandidate = {
  symbolId: string;
  ticker: string;
  segmentKey: string | null;
  buyScore: number;
  sellRiskScore: number;
  confidenceScore: number;
};

export type RotationHolding = {
  symbolId: string;
  ticker: string;
  segmentKey: string | null;
  buyScore: number;
  sellRiskScore: number;
  confidenceScore: number;
};

export function pickRotationTarget<T extends RotationHolding>(input: {
  candidate: RotationCandidate;
  holdings: T[];
  minBuyScoreEdge: number;
  weakHoldMaxBuyScore: number;
  minHeldSellRisk: number;
  maxCandidateSellRiskSpread: number;
}): T | null {
  const eligible = input.holdings.filter((holding) => {
    if (holding.symbolId === input.candidate.symbolId) return false;
    if (input.candidate.buyScore < holding.buyScore + input.minBuyScoreEdge) return false;

    const weakEnough =
      holding.sellRiskScore >= input.minHeldSellRisk || holding.buyScore <= input.weakHoldMaxBuyScore;
    if (!weakEnough) return false;

    if (input.candidate.sellRiskScore > holding.sellRiskScore + input.maxCandidateSellRiskSpread) return false;
    return true;
  });

  if (eligible.length === 0) return null;

  eligible.sort((a, b) => {
    if (a.buyScore !== b.buyScore) return a.buyScore - b.buyScore;
    if (a.sellRiskScore !== b.sellRiskScore) return b.sellRiskScore - a.sellRiskScore;
    if (a.confidenceScore !== b.confidenceScore) return a.confidenceScore - b.confidenceScore;
    return a.ticker.localeCompare(b.ticker);
  });
  return eligible[0] ?? null;
}
