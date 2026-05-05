"""InvestBest scoring service — Build Spec §833+, Milestone 2 stub."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="InvestBest ML Service", version="0.1.0")


class FeatureRow(BaseModel):
    symbol: str
    features: dict[str, float] = Field(default_factory=dict)


class BatchScoreRequest(BaseModel):
    model_version: str = "stub-v0"
    rows: list[FeatureRow]


class BatchScoreResponse(BaseModel):
    scores: list[dict]


@app.get("/health")
def health():
    return {"status": "ok", "service": "investbest-ml"}


@app.post("/score/batch")
def score_batch(body: BatchScoreRequest):
    """Placeholder: return neutral scores until LightGBM models are trained."""
    out = []
    for r in body.rows:
        out.append(
            {
                "symbol": r.symbol,
                "buy_score": 50.0,
                "sell_risk_score": 40.0,
                "expected_return_5d": 0.0,
                "expected_drawdown_risk_5d": 0.0,
                "confidence_score": 50.0,
            }
        )
    return BatchScoreResponse(scores=out)


@app.post("/train/buy-model")
def train_buy():
    raise HTTPException(status_code=501, detail="Training pipeline not implemented in container yet")


@app.post("/train/sell-model")
def train_sell():
    raise HTTPException(status_code=501, detail="Training pipeline not implemented in container yet")


@app.post("/backtest/run")
def backtest_run():
    raise HTTPException(status_code=501, detail="Use Python backtests/walk_forward when added")
