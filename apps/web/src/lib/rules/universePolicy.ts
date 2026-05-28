import {
  isDefensiveMacroTicker,
  isLeadershipGrowthTicker,
} from "@/lib/constants/universe";
import type { MarketRegime } from "@/lib/portfolio/marketRegime";

export type LongUniversePolicyResult = {
  adjustedBuyScore: number;
  blocked: boolean;
  blockedReason: string | null;
  note: string | null;
};

function clampScore(n: number): number {
  return Math.max(0, Math.min(100, Math.round(n)));
}

/**
 * Regime-aware long-candidate policy.
 *
 * Goals:
 * - stop defensive macro ETFs (IEF/TLT/SHY/TIP/UUP) from crowding out growth names
 *   in bull / neutral tapes
 * - give liquid leadership / software-cloud names more weight in risk-on regimes
 */
export function applyLongUniversePolicy(input: {
  ticker: string;
  segmentKey: string | null;
  regime: MarketRegime;
  buyScore: number;
}): LongUniversePolicyResult {
  const { ticker, segmentKey, regime } = input;
  let adjusted = input.buyScore;
  const notes: string[] = [];

  if (isDefensiveMacroTicker(ticker)) {
    if (regime === "bullish") {
      return {
        adjustedBuyScore: clampScore(adjusted - 35),
        blocked: true,
        blockedReason: "regime_segment",
        note: "Blocked defensive macro ETF in bullish regime",
      };
    }
    if (regime === "neutral") {
      adjusted -= 18;
      notes.push("Defensive macro penalty in neutral regime");
    } else {
      adjusted += 8;
      notes.push("Defensive macro tailwind in bearish regime");
    }
  }

  const softwareCloud = segmentKey === "software_cloud";
  const leadershipGrowth = isLeadershipGrowthTicker(ticker);

  if (softwareCloud) {
    if (regime === "bullish") {
      adjusted += 8;
      notes.push("Software/cloud leadership bonus in bullish regime");
    } else if (regime === "neutral") {
      adjusted += 4;
      notes.push("Software/cloud bonus in neutral regime");
    } else {
      adjusted -= 8;
      notes.push("Software/cloud penalty in bearish regime");
    }
  } else if (leadershipGrowth) {
    if (regime === "bullish") {
      adjusted += 6;
      notes.push("Leadership growth bonus in bullish regime");
    } else if (regime === "neutral") {
      adjusted += 3;
      notes.push("Leadership growth bonus in neutral regime");
    } else {
      adjusted -= 6;
      notes.push("Leadership growth penalty in bearish regime");
    }
  }

  return {
    adjustedBuyScore: clampScore(adjusted),
    blocked: false,
    blockedReason: null,
    note: notes.length > 0 ? notes.join("; ") : null,
  };
}
