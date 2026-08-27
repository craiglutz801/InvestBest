"""Walk-forward split utilities and multiple formation windows.

Windows are half-open ``[start, end)`` index ranges. If a sealed holdout
contract is supplied, splits are clipped so they never enter the holdout
region. Point-in-time formation windows end at ``as_of_index`` (exclusive
of later bars).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

from northstar_promotion.arrays import has_fail
from northstar_promotion.holdout import HoldoutContract
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag, warn_flag
from northstar_promotion.schema import TimeWindow, make_meta


@dataclass(frozen=True)
class WalkForwardSplit:
    fold_id: int
    train: TimeWindow
    test: TimeWindow
    embargo: TimeWindow | None = None

    def to_dict(self) -> dict:
        return {
            "fold_id": self.fold_id,
            "train": self.train.to_dict(),
            "test": self.test.to_dict(),
            "embargo": None if self.embargo is None else self.embargo.to_dict(),
        }


def _research_end(n_obs: int, holdout: HoldoutContract | None) -> tuple[int, tuple[QualityFlag, ...]]:
    flags: list[QualityFlag] = []
    if holdout is None:
        return n_obs, ()
    if not holdout.sealed:
        flags.append(
            fail_flag(
                QualityCode.HOLDOUT_NOT_SEALED,
                "Unsealed holdout cannot be used to bound walk-forward splits.",
            )
        )
        return n_obs, tuple(flags)
    return holdout.research.end_index, tuple(flags)


def formation_windows(
    n_obs: int,
    lengths: Sequence[int],
    *,
    as_of_index: int | None = None,
    holdout: HoldoutContract | None = None,
    min_length: int = 2,
) -> tuple[tuple[TimeWindow, ...], tuple[QualityFlag, ...]]:
    """Point-in-time formation windows of several lengths, all ending at as_of."""
    flags: list[QualityFlag] = []
    if n_obs < 1:
        return (), (fail_flag(QualityCode.INVALID_INPUT, "n_obs must be >= 1."),)
    end, bound_flags = _research_end(n_obs, holdout)
    flags.extend(bound_flags)
    if has_fail(flags):
        return (), tuple(flags)
    if as_of_index is None:
        as_of_end = end
    else:
        if as_of_index < 0:
            flags.append(fail_flag(QualityCode.INVALID_INPUT, "as_of_index must be >= 0."))
            return (), tuple(flags)
        as_of_end = min(as_of_index, end)
        if holdout is not None and as_of_index > holdout.research.end_index:
            flags.append(
                fail_flag(
                    QualityCode.POINT_IN_TIME_VIOLATION,
                    "as_of_index is beyond the sealed research region.",
                )
            )
            return (), tuple(flags)

    windows: list[TimeWindow] = []
    for length in lengths:
        if int(length) < min_length:
            flags.append(
                warn_flag(
                    QualityCode.SHORT_SAMPLE,
                    f"Skipping formation length {length} < min_length {min_length}.",
                )
            )
            continue
        start = as_of_end - int(length)
        if start < 0:
            flags.append(
                warn_flag(
                    QualityCode.SHORT_SAMPLE,
                    f"Formation length {length} does not fit before as_of={as_of_end}.",
                )
            )
            continue
        windows.append(
            TimeWindow(start, as_of_end, label=f"formation_{length}")
        )
    if not windows:
        flags.append(
            fail_flag(
                QualityCode.SHORT_SAMPLE,
                "No formation windows could be constructed from the supplied lengths.",
            )
        )
    elif not has_fail(flags):
        flags.append(ok_flag(f"Constructed {len(windows)} formation windows ending at {as_of_end}."))
    return tuple(windows), tuple(flags)


def walk_forward_splits(
    n_obs: int,
    *,
    train_size: int,
    test_size: int,
    mode: Literal["rolling", "expanding"] = "rolling",
    step: int | None = None,
    embargo: int = 0,
    holdout: HoldoutContract | None = None,
    min_folds: int = 1,
) -> tuple[tuple[WalkForwardSplit, ...], tuple[QualityFlag, ...]]:
    flags: list[QualityFlag] = []
    if mode not in {"rolling", "expanding"}:
        return (), (fail_flag(QualityCode.INVALID_INPUT, f"Unknown walk-forward mode {mode!r}."),)
    if train_size < 2 or test_size < 1 or embargo < 0:
        return (), (
            fail_flag(
                QualityCode.INVALID_INPUT,
                "train_size >= 2, test_size >= 1, and embargo >= 0 are required.",
            ),
        )
    step = test_size if step is None else int(step)
    if step < 1:
        return (), (fail_flag(QualityCode.INVALID_INPUT, "step must be >= 1."),)

    limit, bound_flags = _research_end(n_obs, holdout)
    flags.extend(bound_flags)
    if has_fail(flags):
        return (), tuple(flags)

    splits: list[WalkForwardSplit] = []
    fold_id = 0
    train_end = train_size
    while True:
        embargo_start = train_end
        embargo_end = train_end + embargo
        test_start = embargo_end
        test_end = test_start + test_size
        if test_end > limit:
            break
        if mode == "rolling":
            train_start = train_end - train_size
        else:
            train_start = 0
        if train_start < 0:
            break
        embargo_window = (
            TimeWindow(embargo_start, embargo_end, label=f"embargo_{fold_id}")
            if embargo
            else None
        )
        splits.append(
            WalkForwardSplit(
                fold_id=fold_id,
                train=TimeWindow(train_start, train_end, label=f"train_{fold_id}"),
                test=TimeWindow(test_start, test_end, label=f"test_{fold_id}"),
                embargo=embargo_window,
            )
        )
        fold_id += 1
        train_end += step

    if len(splits) < min_folds:
        flags.append(
            fail_flag(
                QualityCode.SHORT_SAMPLE,
                f"Constructed {len(splits)} walk-forward folds; need at least {min_folds}.",
            )
        )
    elif not has_fail(flags):
        flags.append(ok_flag(f"Constructed {len(splits)} {mode} walk-forward folds."))
    return tuple(splits), tuple(flags)


@dataclass(frozen=True)
class WalkForwardReport:
    splits: tuple[WalkForwardSplit, ...]
    fold_scores: tuple[float, ...]
    mean_oos_score: float
    min_oos_score: float
    positive_fold_fraction: float
    quality_flags: tuple[QualityFlag, ...]
    meta: dict

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "splits": [s.to_dict() for s in self.splits],
            "fold_scores": list(self.fold_scores),
            "mean_oos_score": self.mean_oos_score,
            "min_oos_score": self.min_oos_score,
            "positive_fold_fraction": self.positive_fold_fraction,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def evaluate_walk_forward(
    splits: Sequence[WalkForwardSplit],
    fold_scores: Sequence[float],
    *,
    min_oos_score: float = 0.0,
    min_positive_fraction: float = 0.5,
    split_flags: Sequence[QualityFlag] = (),
) -> WalkForwardReport:
    flags: list[QualityFlag] = list(split_flags)
    if len(splits) != len(fold_scores):
        flags.append(
            fail_flag(
                QualityCode.INVALID_INPUT,
                "fold_scores length must match the number of walk-forward splits.",
            )
        )
        meta = make_meta(
            method="walk_forward_evaluation",
            parameters={"min_oos_score": min_oos_score, "min_positive_fraction": min_positive_fraction},
            assumptions=("Caller supplies OOS scores already computed on each test window.",),
            quality_flags=tuple(flags),
        )
        return WalkForwardReport(tuple(splits), tuple(float(s) for s in fold_scores), float("nan"), float("nan"), float("nan"), tuple(flags), meta.to_dict())

    scores = [float(s) for s in fold_scores]
    if any(s != s or s in (float("inf"), float("-inf")) for s in scores):
        flags.append(fail_flag(QualityCode.NON_FINITE, "Walk-forward fold scores contain NaN/Inf."))
        mean_s = min_s = pos = float("nan")
    elif not scores:
        flags.append(fail_flag(QualityCode.SHORT_SAMPLE, "No walk-forward fold scores."))
        mean_s = min_s = pos = float("nan")
    else:
        mean_s = float(sum(scores) / len(scores))
        min_s = float(min(scores))
        pos = float(sum(1 for s in scores if s > 0.0) / len(scores))
        if min_s < min_oos_score:
            flags.append(
                fail_flag(
                    "walk_forward_min_oos",
                    f"Min OOS score {min_s} < threshold {min_oos_score}.",
                )
            )
        if pos < min_positive_fraction:
            flags.append(
                fail_flag(
                    "walk_forward_consistency",
                    f"Positive-fold fraction {pos} < {min_positive_fraction}.",
                )
            )
        if not has_fail(flags):
            flags.append(ok_flag("Walk-forward OOS scores cleared configured thresholds."))

    meta = make_meta(
        method="walk_forward_evaluation",
        parameters={
            "min_oos_score": min_oos_score,
            "min_positive_fraction": min_positive_fraction,
            "n_folds": len(splits),
        },
        assumptions=(
            "Fold scores are out-of-sample on the corresponding test window.",
            "Train windows never include test, embargo, or sealed holdout bars.",
        ),
        quality_flags=tuple(flags),
    )
    return WalkForwardReport(
        splits=tuple(splits),
        fold_scores=tuple(scores),
        mean_oos_score=mean_s,
        min_oos_score=min_s,
        positive_fold_fraction=pos,
        quality_flags=tuple(flags),
        meta=meta.to_dict(),
    )
