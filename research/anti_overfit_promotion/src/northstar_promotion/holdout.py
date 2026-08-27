"""Untouched final holdout contract and contamination audit.

The holdout region is sealed at construction. Research trials must not use
observations at or after ``holdout.start_index``. Any trial window that
touches the holdout, or any metric computed with ``used_holdout=True``
before the holdout is explicitly evaluated as holdout, is contamination.

Fail-closed: contamination or an unsealed contract cannot promote.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from northstar_promotion.arrays import has_fail
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag
from northstar_promotion.registry import TrialRecord
from northstar_promotion.schema import TimeWindow, make_meta


@dataclass(frozen=True)
class HoldoutContract:
    n_obs: int
    research: TimeWindow
    embargo: TimeWindow
    holdout: TimeWindow
    sealed: bool
    quality_flags: tuple[QualityFlag, ...]

    @property
    def is_usable(self) -> bool:
        return self.sealed and not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "n_obs": self.n_obs,
            "research": self.research.to_dict(),
            "embargo": self.embargo.to_dict(),
            "holdout": self.holdout.to_dict(),
            "sealed": self.sealed,
            "is_usable": self.is_usable,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
        }


def seal_holdout(
    n_obs: int,
    *,
    holdout_size: int | None = None,
    holdout_fraction: float = 0.2,
    embargo_bars: int = 0,
    min_research_bars: int = 30,
    min_holdout_bars: int = 10,
) -> HoldoutContract:
    flags: list[QualityFlag] = []
    if n_obs < 1:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "n_obs must be >= 1."))
        empty = TimeWindow(0, 0, "empty")
        return HoldoutContract(n_obs, empty, empty, empty, False, tuple(flags))
    if embargo_bars < 0:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "embargo_bars must be >= 0."))
        empty = TimeWindow(0, 0, "empty")
        return HoldoutContract(n_obs, empty, empty, empty, False, tuple(flags))

    if holdout_size is None:
        if not (0.0 < holdout_fraction < 1.0):
            flags.append(fail_flag(QualityCode.INVALID_INPUT, "holdout_fraction must be in (0, 1)."))
            empty = TimeWindow(0, 0, "empty")
            return HoldoutContract(n_obs, empty, empty, empty, False, tuple(flags))
        holdout_size = int(round(n_obs * holdout_fraction))

    if holdout_size < min_holdout_bars:
        flags.append(
            fail_flag(
                QualityCode.SHORT_SAMPLE,
                f"Holdout size {holdout_size} < min_holdout_bars {min_holdout_bars}.",
            )
        )
    holdout_start = n_obs - holdout_size
    embargo_start = max(0, holdout_start - embargo_bars)
    research_end = embargo_start
    if research_end < min_research_bars:
        flags.append(
            fail_flag(
                QualityCode.SHORT_SAMPLE,
                f"Research window length {research_end} < min_research_bars {min_research_bars}.",
            )
        )
    if holdout_start < 0 or holdout_start >= n_obs:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "Holdout does not fit inside the sample."))

    sealed = not has_fail(flags)
    if sealed:
        flags.append(ok_flag("Holdout sealed. Research trials must not observe this region."))
    research = TimeWindow(0, max(research_end, 0), "research")
    embargo = TimeWindow(research.end_index, max(holdout_start, research.end_index), "embargo")
    holdout = TimeWindow(max(holdout_start, 0), n_obs, "holdout")
    return HoldoutContract(
        n_obs=n_obs,
        research=research,
        embargo=embargo,
        holdout=holdout,
        sealed=sealed,
        quality_flags=tuple(flags),
    )


@dataclass(frozen=True)
class HoldoutAudit:
    contract: HoldoutContract
    contaminated_trial_ids: tuple[str, ...]
    quality_flags: tuple[QualityFlag, ...]
    holdout_score: float | None
    holdout_passed: bool | None
    meta: dict

    @property
    def is_contaminated(self) -> bool:
        return len(self.contaminated_trial_ids) > 0 or any(
            f.code == QualityCode.HOLDOUT_CONTAMINATION for f in self.quality_flags
        )

    @property
    def is_usable(self) -> bool:
        return (
            self.contract.is_usable
            and not self.is_contaminated
            and not has_fail(self.quality_flags)
        )

    def to_dict(self) -> dict:
        return {
            "contract": self.contract.to_dict(),
            "contaminated_trial_ids": list(self.contaminated_trial_ids),
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "holdout_score": self.holdout_score,
            "holdout_passed": self.holdout_passed,
            "is_contaminated": self.is_contaminated,
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def _window_touches_holdout(window: TimeWindow | None, contract: HoldoutContract) -> bool:
    if window is None:
        return False
    return window.end_index > contract.holdout.start_index and window.start_index < contract.holdout.end_index


def audit_holdout(
    contract: HoldoutContract,
    trials: Sequence[TrialRecord],
    *,
    holdout_score: float | None = None,
    min_holdout_score: float | None = None,
    research_as_of_index: int | None = None,
) -> HoldoutAudit:
    flags: list[QualityFlag] = list(contract.quality_flags)
    contaminated: list[str] = []
    if not contract.sealed:
        flags.append(
            fail_flag(
                QualityCode.HOLDOUT_NOT_SEALED,
                "Holdout contract is not sealed; promotion is fail-closed.",
            )
        )

    for trial in trials:
        touches = _window_touches_holdout(trial.window, contract)
        used = bool(trial.used_holdout)
        as_of_violation = (
            trial.as_of_index is not None and trial.as_of_index >= contract.holdout.start_index
        )
        if touches or used or as_of_violation:
            contaminated.append(trial.trial_id)
            flags.append(
                fail_flag(
                    QualityCode.HOLDOUT_CONTAMINATION,
                    f"Trial {trial.trial_id!r} used holdout information "
                    f"(window_touch={touches}, used_holdout={used}, as_of_violation={as_of_violation}).",
                )
            )

    if research_as_of_index is not None and research_as_of_index >= contract.holdout.start_index:
        flags.append(
            fail_flag(
                QualityCode.POINT_IN_TIME_VIOLATION,
                "Research as_of_index is inside the sealed holdout.",
            )
        )

    holdout_passed: bool | None = None
    if min_holdout_score is not None:
        if holdout_score is None or holdout_score != holdout_score:
            flags.append(
                fail_flag(QualityCode.MISSING_DATA, "Holdout score missing; cannot confirm untouched OOS.")
            )
            holdout_passed = False
        else:
            holdout_passed = bool(holdout_score >= min_holdout_score)
            if not holdout_passed:
                flags.append(
                    fail_flag(
                        QualityCode.HOLDOUT_SCORE_BELOW_THRESHOLD,
                        f"Holdout score {holdout_score} < min_holdout_score {min_holdout_score}.",
                    )
                )

    if not contaminated and contract.sealed and not has_fail(flags):
        flags.append(ok_flag("No holdout contamination detected among supplied trials."))

    meta = make_meta(
        method="untouched_final_holdout_audit",
        parameters={
            "min_holdout_score": min_holdout_score,
            "research_as_of_index": research_as_of_index,
            "n_trials_audited": len(trials),
        },
        assumptions=(
            "Holdout bars are unused during parameter search, formation, and walk-forward.",
            "Embargo bars sit between research and holdout to reduce leakage from overlapping labels.",
            "used_holdout=True on a trial is treated as contamination even without an explicit window.",
        ),
        quality_flags=tuple(flags),
    )
    # Convert holdout_score_below_threshold to FAIL if we appended a string code incorrectly.
    # The fail_flag above uses a custom code; that is intentional and FAIL level.
    return HoldoutAudit(
        contract=contract,
        contaminated_trial_ids=tuple(contaminated),
        quality_flags=tuple(flags),
        holdout_score=holdout_score,
        holdout_passed=holdout_passed,
        meta=meta.to_dict(),
    )
