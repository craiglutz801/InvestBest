from __future__ import annotations

import numpy as np

from fixtures import iid_normal, noisy_edge_matrix
from northstar_promotion.concentration import trade_pnl_concentration
from northstar_promotion.dsr import deflated_sharpe_ratio
from northstar_promotion.holdout import audit_holdout, seal_holdout
from northstar_promotion.kelly import RiskCapBundle, kelly_ceiling
from northstar_promotion.neighborhood import ParameterPoint, evaluate_plateau
from northstar_promotion.pbo import probability_of_backtest_overfitting
from northstar_promotion.promotion import (
    PromotionConfig,
    PromotionEvidence,
    PromotionVerdict,
    evaluate_promotion,
)
from northstar_promotion.quality import ReasonCode
from northstar_promotion.registry import ExperimentRegistry
from northstar_promotion.splits import evaluate_walk_forward, walk_forward_splits
from northstar_promotion.stress import cost_stress, execution_delay_stress


def _plateau_pass() -> object:
    points = [
        ParameterPoint("p4", {"lookback": 4.0}, 0.95),
        ParameterPoint("p5", {"lookback": 5.0}, 1.00),
        ParameterPoint("p6", {"lookback": 6.0}, 0.96),
        ParameterPoint("p1", {"lookback": 1.0}, 0.10),
        ParameterPoint("p9", {"lookback": 9.0}, 0.10),
    ]
    return evaluate_plateau(points, selected_trial_id="p5", radius=0.3, min_neighbors=2)


def _plateau_spike() -> object:
    points = [
        ParameterPoint("p4", {"lookback": 4.0}, 0.10),
        ParameterPoint("p5", {"lookback": 5.0}, 2.00),
        ParameterPoint("p6", {"lookback": 6.0}, 0.10),
        ParameterPoint("p1", {"lookback": 1.0}, 0.10),
        ParameterPoint("p9", {"lookback": 9.0}, 0.10),
    ]
    return evaluate_plateau(points, selected_trial_id="p5", radius=0.3, min_neighbors=2)


def _registry(n_trials: int, experiment_id: str = "exp", sharpes: list[float] | None = None) -> ExperimentRegistry:
    reg = ExperimentRegistry()
    reg.register_experiment(experiment_id, strategy_family="toy")
    if sharpes is None:
        sharpes = [0.05 + 0.02 * float(i) for i in range(n_trials)]
    for i in range(n_trials):
        outcome = "fail" if i < n_trials - 1 else "pass"
        reg.record_trial(
            trial_id=f"t{i}",
            experiment_id=experiment_id,
            strategy_family="toy",
            parameters={"lookback": float(i + 1)},
            outcome=outcome,
            metrics={"sharpe": float(sharpes[i])},
        )
    return reg


def _passing_bundle(n_trials: int = 3):
    rets = iid_normal(250, mu=0.004, sigma=0.01, seed=3)
    reg = _registry(n_trials)
    contract = seal_holdout(250, holdout_size=40, embargo_bars=2, min_research_bars=30, min_holdout_bars=10)
    audit = audit_holdout(
        contract,
        [t for t in reg.trials_for("exp") if t.window is None],
        holdout_score=0.3,
        min_holdout_score=0.0,
    )
    # Windows were None so they do not touch holdout; used_holdout defaults False.
    splits, sflags = walk_forward_splits(contract.research.length, train_size=40, test_size=10, step=10, min_folds=3)
    wf = evaluate_walk_forward(splits, [0.2] * len(splits), min_oos_score=0.0, split_flags=sflags)
    trial_sharpes, _ = reg.trial_sharpes("exp")
    dsr = deflated_sharpe_ratio(
        rets,
        n_trials=n_trials,
        trial_sharpes=trial_sharpes if n_trials > 1 else None,
    )
    pbo = probability_of_backtest_overfitting(
        noisy_edge_matrix(240, 4, edge_mu=0.03, seed=9), n_slices=6
    )
    kelly = kelly_ceiling(
        rets,
        fraction=0.25,
        min_obs=30,
        caps=RiskCapBundle(risk_governor_cap=0.2, hard_leverage_cap=0.5, concentration_max_weight=0.3),
    )
    conc = trade_pnl_concentration(np.linspace(0.1, 0.3, 12), min_trades=5)
    g = np.random.default_rng(0)
    gross = 0.02 + g.normal(0.0, 0.003, 80)
    costs = np.full(80, 0.001)
    cost = cost_stress(gross, costs, min_sharpe=0.0)
    asset = 0.01 + g.normal(0.0, 0.004, 80)
    pos = np.ones(80)
    delay = execution_delay_stress(asset, pos, delay_bars=(0, 1), min_sharpe=0.0)
    evidence = PromotionEvidence(
        experiment_id="exp",
        candidate_trial_id=f"t{n_trials - 1}",
        registry=reg,
        n_obs=250,
        dsr=dsr,
        pbo=pbo,
        plateau=_plateau_pass(),
        holdout=audit,
        cost_stress=cost,
        delay_stress=delay,
        concentration=conc,
        walk_forward=wf,
        kelly=kelly,
    )
    return evidence


def test_passing_gates_are_human_review_not_self_promotion():
    decision = evaluate_promotion(_passing_bundle(n_trials=3))
    assert decision.verdict is PromotionVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert decision.reason_codes == ()
    payload = decision.to_dict()
    assert payload["activates_trading"] is False
    assert payload["self_promotes"] is False
    assert "human review" in " ".join(decision.notes).lower()


