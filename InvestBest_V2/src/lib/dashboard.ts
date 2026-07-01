import { loadPortfolioState } from "@/lib/paperPortfolio";
import { refreshPortfolioValuation } from "@/lib/simulator";
import type { DashboardSnapshot } from "@/lib/types";

const ACTIVE_MODEL = "regression_v1_manual";

export async function getDashboardSnapshot(): Promise<DashboardSnapshot> {
  const portfolio = await refreshPortfolioValuation(await loadPortfolioState());
  const totalReturnPct = portfolio.startingCash === 0 ? 0 : portfolio.equity / portfolio.startingCash - 1;

  let benchmarkReturnPct: number | null = null;
  if (portfolio.benchmarkStartPrice && portfolio.benchmarkCurrentPrice) {
    benchmarkReturnPct = portfolio.benchmarkCurrentPrice / portfolio.benchmarkStartPrice - 1;
  }

  return {
    portfolio,
    totalReturnPct,
    benchmarkReturnPct,
    activeModel: ACTIVE_MODEL,
  };
}
