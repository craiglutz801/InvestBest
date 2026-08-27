"""Fail-closed promotion decision.

The only non-reject verdict is ``eligible_for_human_review``. This module
never activates paper or live trading, never sizes orders, and never
self-promotes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

from northstar_promotion.arrays import has_fail
from northstar_promotion.concentration import ConcentrationReport
from northstar_promotion.dsr import DSRResult
from northstar_promotion.holdout import HoldoutAudit
from northstar_promotion.kelly import KellyCeilingResult
from northstar_promotion.neighborhood import PlateauReport
from northstar_promotion.pbo import PBOResult
from northstar_promotion.quality import QualityCode, QualityFlag, QualityLevel, ReasonCode, fail_flag
from northstar_promotion.regimes import RegimeSliceReport
from northstar_promotion.registry import ExperimentRegistry
from northstar_promotion.schema import jsonable, make_meta
from northstar_promotion.splits import WalkForwardReport
from northstar_promotion.stress import StressReport


class PromotionVerdict(str, Enum):
    REJECT = "reject"
    ELIGIBLE_FOR_HUMAN_REVIEW = "eligible_for_human_review"


@dataclass(frozen=True)
class PromotionConfig:
    min_dsr: float = 0.5
    max_pbo: float = 0.5
    min_sample_obs: int = 30
    max_trials_before_extra_haircut: int | None = None
    require_sealed_holdout: bool = True
    require_holdout_pass: bool = True
    require_plateau: bool = True
    require_dsr: bool = True
    require_pbo: bool = True
    require_cost_stress: bool = True
    require_delay_stress: bool = True
    require_walk_forward: bool = True
    require_kelly_ceiling: bool = True
    require_shadow_forward: bool = False
    concentration_veto: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "min_dsr": self.min_dsr,
            "max_pbo": self.max_pbo,
            "min_sample_obs": self.min_sample_obs,
            "max_trials_before_extra_haircut": self.max_trials_before_extra_haircut,
            "require_sealed_holdout": self.require_sealed_holdout,
            "require_holdout_pass": self.require_holdout_pass,
            "require_plateau": self.require_plateau,
            "require_dsr": self.require_dsr,
            "require_pbo": self.require_pbo,
            "require_cost_stress": self.require_cost_stress,
            "require_delay_stress": self.require_delay_stress,
            "require_walk_forward": self.require_walk_forward,
            "require_kelly_ceiling": self.require_kelly_ceiling,
            "require_shadow_forward": self.require_shadow_forward,
            "concentration_veto": self.concentration_veto,
        }


@dataclass(frozen=True)
class PromotionEvidence:
    experiment_id: str
    candidate_trial_id: str
    registry: ExperimentRegistry
    n_obs: int | None = None
    dsr: DSRResult | None = None
    pbo: PBOResult | None = None
    plateau: PlateauReport | None = None
    holdout: HoldoutAudit | None = None
    cost_stress: StressReport | None = None
    delay_stress: StressReport | None = None
    concentration: ConcentrationReport | None = None
    walk_forward: WalkForwardReport | None = None
    regime_slices: RegimeSliceReport | None = None
    kelly: KellyCeilingResult | None = None
    shadow_forward_complete: bool = False
    extra_flags: tuple[QualityFlag, ...] = ()


@dataclass(frozen=True)
class PromotionDecision:
    verdict: PromotionVerdict
    reason_codes: tuple[ReasonCode, ...]
    experiment_id: str
    candidate_trial_id: str
    n_trials: int
    trial_count_confidence_haircut: float
    quality_flags: tuple[QualityFlag, ...]
    notes: tuple[str, ...]
    details: Mapping[str, Any] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @property
    def eligible_for_human_review(self) -> bool:
        return self.verdict is PromotionVerdict.ELIGIBLE_FOR_HUMAN_REVIEW

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "reason_codes": [r.value for r in self.reason_codes],
            "experiment_id": self.experiment_id,
            "candidate_trial_id": self.candidate_trial_id,
            "n_trials": self.n_trials,
            "trial_count_confidence_haircut": self.trial_count_confidence_haircut,
            "eligible_for_human_review": self.eligible_for_human_review,
            "activates_trading": False,
            "self_promotes": False,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "notes": list(self.notes),
            "details": jsonable(self.details),
            "meta": self.meta,
        }


def _missing(code: ReasonCode, flags: list[QualityFlag], reasons: list[ReasonCode], msg: str) -> None:
    flags.append(fail_flag(QualityCode.MISSING_REQUIRED_EVIDENCE, msg))
    reasons.append(code)


def evaluate_promotion(
    evidence: PromotionEvidence,
    config: PromotionConfig | None = None,
) -> PromotionDecision:
    config = config or PromotionConfig()
    flags: list[QualityFlag] = list(evidence.extra_flags)
    reasons: list[ReasonCode] = []
    notes: list[str] = [
        "Verdict eligible_for_human_review is not paper or live activation.",
        "Failed experiments remain in the registry; they are not dropped.",
        "Kelly, if present, is a ceiling subordinate to hard risk caps.",
    ]

    n_trials = evidence.registry.trial_count(evidence.experiment_id)
    if n_trials < 1:
        flags.append(
            fail_flag(
                QualityCode.INSUFFICIENT_TRIALS,
                "No trials recorded. Unknown search breadth is fail-closed.",
            )
        )
        reasons.append(ReasonCode.MISSING_REQUIRED_EVIDENCE)

    # Multiple trials reduce promotion confidence: haircut = 1/sqrt(n_trials).
    haircut = float("nan")
    if n_trials >= 1:
        import math

        haircut = float(1.0 / math.sqrt(n_trials))
        notes.append(
            f"Trial-count confidence haircut = 1/sqrt(n_trials) = {haircut:.6f} with n_trials={n_trials}."
        )

    if evidence.n_obs is not None and evidence.n_obs < config.min_sample_obs:
        flags.append(
            fail_flag(
                QualityCode.SHORT_SAMPLE,
                f"n_obs={evidence.n_obs} < min_sample_obs={config.min_sample_obs}.",
            )
        )
        reasons.append(ReasonCode.INSUFFICIENT_SAMPLE)

    if config.require_dsr:
        if evidence.dsr is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "DSR result is required.")
        else:
            flags.extend(evidence.dsr.quality_flags)
            if not evidence.dsr.is_usable:
                reasons.append(ReasonCode.MULTIPLE_TESTING_FAIL)
            elif evidence.dsr.deflated_sharpe < config.min_dsr:
                flags.append(
                    fail_flag(
                        "dsr_below_threshold",
                        f"DSR {evidence.dsr.deflated_sharpe} < min_dsr {config.min_dsr} "
                        f"(n_trials={evidence.dsr.n_trials}).",
                    )
                )
                reasons.append(ReasonCode.DSR_BELOW_THRESHOLD)

    if config.require_pbo:
        if evidence.pbo is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "PBO/CSCV result is required.")
        else:
            flags.extend(evidence.pbo.quality_flags)
            if not evidence.pbo.is_usable:
                reasons.append(ReasonCode.MULTIPLE_TESTING_FAIL)
            elif evidence.pbo.pbo > config.max_pbo:
                flags.append(
                    fail_flag(
                        "pbo_above_threshold",
                        f"PBO {evidence.pbo.pbo} > max_pbo {config.max_pbo}.",
                    )
                )
                reasons.append(ReasonCode.PBO_ABOVE_THRESHOLD)

    if config.require_plateau:
        if evidence.plateau is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "Plateau/neighborhood result is required.")
        else:
            flags.extend(evidence.plateau.quality_flags)
            if evidence.plateau.isolated_optimum or not evidence.plateau.plateau_pass:
                reasons.append(ReasonCode.ISOLATED_OPTIMUM)
                if not any(f.code == "isolated_optimum" for f in evidence.plateau.quality_flags):
                    flags.append(
                        fail_flag("isolated_optimum", "Parameter neighborhood is not a stable plateau.")
                    )

    if config.require_sealed_holdout:
        if evidence.holdout is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "Holdout audit is required.")
        else:
            flags.extend(evidence.holdout.quality_flags)
            if not evidence.holdout.contract.sealed:
                reasons.append(ReasonCode.HOLDOUT_NOT_SEALED)
            if evidence.holdout.is_contaminated:
                reasons.append(ReasonCode.HOLDOUT_CONTAMINATION)
            if config.require_holdout_pass and evidence.holdout.holdout_passed is False:
                reasons.append(ReasonCode.HOLDOUT_FAIL)

    if config.require_cost_stress:
        if evidence.cost_stress is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "Cost-stress report is required.")
        else:
            flags.extend(evidence.cost_stress.quality_flags)
            if evidence.cost_stress.veto or not evidence.cost_stress.is_usable:
                reasons.append(ReasonCode.COST_STRESS_FAIL)

    if config.require_delay_stress:
        if evidence.delay_stress is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "Execution-delay stress report is required.")
        else:
            flags.extend(evidence.delay_stress.quality_flags)
            if evidence.delay_stress.veto or not evidence.delay_stress.is_usable:
                reasons.append(ReasonCode.DELAY_STRESS_FAIL)

    if config.require_walk_forward:
        if evidence.walk_forward is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "Walk-forward report is required.")
        else:
            flags.extend(evidence.walk_forward.quality_flags)
            if not evidence.walk_forward.is_usable:
                reasons.append(ReasonCode.WALK_FORWARD_FAIL)

    if evidence.regime_slices is not None:
        flags.extend(evidence.regime_slices.quality_flags)
        if evidence.regime_slices.veto or not evidence.regime_slices.is_usable:
            reasons.append(ReasonCode.REGIME_SLICE_FAIL)

    if evidence.concentration is not None:
        flags.extend(evidence.concentration.quality_flags)
        if config.concentration_veto and evidence.concentration.veto:
            reasons.append(ReasonCode.CONCENTRATION_FAIL)
        elif evidence.concentration.top1_share == evidence.concentration.top1_share:
            notes.append(
                f"P&L concentration surfaced: top1_share={evidence.concentration.top1_share:.4f}, "
                f"HHI={evidence.concentration.herfindahl:.4f}."
            )

    if config.require_kelly_ceiling:
        if evidence.kelly is None:
            _missing(ReasonCode.MISSING_REQUIRED_EVIDENCE, flags, reasons, "Kelly ceiling result is required.")
        else:
            flags.extend(evidence.kelly.quality_flags)
            if evidence.kelly.role != "ceiling_not_target":
                flags.append(fail_flag(QualityCode.INVALID_INPUT, "Kelly result is not labeled as a ceiling."))
                reasons.append(ReasonCode.KELLY_INVALID)
            if not evidence.kelly.is_usable:
                reasons.append(ReasonCode.KELLY_INVALID)
            else:
                notes.append(
                    f"Kelly ceiling={evidence.kelly.ceiling} (not a target); "
                    f"full_kelly={evidence.kelly.full_kelly} was not used."
                )

    if config.require_shadow_forward and not evidence.shadow_forward_complete:
        flags.append(
            fail_flag(
                QualityCode.MISSING_REQUIRED_EVIDENCE,
                "Shadow forward testing is required before human review under this config.",
            )
        )
        reasons.append(ReasonCode.SHADOW_FORWARD_REQUIRED)
    elif not evidence.shadow_forward_complete:
        notes.append(
            "Shadow forward testing was not supplied. Research eligibility does not skip live-shadow "
            "before any later paper promotion (out of scope for this package)."
        )

    if (
        config.max_trials_before_extra_haircut is not None
        and n_trials > config.max_trials_before_extra_haircut
    ):
        flags.append(
            fail_flag(
                "trial_count_excessive",
                f"n_trials={n_trials} exceeds configured cap {config.max_trials_before_extra_haircut}.",
            )
        )
        reasons.append(ReasonCode.TRIAL_COUNT_EXCESSIVE)

    # Deduplicate reason codes, preserve order.
    seen: set[ReasonCode] = set()
    uniq_reasons: list[ReasonCode] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq_reasons.append(r)

    failed = bool(uniq_reasons) or has_fail(flags)
    verdict = PromotionVerdict.REJECT if failed else PromotionVerdict.ELIGIBLE_FOR_HUMAN_REVIEW
    if verdict is PromotionVerdict.ELIGIBLE_FOR_HUMAN_REVIEW:
        notes.append("All configured gates passed. Human review is still required. Do not merge, deploy, or trade.")

    meta = make_meta(
        method="fail_closed_promotion_decision",
        parameters=config.to_dict(),
        assumptions=(
            "Default verdict is reject.",
            "eligible_for_human_review never places orders or enables paper/live.",
            "Trial count haircut is 1/sqrt(N) and is informational alongside DSR.",
            "Missing required evidence fails closed.",
        ),
        quality_flags=tuple(flags),
        notes=tuple(notes),
        details={
            "n_trials": n_trials,
            "failed_trial_count": len(evidence.registry.failed_trials(evidence.experiment_id)),
        },
    )
    return PromotionDecision(
        verdict=verdict,
        reason_codes=tuple(uniq_reasons),
        experiment_id=evidence.experiment_id,
        candidate_trial_id=evidence.candidate_trial_id,
        n_trials=n_trials,
        trial_count_confidence_haircut=haircut,
        quality_flags=tuple(flags),
        notes=tuple(notes),
        details={
            "config": config.to_dict(),
            "dsr": None if evidence.dsr is None else evidence.dsr.to_dict(),
            "pbo": None if evidence.pbo is None else evidence.pbo.to_dict(),
            "kelly_ceiling": None if evidence.kelly is None else evidence.kelly.ceiling,
        },
        meta=meta.to_dict(),
    )