def test_multiple_trials_reduce_promotion_confidence_and_can_veto_dsr():
    rets = iid_normal(250, mu=0.0008, sigma=0.01, seed=3)
    dsr_few = deflated_sharpe_ratio(rets, n_trials=1)
    many_sharpes = np.random.default_rng(3).normal(0.0, 0.08, size=400)
    dsr_many = deflated_sharpe_ratio(rets, n_trials=400, trial_sharpes=many_sharpes)
    assert dsr_few.deflated_sharpe > dsr_many.deflated_sharpe
    assert dsr_few.deflated_sharpe >= 0.85
    assert dsr_many.deflated_sharpe < 0.85

    few = _passing_bundle(n_trials=1)
    # Rebuild evidence with explicit DSR objects.
    few = PromotionEvidence(
        **{**few.__dict__, "dsr": dsr_few, "registry": _registry(1), "candidate_trial_id": "t0"}
    )
    many_reg = _registry(400, sharpes=list(many_sharpes))
    many = PromotionEvidence(
        **{**few.__dict__, "dsr": dsr_many, "registry": many_reg, "candidate_trial_id": "t399", "experiment_id": "exp"}
    )
    cfg = PromotionConfig(min_dsr=0.85, require_pbo=True)
    d_few = evaluate_promotion(few, cfg)
    d_many = evaluate_promotion(many, cfg)
    assert d_few.trial_count_confidence_haircut > d_many.trial_count_confidence_haircut
    assert d_few.verdict is PromotionVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    assert d_many.verdict is PromotionVerdict.REJECT
    assert ReasonCode.DSR_BELOW_THRESHOLD in d_many.reason_codes


def test_isolated_optimum_rejects():
    evidence = _passing_bundle()
    evidence = PromotionEvidence(**{**evidence.__dict__, "plateau": _plateau_spike()})
    decision = evaluate_promotion(evidence)
    assert decision.verdict is PromotionVerdict.REJECT
    assert ReasonCode.ISOLATED_OPTIMUM in decision.reason_codes


def test_holdout_contamination_rejects():
    evidence = _passing_bundle()
    contract = evidence.holdout.contract
    evidence.registry.record_trial(
        trial_id="peek",
        experiment_id="exp",
        strategy_family="toy",
        outcome="pass",
        used_holdout=True,
        window=contract.holdout,
    )
    dirty = audit_holdout(contract, evidence.registry.trials_for("exp"), holdout_score=0.3, min_holdout_score=0.0)
    evidence = PromotionEvidence(**{**evidence.__dict__, "holdout": dirty})
    decision = evaluate_promotion(evidence)
    assert decision.verdict is PromotionVerdict.REJECT
    assert ReasonCode.HOLDOUT_CONTAMINATION in decision.reason_codes


def test_cost_stress_veto_rejects_otherwise_attractive_candidate():
    evidence = _passing_bundle()
    g = np.random.default_rng(0)
    gross = 0.012 + g.normal(0.0, 0.002, 80)
    costs = np.full(80, 0.008)
    stressed = cost_stress(gross, costs, min_sharpe=0.0)
    evidence = PromotionEvidence(**{**evidence.__dict__, "cost_stress": stressed})
    decision = evaluate_promotion(evidence)
    assert decision.verdict is PromotionVerdict.REJECT
    assert ReasonCode.COST_STRESS_FAIL in decision.reason_codes


def test_delay_stress_veto_rejects():
    evidence = _passing_bundle()
    asset = np.zeros(60)
    asset[10] = 0.5
    asset[11] = -0.4
    pos = np.zeros(60)
    pos[10] = 1.0
    stressed = execution_delay_stress(asset, pos, delay_bars=(0, 1), min_sharpe=0.0)
    evidence = PromotionEvidence(**{**evidence.__dict__, "delay_stress": stressed})
    decision = evaluate_promotion(evidence)
    assert decision.verdict is PromotionVerdict.REJECT
    assert ReasonCode.DELAY_STRESS_FAIL in decision.reason_codes


def test_missing_required_evidence_fails_closed():
    reg = _registry(2)
    evidence = PromotionEvidence(
        experiment_id="exp",
        candidate_trial_id="t1",
        registry=reg,
        n_obs=10,
    )
    decision = evaluate_promotion(evidence)
    assert decision.verdict is PromotionVerdict.REJECT
    assert ReasonCode.MISSING_REQUIRED_EVIDENCE in decision.reason_codes
    assert ReasonCode.INSUFFICIENT_SAMPLE in decision.reason_codes


def test_empty_registry_fails_closed():
    evidence = PromotionEvidence(
        experiment_id="missing",
        candidate_trial_id="none",
        registry=ExperimentRegistry(),
    )
    cfg = PromotionConfig(
        require_dsr=False,
        require_pbo=False,
        require_plateau=False,
        require_sealed_holdout=False,
        require_cost_stress=False,
        require_delay_stress=False,
        require_walk_forward=False,
        require_kelly_ceiling=False,
    )
    decision = evaluate_promotion(evidence, cfg)
    assert decision.verdict is PromotionVerdict.REJECT
    assert ReasonCode.MISSING_REQUIRED_EVIDENCE in decision.reason_codes
