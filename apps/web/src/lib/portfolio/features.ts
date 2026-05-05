import type { OhlcvBar } from "@/lib/data-provider/twelveData";

export type FeatureVector = {
  ret1d: number;
  ret5d: number;
  ret20d: number;
  distSma20: number;
  distSma50: number;
  rsi14: number;
  vol20: number;
  volSpike: boolean;
};

function sma(values: number[], window: number): number | null {
  if (values.length < window) return null;
  const slice = values.slice(-window);
  return slice.reduce((a, b) => a + b, 0) / window;
}

function rsi(closes: number[], period = 14): number | null {
  if (closes.length < period + 1) return null;
  let gains = 0;
  let losses = 0;
  for (let i = closes.length - period; i < closes.length; i++) {
    const ch = closes[i] - closes[i - 1];
    if (ch >= 0) gains += ch;
    else losses -= ch;
  }
  const avgGain = gains / period;
  const avgLoss = losses / period;
  if (avgLoss === 0) return 100;
  const rs = avgGain / avgLoss;
  return 100 - 100 / (1 + rs);
}

function stdDev(values: number[]): number {
  if (values.length < 2) return 0;
  const m = values.reduce((a, b) => a + b, 0) / values.length;
  return Math.sqrt(values.reduce((s, v) => s + (v - m) ** 2, 0) / values.length);
}

/** Log returns from closes */
export function computeFeatures(bars: OhlcvBar[]): { features: FeatureVector; completeness: number } {
  const closes = bars.map((b) => b.close);
  const vols = bars.map((b) => b.volume);
  if (closes.length < 22) {
    return {
      features: {
        ret1d: 0,
        ret5d: 0,
        ret20d: 0,
        distSma20: 0,
        distSma50: 0,
        rsi14: 50,
        vol20: 0,
        volSpike: false,
      },
      completeness: closes.length / 50,
    };
  }

  const ret1d = (closes.at(-1)! - closes.at(-2)!) / closes.at(-2)!;
  const ret5d = (closes.at(-1)! - closes.at(-6)!) / closes.at(-6)!;
  const ret20d = (closes.at(-1)! - closes.at(-21)!) / closes.at(-21)!;
  const s20 = sma(closes, 20);
  const s50 = sma(closes, Math.min(50, closes.length));
  const last = closes.at(-1)!;
  const distSma20 = s20 ? (last - s20) / s20 : 0;
  const distSma50 = s50 ? (last - s50) / s50 : 0;
  const rsi14 = rsi(closes, 14) ?? 50;
  const recent = closes.slice(-21, -1);
  const rets = recent.slice(1).map((c, i) => Math.log(c / recent[i]));
  const vol20 = stdDev(rets) * Math.sqrt(252) || 0;
  const volMa = vols.slice(-20).reduce((a, b) => a + b, 0) / 20;
  const volSpike = volMa > 0 && (vols.at(-1) ?? 0) > volMa * 2;

  return {
    features: {
      ret1d,
      ret5d,
      ret20d,
      distSma20,
      distSma50,
      rsi14,
      vol20,
      volSpike,
    },
    completeness: Math.min(1, closes.length / 60),
  };
}

export type ScoreBreakdown = {
  buyFactors: string[];
  sellRiskFactors: string[];
  confidenceFactors: string[];
  featureSummary: string;
};

