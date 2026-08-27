"""Build native Stage 2–5 typed objects for the integrated harness.

These helpers call the real package constructors. They are not synthetic
stand-ins for engine *outputs*.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

import numpy as np

from northstar_diagnostics.efr import FrictionInputs
from northstar_edge_health.config import HealthConfig, HysteresisConfig
from northstar_edge_health.evidence import MeanReversionEvidence
from northstar_edge_health.schema import StrategyIdentity
from northstar_mean_reversion.types import MeanReversionEligibilityConfig
from northstar_mean_reversion.universe import EconomicCandidate, RelationshipKind
from northstar_promotion.concentration import trade_pnl_concentration
from northstar_promotion.dsr import deflated_sharpe_ratio
from northstar_promotion.holdout import audit_holdout, seal_holdout
from northstar_promotion.kelly import RiskCapBundle, kelly_ceiling
from northstar_promotion.neighborhood import ParameterPoint, evaluate_plateau
from northstar_promotion.pbo import probability_of_backtest_overfitting
from northstar_promotion.promotion import PromotionConfig, PromotionEvidence
from northstar_promotion.registry import ExperimentRegistry
from northstar_promotion.splits import evaluate_walk_forward, walk_forward_splits
from northstar_promotion.stress import cost_stress, execution_delay_stress
from northstar_trend_carry.fixtures import uptrend_series

N = 240
AS_OF = datetime(2026, 1, 15, tzinfo=timezone.utc)
MR_IDENTITY = StrategyIdentity(
    strategy_family="mean_reversion",
    strategy_id="mr_cadf_residual",
    instrument_id="PAIR:KO-PEP",
    horizon="5d",
)


def ar1(n: int, phi: float, seed: int, scale: float = 0.3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    e = rng.normal(0.0, scale, size=n)
    y = np.zeros(n, dtype=float)
    for t in range(1, n):
        y[t] = phi * y[t - 1] + e[t]
    return y


def random_walk(n: int, seed: int) -> np.ndarray:
    return np.cumsum(np.random.default_rng(seed).normal(0.0, 1.0, size=n))


def cointegrated_pair(n: int = N, seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    x = random_walk(n, seed=seed)
    resid = ar1(n, phi=0.4, seed=seed + 1, scale=0.3)
    return 2.0 * x + resid, x


def independent_walks(n: int = N, seed: int = 2) -> tuple[np.ndarray, np.ndarray]:
    y = random_walk(n, seed=seed)
    x = np.cumsum(np.random.default_rng(seed + 7).normal(0.0, 1.0, size=n) + 0.2)
    return y, x


def cheap_friction() -> FrictionInputs:
    return FrictionInputs(
        commission=0.002,
        spread=0.003,
        slippage=0.002,
        market_impact=0.001,
        borrow_fees=0.001,
        other=0.001,
    )


def expensive_friction() -> FrictionInputs:
    return FrictionInputs(
        commission=0.02,
        spread=0.03,
        slippage=0.02,
        market_impact=0.02,
        borrow_fees=0.01,
        other=0.01,
    )


def mr_config() -> MeanReversionEligibilityConfig:
    return MeanReversionEligibilityConfig(
        min_obs=40,
        rolling_window=40,
        rolling_step=10,
        hedge_beta_relative_std_max=0.75,
        spread_vol_cv_max=1.25,
        half_life_max_multiple_of_horizon=8.0,
        half_life_min_fraction_of_horizon=0.01,
        efr_min=2.5,
        structural_break_method="cusum_ols_resid",
    )


def pair_candidate(
    y: np.ndarray,
    x: np.ndarray,
    *,
    friction: FrictionInputs | None = None,
    expected_gross_edge: float = 0.05,
    candidate_id: str = "KO-PEP",
) -> EconomicCandidate:
    from northstar_mean_reversion.liquidity import LiquiditySnapshot

    symbols = ("KO", "PEP")
    liquidity = {
        symbol: LiquiditySnapshot(
            symbol=symbol,
            as_of=AS_OF,
            adv=5_000_000,
            spread_bps=4.0,
            shortable=True,
            locate_available=True,
            borrow_fee_rate=0.01,
        )
        for symbol in symbols
    }
    return EconomicCandidate(
        candidate_id=candidate_id,
        symbols=symbols,
        relationship_kind=RelationshipKind.SECTOR_PEERS,
        relationship_rationale="Large-cap beverage peers with overlapping demand and input costs",
        legs={"KO": y, "PEP": x},
        holding_horizon=10.0,
        as_of=AS_OF,
        expected_gross_edge=expected_gross_edge,
        friction=friction if friction is not None else cheap_friction(),
        liquidity=liquidity,
    )


def instant_health_config() -> HealthConfig:
    return HealthConfig(
        hysteresis=HysteresisConfig(
            degraded_confirmations=1,
            paused_confirmations=1,
            retire_confirmations=8,
            recovery_confirmations=1,
            cooldown_observations=1,
        )
    )


def healthy_mr_evidence(*, break_detected: bool = False) -> MeanReversionEvidence:
    return MeanReversionEvidence(
        as_of=AS_OF,
        rolling_adf_pvalues=(0.01, 0.02, 0.01, 0.015),
        rolling_adf_reject_fraction=1.0,
        rolling_cadf_pvalues=(0.01, 0.02, 0.01),
        rolling_cadf_reject_fraction=1.0,
        half_life=10.0,
        half_life_baseline=10.0,
        hedge_ratio=1.00,
        hedge_ratio_baseline=1.00,
        residual_volatility=0.02,
        residual_volatility_baseline=0.02,
        convergence_rate=0.06931471805599453,
        convergence_rate_baseline=0.06931471805599453,
        structural_break_detected=break_detected,
        realized_friction=0.0010,
        expected_friction=0.0010,
        usable=True,
        source="harness",
    )


def _plateau(*, spike: bool) -> Any:
    if spike:
        points = [
            ParameterPoint("p4", {"lookback": 4.0}, 0.10),
            ParameterPoint("p5", {"lookback": 5.0}, 2.00),
            ParameterPoint("p6", {"lookback": 6.0}, 0.10),
            ParameterPoint("p1", {"lookback": 1.0}, 0.10),
            ParameterPoint("p9", {"lookback": 9.0}, 0.10),
        ]
    else:
        points = [
            ParameterPoint("p4", {"lookback": 4.0}, 0.95),
            ParameterPoint("p5", {"lookback": 5.0}, 1.00),
            ParameterPoint("p6", {"lookback": 6.0}, 0.96),
            ParameterPoint("p1", {"lookback": 1.0}, 0.10),
            ParameterPoint("p9", {"lookback": 9.0}, 0.10),
        ]
    return evaluate_plateau(points, selected_trial_id="p5", radius=0.3, min_neighbors=2)


def _registry(n_trials: int, experiment_id: str) -> ExperimentRegistry:
    reg = ExperimentRegistry()
    reg.register_experiment(experiment_id, strategy_family="mean_reversion")
    for i in range(n_trials):
        outcome = "fail" if i < n_trials - 1 else "pass"
        reg.record_trial(
            trial_id=f"t{i}",
            experiment_id=experiment_id,
            strategy_family="mean_reversion",
            parameters={"lookback": float(i + 1)},
            outcome=outcome,
        )
    return reg


def noisy_edge_matrix(n_obs: int, n_noise: int, *, edge_mu: float, seed: int) -> np.ndarray:
    g = np.random.default_rng(seed)
    edge = g.normal(edge_mu, 0.02, size=n_obs)
    noise = g.normal(0.0, 0.02, size=(n_obs, n_noise))
    return np.column_stack([edge, noise])


def promotion_bundle(
    *,
    experiment_id: str,
    overfit: bool = False,
) -> tuple[PromotionEvidence, np.ndarray, PromotionConfig]:
    n_trials = 240 if overfit else 3
    rets = np.random.default_rng(3).normal(0.004, 0.01, size=250)
    reg = _registry(n_trials, experiment_id)
    contract = seal_holdout(250, holdout_size=40, embargo_bars=2, min_research_bars=30, min_holdout_bars=10)
    if overfit:
        reg.record_trial(
            trial_id="peek",
            experiment_id=experiment_id,
            strategy_family="mean_reversion",
            parameters={"lookback": 99.0},
            outcome="peek",
            used_holdout=True,
        )
    audit = audit_holdout(
        contract,
        list(reg.trials_for(experiment_id)),
        holdout_score=0.3,
        min_holdout_score=0.0,
    )
    splits, sflags = walk_forward_splits(
        contract.research.length, train_size=40, test_size=10, step=10, min_folds=3
    )
    wf = evaluate_walk_forward(splits, [0.2] * len(splits), min_oos_score=0.0, split_flags=sflags)
    dsr = deflated_sharpe_ratio(rets, n_trials=n_trials)
    edge_mu = 0.001 if overfit else 0.03
    pbo = probability_of_backtest_overfitting(
        noisy_edge_matrix(240, 4, edge_mu=edge_mu, seed=9 if not overfit else 11),
        n_slices=6,
    )
    conc = trade_pnl_concentration(np.linspace(0.1, 0.3, 12), min_trades=5)
    g = np.random.default_rng(0)
    gross = 0.02 + g.normal(0.0, 0.003, 80)
    costs = np.full(80, 0.001)
    cost = cost_stress(gross, costs, min_sharpe=0.0)
    asset = 0.01 + g.normal(0.0, 0.004, 80)
    pos = np.ones(80)
    delay = execution_delay_stress(asset, pos, delay_bars=(0, 1), min_sharpe=0.0)
    kelly = kelly_ceiling(
        rets,
        fraction=0.25,
        min_obs=30,
        caps=RiskCapBundle(
            risk_governor_cap=0.2,
            hard_leverage_cap=0.5,
            concentration_max_weight=0.3,
        ),
    )
    evidence = PromotionEvidence(
        experiment_id=experiment_id,
        candidate_trial_id=f"t{n_trials - 1}",
        registry=reg,
        n_obs=250,
        dsr=dsr,
        pbo=pbo,
        plateau=_plateau(spike=overfit),
        holdout=audit,
        cost_stress=cost,
        delay_stress=delay,
        concentration=conc,
        walk_forward=wf,
        kelly=kelly,
    )
    cfg = PromotionConfig()
    return evidence, rets, cfg


Kind = Literal["good", "overfit", "high_friction", "broken", "invalid"]


def evidence_for(kind: Kind, experiment_id: str) -> dict[str, Any]:
    if kind == "invalid":
        y, x = independent_walks()
        friction = cheap_friction()
        edge = 0.05
    elif kind == "high_friction":
        y, x = cointegrated_pair()
        friction = expensive_friction()
        edge = 0.004
    else:
        y, x = cointegrated_pair()
        friction = cheap_friction()
        edge = 0.05

    promo, rets, promo_cfg = promotion_bundle(
        experiment_id=experiment_id,
        overfit=(kind == "overfit"),
    )
    payload: dict[str, Any] = {
        "y": y,
        "x": x,
        "expected_gross_edge": edge,
        "friction": friction.as_dict(),
        "as_of": AS_OF,
        "mean_reversion_candidate": pair_candidate(y, x, friction=friction, expected_gross_edge=edge),
        "mean_reversion_config": mr_config(),
        "price_series": uptrend_series(n=400, seed=11, symbol="UP"),
        "performance_sweep": {21: 0.11, 63: 0.10, 126: 0.09, 252: 0.08},
        "health_evidence": healthy_mr_evidence(break_detected=(kind == "broken")),
        "health_identity": MR_IDENTITY,
        "health_config": instant_health_config(),
        "promotion_evidence": promo,
        "promotion_config": promo_cfg,
        "sizing_returns": rets,
        "sizing_caps": {
            "risk_governor_cap": 0.2,
            "hard_leverage_cap": 0.5,
            "concentration_max_weight": 0.3,
        },
        "family": "mean_reversion",
    }
    if kind == "high_friction":
        payload["friction_stress"] = {"efr_plus_50": 0.4, "efr_plus_100": 0.3}
    else:
        payload["friction_stress"] = {"efr_plus_50": 4.0, "efr_plus_100": 3.0}
    return payload
