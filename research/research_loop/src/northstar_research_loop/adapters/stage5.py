"""Stage 5 robustness / conservative-sizing adapters.

Does not reimplement DSR/PBO/Kelly math. Wraps a native Stage 5 module when
present; otherwise consumes explicit RobustnessDecision / SizingRecommendation
records and applies fail-closed research defaults.
"""

from __future__ import annotations

from typing import Any, Mapping

from northstar_research_loop.adapters.discovery import native_module
from northstar_research_loop.contracts import RobustnessDecision, SizingRecommendation

DEFAULT_PBO_MAX = 0.5
DEFAULT_MIN_TRIALS_FOR_OVERFIT_FLAG = 30
DEFAULT_FRACTIONAL_KELLY_CAP = 0.25


class Stage5RobustnessAdapter:
    def __init__(self) -> None:
        self.module = native_module(5)

    def evaluate(self, evidence: Mapping[str, Any]) -> RobustnessDecision:
        explicit = evidence.get("robustness")
        native = self.module
        if native is not None:
            for attr in ("evaluate_robustness", "promotion_decision", "evaluate"):
                fn = getattr(native, attr, None)
                if callable(fn):
                    return self._wrap(fn(evidence), native.__name__)
        if explicit is None:
            return RobustnessDecision(
                passed=False,
                reason_codes=("rob.missing_stage5_fail_closed",),
                trial_count=0,
                plateau_stable=False,
                holdout_contaminated=True,
                cost_stress_failed=True,
                delay_stress_failed=True,
                concentration_flag=True,
                source_package=None,
            )
        return self._wrap(explicit, native.__name__ if native else "explicit_evidence")

    def _wrap(self, payload: Any, source: str | None) -> RobustnessDecision:
        if isinstance(payload, RobustnessDecision):
            decision = payload
        else:
            data = dict(payload) if isinstance(payload, Mapping) else {}
            decision = RobustnessDecision(
                passed=bool(data.get("passed")),
                reason_codes=tuple(data.get("reason_codes") or ()),
                trial_count=int(data.get("trial_count") or 0),
                plateau_stable=bool(data.get("plateau_stable")),
                holdout_contaminated=bool(data.get("holdout_contaminated")),
                cost_stress_failed=bool(data.get("cost_stress_failed")),
                delay_stress_failed=bool(data.get("delay_stress_failed")),
                concentration_flag=bool(data.get("concentration_flag")),
                deflated_sharpe=data.get("deflated_sharpe"),
                pbo=data.get("pbo"),
                source_package=source,
                details=dict(data.get("details") or {}),
            )
        reasons = list(decision.reason_codes)
        passed = decision.passed
        if decision.holdout_contaminated:
            passed = False
            reasons.append("rob.holdout_contaminated")
        if decision.cost_stress_failed:
            passed = False
            reasons.append("rob.cost_stress_failed")
        if decision.delay_stress_failed:
            passed = False
            reasons.append("rob.delay_stress_failed")
        if not decision.plateau_stable:
            passed = False
            reasons.append("rob.unstable_parameter_peak")
        pbo = decision.pbo
        if pbo is not None and float(pbo) > DEFAULT_PBO_MAX:
            passed = False
            reasons.append("rob.pbo_above_threshold")
        if decision.trial_count >= DEFAULT_MIN_TRIALS_FOR_OVERFIT_FLAG and not decision.plateau_stable:
            passed = False
            reasons.append("rob.multiple_testing_overfit")
        if decision.concentration_flag:
            # Surface concentration; configurable veto via evidence.
            reasons.append("rob.concentrated_pnl")
            if bool(decision.details.get("concentration_veto", True)):
                passed = False
        if passed and not reasons:
            reasons.append("rob.ok")
        return RobustnessDecision(
            passed=passed,
            reason_codes=tuple(dict.fromkeys(reasons)),
            trial_count=decision.trial_count,
            plateau_stable=decision.plateau_stable,
            holdout_contaminated=decision.holdout_contaminated,
            cost_stress_failed=decision.cost_stress_failed,
            delay_stress_failed=decision.delay_stress_failed,
            concentration_flag=decision.concentration_flag,
            deflated_sharpe=decision.deflated_sharpe,
            pbo=decision.pbo,
            source_package=decision.source_package or source,
            details=decision.details,
        )