/** Rules-based buy/sell scores (Milestone 1). ML replaces later. */
export function rulesScores(f: FeatureVector): {
  buyScore: number;
  sellRiskScore: number;
  confidenceScore: number;
  expectedReturn5d: number;
  expectedDrawdownRisk5d: number;
  breakdown: ScoreBreakdown;
} {
  const buyFactors: string[] = [];
  const sellRiskFactors: string[] = [];
  const confidenceFactors: string[] = [];

  let buy = 50;
  if (f.ret5d > 0 && f.ret20d > 0) {
    buy += 15;
    buyFactors.push(`+15 positive momentum (5d ${(f.ret5d * 100).toFixed(1)}%, 20d ${(f.ret20d * 100).toFixed(1)}%)`);
  } else {
    buyFactors.push(`+0 momentum neutral/negative (5d ${(f.ret5d * 100).toFixed(1)}%, 20d ${(f.ret20d * 100).toFixed(1)}%)`);
  }
  if (f.distSma20 > 0 && f.distSma50 > 0) {
    buy += 10;
    buyFactors.push(`+10 price above SMA20 (+${(f.distSma20 * 100).toFixed(1)}%) and SMA50 (+${(f.distSma50 * 100).toFixed(1)}%)`);
  } else {
    buyFactors.push(`+0 not above both SMAs (SMA20 ${(f.distSma20 * 100).toFixed(1)}%, SMA50 ${(f.distSma50 * 100).toFixed(1)}%)`);
  }
  if (f.rsi14 > 35 && f.rsi14 < 70) {
    buy += 10;
    buyFactors.push(`+10 RSI in healthy range (${f.rsi14.toFixed(1)})`);
  }
  if (f.rsi14 >= 75) {
    buy -= 25;
    buyFactors.push(`-25 RSI overbought (${f.rsi14.toFixed(1)})`);
  }
  if (f.volSpike) {
    buy -= 15;
    buyFactors.push("-15 unusual volume spike (>2x 20-day avg)");
  }
  if (f.vol20 > 0.35) {
    buy -= 10;
    buyFactors.push(`-10 high volatility (${(f.vol20 * 100).toFixed(0)}% annualized)`);
  }

  buy = Math.max(0, Math.min(100, buy));

  let sellRisk = 30;
  if (f.ret5d < -0.03) {
    sellRisk += 20;
    sellRiskFactors.push(`+20 weak 5d return (${(f.ret5d * 100).toFixed(1)}%)`);
  }
  if (f.rsi14 > 80) {
    sellRisk += 15;
    sellRiskFactors.push(`+15 RSI overextended (${f.rsi14.toFixed(1)})`);
  }
  if (f.distSma20 < -0.05) {
    sellRisk += 20;
    sellRiskFactors.push(`+20 price well below SMA20 (${(f.distSma20 * 100).toFixed(1)}%)`);
  }
  if (f.volSpike && f.ret1d < 0) {
    sellRisk += 15;
    sellRiskFactors.push(`+15 volume spike on down day (1d ${(f.ret1d * 100).toFixed(1)}%)`);
  }
  if (sellRiskFactors.length === 0) {
    sellRiskFactors.push("No elevated risk signals");
  }
  sellRisk = Math.max(0, Math.min(100, sellRisk));

  let conf = 40;
  confidenceFactors.push("Base: 40 (minimum data quality)");
  if (f.vol20 < 0.25) {
    conf += 20;
    confidenceFactors.push(`+20 low volatility (${(f.vol20 * 100).toFixed(0)}% < 25%): signals more reliable`);
  } else {
    confidenceFactors.push(`+0 elevated volatility (${(f.vol20 * 100).toFixed(0)}%): noisier signals`);
  }
  if (f.rsi14 > 0 && f.rsi14 < 100) {
    conf += 20;
    confidenceFactors.push("+20 RSI well-defined (sufficient price history)");
  } else {
    confidenceFactors.push("+0 RSI at extreme/undefined — data may be incomplete");
  }
  const confidenceScore = Math.min(100, Math.round(conf));

  const featureSummary = [
    `RSI ${f.rsi14.toFixed(1)}`,
    `Vol ${(f.vol20 * 100).toFixed(0)}%`,
    `5d ${(f.ret5d * 100).toFixed(1)}%`,
    `20d ${(f.ret20d * 100).toFixed(1)}%`,
    `SMA20 ${f.distSma20 >= 0 ? "+" : ""}${(f.distSma20 * 100).toFixed(1)}%`,
    f.volSpike ? "VolSpike" : null,
  ].filter(Boolean).join(" | ");

  return {
    buyScore: Math.round(buy),
    sellRiskScore: Math.round(sellRisk),
    confidenceScore,
    expectedReturn5d: f.ret5d,
    expectedDrawdownRisk5d: Math.min(1, f.vol20),
    breakdown: { buyFactors, sellRiskFactors, confidenceFactors, featureSummary },
  };
}

export type BearScoreBreakdown = {
  bearFactors: string[];
  featureSummary: string;
};

/** Rules-based bearish / short conviction from the same feature vector as long scores. */
export function bearScores(f: FeatureVector): { bearScore: number; breakdown: BearScoreBreakdown } {
  const bearFactors: string[] = [];
  let bear = 48;

  if (f.ret5d < 0 && f.ret20d < 0) {
    bear += 18;
    bearFactors.push(
      `+18 weak momentum (5d ${(f.ret5d * 100).toFixed(1)}%, 20d ${(f.ret20d * 100).toFixed(1)}%)`,
    );
  } else {
    bearFactors.push(
      `+0 momentum not both negative (5d ${(f.ret5d * 100).toFixed(1)}%, 20d ${(f.ret20d * 100).toFixed(1)}%)`,
    );
  }

  if (f.ret5d > 0.025 && f.ret20d > 0.04) {
    bear -= 28;
    bearFactors.push("-28 strong uptrend — avoid short");
  }

  if (f.distSma20 < -0.02 && f.distSma50 <= 0.01) {
    bear += 12;
    bearFactors.push(`+12 trading below SMA20 (${(f.distSma20 * 100).toFixed(1)}%) with weak SMA50`);
  }

  if (f.distSma20 > 0.12) {
    bear -= 15;
    bearFactors.push(`-15 stretched above SMA20 (${(f.distSma20 * 100).toFixed(1)}%) — squeeze risk`);
  }

  if (f.rsi14 > 62 && f.rsi14 < 82) {
    bear += 10;
    bearFactors.push(`+10 RSI elevated (${f.rsi14.toFixed(1)})`);
  }
  if (f.rsi14 < 32) {
    bear -= 22;
    bearFactors.push(`-22 RSI oversold (${f.rsi14.toFixed(1)}) — exhaustion`);
  }

  if (f.volSpike && f.ret1d < 0) {
    bear += 8;
    bearFactors.push(`+8 volume spike on down day (1d ${(f.ret1d * 100).toFixed(1)}%)`);
  }

  if (f.vol20 > 0.52) {
    bear -= 10;
    bearFactors.push(`-10 very high vol (${(f.vol20 * 100).toFixed(0)}% ann.) — noisy`);
  }

  bear = Math.max(0, Math.min(100, Math.round(bear)));

  const featureSummary = [
    `Bear ${bear}`,
    `RSI ${f.rsi14.toFixed(1)}`,
    `Vol ${(f.vol20 * 100).toFixed(0)}%`,
    `5d ${(f.ret5d * 100).toFixed(1)}%`,
    `20d ${(f.ret20d * 100).toFixed(1)}%`,
    `SMA20 ${f.distSma20 >= 0 ? "+" : ""}${(f.distSma20 * 100).toFixed(1)}%`,
  ].join(" | ");

  return {
    bearScore: bear,
    breakdown: { bearFactors, featureSummary },
  };
}
