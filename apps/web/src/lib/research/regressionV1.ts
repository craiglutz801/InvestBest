export type RegressionFeatureVector = {
  ret1d: number;
  ret5d: number;
  ret20d: number;
  distSma20: number;
  distSma50: number;
  rsi14: number;
  vol20: number;
  volSpike: boolean;
};

export type RegressionTrainingRow = {
  symbolId: string;
  ticker: string;
  segmentKey: string | null;
  featureTimestamp: string;
  marketTimestamp: string;
  baseClose: number;
  ret1d: number;
  ret5d: number;
  ret20d: number;
  distSma20: number;
  distSma50: number;
  rsi14: number;
  vol20: number;
  volSpike: boolean;
  lookaheadBars: number;
  targetClose: number;
  targetReturn: number;
  downsideReturn: number;
  downsideHit: boolean;
};

export type RegressionPrediction = {
  expectedReturn5d: number;
  downsideProbability5d: number;
  driverLines: string[];
};

type Coefficients = {
  intercept: number;
  ret1d: number;
  ret5d: number;
  ret20d: number;
  distSma20: number;
  distSma50: number;
  rsiCentered: number;
  rsiStretch: number;
  vol20: number;
  volSpike: number;
};

export type RegressionModelV1 = {
  modelVersion: string;
  lookaheadBars: number;
  returnModel: Coefficients;
  downsideModel: Coefficients;
};

/**
 * Seeded transparent linear baseline for InvestBest v2.
 * This is intentionally simple so it can be replaced by walk-forward-trained
 * coefficients once the research/export loop is in place.
 */
export const DEFAULT_REGRESSION_V1_MODEL: RegressionModelV1 = {
  modelVersion: "regression-v1-seeded",
  lookaheadBars: 5,
  returnModel: {
    intercept: 0.001,
    ret1d: 0.06,
    ret5d: 0.34,
    ret20d: 0.42,
    distSma20: 0.09,
    distSma50: 0.05,
    rsiCentered: 0.012,
    rsiStretch: -0.018,
    vol20: -0.07,
    volSpike: -0.008,
  },
  downsideModel: {
    intercept: -1.45,
    ret1d: -0.45,
    ret5d: -1.15,
    ret20d: -1.05,
    distSma20: -0.85,
    distSma50: -0.6,
    rsiCentered: -0.22,
    rsiStretch: 0.65,
    vol20: 2.35,
    volSpike: 0.35,
  },
};

function logistic(x: number): number {
  return 1 / (1 + Math.exp(-x));
}

function transformed(f: RegressionFeatureVector) {
  return {
    ret1d: f.ret1d,
    ret5d: f.ret5d,
    ret20d: f.ret20d,
    distSma20: f.distSma20,
    distSma50: f.distSma50,
    rsiCentered: (f.rsi14 - 50) / 50,
    rsiStretch: Math.max(0, (f.rsi14 - 72) / 28),
    vol20: f.vol20,
    volSpike: f.volSpike ? 1 : 0,
  };
}

function linear(coeffs: Coefficients, f: ReturnType<typeof transformed>): number {
  return (
    coeffs.intercept +
    coeffs.ret1d * f.ret1d +
    coeffs.ret5d * f.ret5d +
    coeffs.ret20d * f.ret20d +
    coeffs.distSma20 * f.distSma20 +
    coeffs.distSma50 * f.distSma50 +
    coeffs.rsiCentered * f.rsiCentered +
    coeffs.rsiStretch * f.rsiStretch +
    coeffs.vol20 * f.vol20 +
    coeffs.volSpike * f.volSpike
  );
}

export function predictRegressionV1(
  features: RegressionFeatureVector,
  model: RegressionModelV1 = DEFAULT_REGRESSION_V1_MODEL,
): RegressionPrediction {
  const tf = transformed(features);
  const expectedReturn5d = linear(model.returnModel, tf);
  const downsideProbability5d = logistic(linear(model.downsideModel, tf));
  const driverLines = [
    `Seeded regression prior · E[r+5d]=${(expectedReturn5d * 100).toFixed(2)}%`,
    `Downside prob=${(downsideProbability5d * 100).toFixed(1)}%`,
    `Inputs: 5d ${(features.ret5d * 100).toFixed(1)}% · 20d ${(features.ret20d * 100).toFixed(1)}% · RSI ${features.rsi14.toFixed(1)} · Vol ${(features.vol20 * 100).toFixed(0)}%`,
  ];

  return { expectedReturn5d, downsideProbability5d, driverLines };
}

export function computeForwardTargets(baseClose: number, forwardCloses: number[]) {
  if (!Number.isFinite(baseClose) || baseClose <= 0) {
    throw new Error("baseClose must be a positive finite number");
  }
  if (forwardCloses.length === 0) {
    throw new Error("forwardCloses must include at least one close");
  }
  const targetClose = forwardCloses[forwardCloses.length - 1]!;
  const minClose = Math.min(...forwardCloses);
  const targetReturn = (targetClose - baseClose) / baseClose;
  const downsideReturn = Math.min(0, (minClose - baseClose) / baseClose);
  return {
    targetClose,
    targetReturn,
    downsideReturn,
    downsideHit: downsideReturn < 0,
  };
}
