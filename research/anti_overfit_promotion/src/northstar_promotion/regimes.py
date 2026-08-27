"""Regime-slice evaluation contract.

A candidate that only "works" inside one labeled regime, or that cannot be
measured in the regimes where the thesis says it should fail, is not ready.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from northstar_promotion.arrays import has_fail, validate_1d
from northstar_promotion.metrics import period_sharpe
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag, warn_flag
from northstar_promotion.schema import make_meta


@dataclass(frozen=True)
class RegimeSliceScore:
    label: str
    n_obs: int
    sharpe: float
    mean_return: float
    passed: bool | None
    skipped: bool

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "n_obs": self.n_obs,
            "sharpe": self.sharpe,
            "mean_return": self.mean_return,
            "passed": self.passed,
            "skipped": self.skipped,
        }


@dataclass(frozen=True)
class RegimeSliceReport:
    slices: tuple[RegimeSliceScore, ...]
    required_labels: tuple[str, ...]
    quality_flags: tuple[QualityFlag, ...]
    veto: bool
    meta: dict

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "slices": [s.to_dict() for s in self.slices],
            "required_labels": list(self.required_labels),
            "veto": self.veto,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def evaluate_regime_slices(
    returns: Sequence[float] | np.ndarray,
    labels: Sequence[str],
    *,
    min_obs: int = 20,
    min_sharpe: float = 0.0,
    required_labels: Sequence[str] | None = None,
    expected_fail_labels: Sequence[str] | Mapping[str, float] | None = None,
) -> RegimeSliceReport:
    flags: list[QualityFlag] = []
    arr, rflags = validate_1d(returns, name="returns")
    flags.extend(rflags)
    label_arr = np.asarray(list(labels), dtype=object)
    if has_fail(flags):
        meta = make_meta(
            method="regime_slice_evaluation",
            parameters={"min_obs": min_obs, "min_sharpe": min_sharpe},
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return RegimeSliceReport((), tuple(required_labels or ()), tuple(flags), True, meta.to_dict())
    if label_arr.shape[0] != arr.shape[0]:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "returns and labels must have the same length."))
        meta = make_meta(
            method="regime_slice_evaluation",
            parameters={"min_obs": min_obs, "min_sharpe": min_sharpe},
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return RegimeSliceReport((), tuple(required_labels or ()), tuple(flags), True, meta.to_dict())

    uniq = []
    seen = set()
    for lab in label_arr.tolist():
        key = str(lab)
        if key not in seen:
            seen.add(key)
            uniq.append(key)

    required = tuple(str(x) for x in (required_labels or uniq))
    expected_fail: dict[str, float] = {}
    if expected_fail_labels is not None:
        if isinstance(expected_fail_labels, Mapping):
            expected_fail = {str(k): float(v) for k, v in expected_fail_labels.items()}
        else:
            expected_fail = {str(k): min_sharpe for k in expected_fail_labels}

    slices: list[RegimeSliceScore] = []
    veto = False
    for lab in uniq:
        mask = np.array([str(x) == lab for x in label_arr.tolist()], dtype=bool)
        n = int(mask.sum())
        if n < min_obs:
            flags.append(
                warn_flag(QualityCode.SHORT_SAMPLE, f"Regime {lab!r} has {n} obs < min_obs {min_obs}; skipped.")
            )
            slices.append(
                RegimeSliceScore(lab, n, float("nan"), float("nan"), None, True)
            )
            if lab in required:
                flags.append(
                    fail_flag(
                        QualityCode.SHORT_SAMPLE,
                        f"Required regime {lab!r} has insufficient observations.",
                    )
                )
                veto = True
            continue
        sr, sflags = period_sharpe(arr[mask])
        mu = float(np.mean(arr[mask]))
        if has_fail(sflags):
            flags.extend(sflags)
            slices.append(RegimeSliceScore(lab, n, sr, mu, False, False))
            if lab in required:
                veto = True
            continue
        if lab in expected_fail:
            # Thesis says this regime should *not* look attractive.
            cap = expected_fail[lab]
            looks_too_good = bool(sr >= cap)
            if looks_too_good:
                flags.append(
                    fail_flag(
                        "regime_slice_unexpected_pass",
                        f"Regime {lab!r} was expected to fail (Sharpe < {cap}) but Sharpe={sr}.",
                    )
                )
                veto = True
            slices.append(RegimeSliceScore(lab, n, sr, mu, passed=not looks_too_good, skipped=False))
            continue
        passed = bool(sr >= min_sharpe)
        if lab in required and not passed:
            flags.append(
                fail_flag(
                    "regime_slice_fail",
                    f"Required regime {lab!r} Sharpe {sr} < {min_sharpe}.",
                )
            )
            veto = True
        slices.append(RegimeSliceScore(lab, n, sr, mu, passed, False))

    for lab in required:
        if lab not in seen:
            flags.append(fail_flag(QualityCode.MISSING_DATA, f"Required regime {lab!r} is absent from labels."))
            veto = True

    if not veto:
        flags.append(ok_flag("Regime slices cleared the configured contract."))
    meta = make_meta(
        method="regime_slice_evaluation",
        parameters={
            "min_obs": min_obs,
            "min_sharpe": min_sharpe,
            "required_labels": list(required),
            "expected_fail_labels": expected_fail,
        },
        assumptions=_ASSUMPTIONS,
        quality_flags=tuple(flags),
    )
    return RegimeSliceReport(tuple(slices), required, tuple(flags), veto, meta.to_dict())


_ASSUMPTIONS = (
    "Labels are caller-supplied regime tags aligned with the return series.",
    "This module does not infer regimes; it only evaluates a pre-labeled contract.",
    "required_labels must clear min_sharpe; expected_fail_labels must remain below their cap.",
)
