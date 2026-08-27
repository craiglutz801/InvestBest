"""Stage 5 adapters — explicit northstar_promotion API.

Robustness calls ``evaluate_promotion(evidence, config=...)``.
Sizing calls ``kelly_ceiling(returns, *, caps=...)``.

Health's advisory multiplier is applied once after the native ceiling.
Missing ``risk_governor_cap`` fails closed at 0; it is not defaulted to 0.2.
"""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.contracts import RobustnessDecision, SizingRecommendation


class Stage5RobustnessAdapter:
    def __init__(self) -> None:
        try:
            from northstar_promotion import evaluate_promotion
            from northstar_promotion.promotion import (
                PromotionEvidence,
                PromotionVerdict,
            )
        except ImportError:
            self.evaluate_promotion = None
            self.PromotionEvidence = None
            self.PromotionVerdict = None
            self.source_package = None
        else:
            self.evaluate_promotion = evaluate_promotion
            self.PromotionEvidence = PromotionEvidence
            self.PromotionVerdict = PromotionVerdict
            self.source_package = "northstar_promotion"

    def evaluate(self, evidence: Mapping[str, Any]) -> RobustnessDecision:
        if self.evaluate_promotion is None:
            return RobustnessDecision(
                passed=False,
                reason_codes=("rob.stage5_unavailable_fail_closed",),
                trial_count=0,
                plateau_stable=False,
                holdout_contaminated=True,
                cost_stress_failed=True,
                delay_stress_failed=True,
                concentration_flag=True,
                source_package=None,
            )

        native_evidence = evidence.get("promotion_evidence")
        if native_evidence is None:
            return RobustnessDecision(
                passed=False,
                reason_codes=("rob.missing_promotion_evidence_fail_closed",),
                trial_count=0,
                plateau_stable=False,
                holdout_contaminated=True,
                cost_stress_failed=True,
                delay_stress_failed=True,
                concentration_flag=True,
                source_package=self.source_package,
            )
        if self.PromotionEvidence is not None and not isinstance(native_evidence, self.PromotionEvidence):
            return RobustnessDecision(
                passed=False,
                reason_codes=("rob.evidence_not_promotion_evidence",),
                trial_count=0,
                plateau_stable=False,
                holdout_contaminated=True,
                cost_stress_failed=True,
                delay_stress_failed=True,
                concentration_flag=True,
                source_package=self.source_package,
            )

        decision = self.evaluate_promotion(
            native_evidence,
            config=evidence.get("promotion_config"),
        )
        if self.PromotionVerdict is None:
            return RobustnessDecision(
                passed=False,
                reason_codes=("rob.stage5_unavailable_fail_closed",),
                trial_count=0,
                plateau_stable=False,
                holdout_contaminated=True,
                cost_stress_failed=True,
                delay_stress_failed=True,
                concentration_flag=True,
                source_package=self.source_package,
            )
        passed = decision.verdict is self.PromotionVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
        codes = tuple(item.value for item in decision.reason_codes)
        details = decision.to_dict()
        details["self_promotes_to_live"] = False
        details["activates_trading"] = False
        reason_blob = " ".join(codes).lower()
        dsr = native_evidence.dsr
        pbo = native_evidence.pbo
        return RobustnessDecision(
            passed=passed,
            reason_codes=codes or (("rob.ok",) if passed else ("rob.rejected",)),
            trial_count=int(decision.n_trials),
            plateau_stable="isolated_optimum" not in reason_blob,
            holdout_contaminated="holdout" in reason_blob and "contaminat" in reason_blob,
            cost_stress_failed="cost_stress" in reason_blob,
            delay_stress_failed="delay_stress" in reason_blob or "execution_delay" in reason_blob,
            concentration_flag="concentration" in reason_blob,
            deflated_sharpe=None if dsr is None else dsr.deflated_sharpe,
            pbo=None if pbo is None else pbo.pbo,
            source_package=self.source_package,
            details=details,
        )


class Stage5SizingAdapter:
    def __init__(self) -> None:
        try:
            from northstar_promotion import kelly_ceiling
            from northstar_promotion.kelly import RiskCapBundle
        except ImportError:
            self.kelly_ceiling = None
            self.RiskCapBundle = None
            self.source_package = None
        else:
            self.kelly_ceiling = kelly_ceiling
            self.RiskCapBundle = RiskCapBundle
            self.source_package = "northstar_promotion"

    def evaluate(self, evidence: Mapping[str, Any]) -> SizingRecommendation:
        if self.kelly_ceiling is None:
            return SizingRecommendation(
                fractional_kelly_ceiling=0.0,
                applied_caps={"missing_stage5": 0.0},
                reason_codes=("size.stage5_unavailable_fail_closed",),
                subordinate_to_risk_governor=True,
                source_package=None,
            )

        returns = evidence.get("sizing_returns")
        if returns is None:
            return SizingRecommendation(
                fractional_kelly_ceiling=0.0,
                applied_caps={"missing_returns": 0.0},
                reason_codes=("size.missing_returns_fail_closed",),
                subordinate_to_risk_governor=True,
                source_package=self.source_package,
            )

        raw_caps = dict(evidence.get("sizing_caps") or {})
        health_mult = float(raw_caps.pop("health_advisory_multiplier", 1.0))
        governor = raw_caps.get("risk_governor_cap")
        if governor is None:
            return SizingRecommendation(
                fractional_kelly_ceiling=0.0,
                applied_caps={"risk_governor_cap": 0.0, "health_advisory_multiplier": health_mult},
                reason_codes=("size.missing_risk_governor_cap_fail_closed",),
                subordinate_to_risk_governor=True,
                source_package=self.source_package,
            )

        caps = None
        if self.RiskCapBundle is not None:
            allowed = {
                "vol_target",
                "asset_vol",
                "concentration_max_weight",
                "drawdown_throttle",
                "exposure_cap",
                "liquidity_cap",
                "risk_governor_cap",
                "hard_leverage_cap",
            }
            # Health is applied once after kelly_ceiling. Do not also inject it as
            # drawdown_throttle — kelly_ceiling already multiplies by that field.
            kwargs = {k: v for k, v in raw_caps.items() if k in allowed}
            caps = self.RiskCapBundle(**kwargs)

        result = self.kelly_ceiling(
            returns,
            fraction=float(evidence.get("kelly_fraction", 0.25)),
            caps=caps,
            min_obs=int(evidence.get("kelly_min_obs", 30)),
        )
        ceiling = float(result.ceiling)
        if health_mult <= 0:
            ceiling = 0.0
        elif health_mult < 1.0:
            ceiling = ceiling * health_mult
        reasons = tuple(flag.code for flag in result.quality_flags)
        if not reasons:
            reasons = ("size.ok",)
        applied = dict(result.binding_caps or {})
        applied["final_ceiling"] = ceiling
        applied["health_advisory_multiplier"] = health_mult
        applied["health_applied_once"] = 1.0
        applied["risk_governor_cap"] = float(governor)
        applied["risk_governor_authoritative"] = 1.0
        applied["role"] = result.role
        return SizingRecommendation(
            fractional_kelly_ceiling=ceiling,
            applied_caps=applied,
            reason_codes=reasons,
            subordinate_to_risk_governor=True,
            source_package=self.source_package,
        )