class Stage5SizingAdapter:
    def __init__(self) -> None:
        self.module = native_module(5)

    def evaluate(self, evidence: Mapping[str, Any]) -> SizingRecommendation:
        explicit = evidence.get("sizing")
        native = self.module
        if native is not None:
            for attr in ("kelly_ceiling", "sizing_recommendation", "fractional_kelly_ceiling"):
                fn = getattr(native, attr, None)
                if callable(fn):
                    return self._wrap(fn(evidence), native.__name__)
        if explicit is None:
            return SizingRecommendation(
                fractional_kelly_ceiling=0.0,
                applied_caps={"missing_stage5": 0.0},
                reason_codes=("size.missing_stage5_fail_closed",),
                subordinate_to_risk_governor=True,
                source_package=None,
            )
        return self._wrap(explicit, native.__name__ if native else "explicit_evidence")

    @staticmethod
    def _wrap(payload: Any, source: str | None) -> SizingRecommendation:
        if isinstance(payload, SizingRecommendation):
            rec = payload
        else:
            data = dict(payload) if isinstance(payload, Mapping) else {}
            rec = SizingRecommendation(
                fractional_kelly_ceiling=float(data.get("fractional_kelly_ceiling") or 0.0),
                applied_caps=dict(data.get("applied_caps") or {}),
                reason_codes=tuple(data.get("reason_codes") or ()),
                subordinate_to_risk_governor=bool(
                    data.get("subordinate_to_risk_governor", True)
                ),
                source_package=source,
            )
        ceiling = rec.fractional_kelly_ceiling
        reasons = list(rec.reason_codes)
        caps = dict(rec.applied_caps)
        hard_cap = float(caps.get("hard_risk_cap", DEFAULT_FRACTIONAL_KELLY_CAP))
        vol_cap = float(caps.get("vol_target_cap", 1.0))
        dd_cap = float(caps.get("drawdown_cap", 1.0))
        exposure_cap = float(caps.get("exposure_cap", 1.0))
        liquidity_cap = float(caps.get("liquidity_cap", 1.0))
        health_mult = float(caps.get("health_advisory_multiplier", 1.0))
        if ceiling != ceiling or ceiling < 0:
            ceiling = 0.0
            reasons.append("size.invalid_ceiling_fail_closed")
        # Never a full-Kelly target; clamp to configured fractional/hard caps.
        for name, cap in (
            ("hard_risk_cap", hard_cap),
            ("vol_target_cap", vol_cap),
            ("drawdown_cap", dd_cap),
            ("exposure_cap", exposure_cap),
            ("liquidity_cap", liquidity_cap),
            ("health_advisory_multiplier", health_mult),
            ("fractional_kelly_cap", DEFAULT_FRACTIONAL_KELLY_CAP),
        ):
            if ceiling > cap:
                ceiling = cap
                reasons.append(f"size.clamped_by_{name}")
        if not rec.subordinate_to_risk_governor:
            ceiling = 0.0
            reasons.append("size.must_remain_subordinate_to_risk_governor")
        if ceiling >= 1.0:
            ceiling = DEFAULT_FRACTIONAL_KELLY_CAP
            reasons.append("size.full_kelly_forbidden")
        caps["final_ceiling"] = ceiling
        caps["risk_governor_authoritative"] = 1.0
        if not reasons:
            reasons.append("size.ok")
        return SizingRecommendation(
            fractional_kelly_ceiling=float(ceiling),
            applied_caps=caps,
            reason_codes=tuple(dict.fromkeys(reasons)),
            subordinate_to_risk_governor=True,
            source_package=rec.source_package or source,
        )
