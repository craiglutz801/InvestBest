"""Parameter-neighborhood / plateau evaluation.

An isolated sharp optimum (one grid point much better than its neighbors) is
treated as a falsification signal. A stable plateau — a sufficient fraction of
neighbors within a score tolerance of the selected point — can pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from northstar_promotion.arrays import has_fail
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag
from northstar_promotion.schema import make_meta


@dataclass(frozen=True)
class ParameterPoint:
    trial_id: str
    parameters: Mapping[str, float]
    score: float

    def to_dict(self) -> dict:
        return {
            "trial_id": self.trial_id,
            "parameters": dict(self.parameters),
            "score": self.score,
        }


@dataclass(frozen=True)
class PlateauReport:
    selected_trial_id: str
    selected_score: float
    neighbor_trial_ids: tuple[str, ...]
    neighbor_scores: tuple[float, ...]
    n_neighbors: int
    n_within_tolerance: int
    neighbor_fraction_within_tolerance: float
    isolated_optimum: bool
    plateau_pass: bool
    quality_flags: tuple[QualityFlag, ...]
    meta: dict

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "selected_trial_id": self.selected_trial_id,
            "selected_score": self.selected_score,
            "neighbor_trial_ids": list(self.neighbor_trial_ids),
            "neighbor_scores": list(self.neighbor_scores),
            "n_neighbors": self.n_neighbors,
            "n_within_tolerance": self.n_within_tolerance,
            "neighbor_fraction_within_tolerance": self.neighbor_fraction_within_tolerance,
            "isolated_optimum": self.isolated_optimum,
            "plateau_pass": self.plateau_pass,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def _normalized_vector(
    params: Mapping[str, float],
    keys: Sequence[str],
    mins: Mapping[str, float],
    spans: Mapping[str, float],
) -> np.ndarray:
    vec = []
    for k in keys:
        span = spans[k]
        if span <= 0:
            vec.append(0.0)
        else:
            vec.append((float(params[k]) - mins[k]) / span)
    return np.asarray(vec, dtype=float)


def evaluate_plateau(
    points: Sequence[ParameterPoint],
    *,
    selected_trial_id: str,
    radius: float = 0.15,
    score_tolerance: float = 0.25,
    min_neighbor_fraction: float = 0.5,
    min_neighbors: int = 2,
    relative_tolerance: bool = True,
) -> PlateauReport:
    """Chebyshev neighborhood in min-max normalized parameter space.

    ``radius`` is in normalized units (0–1 across the observed range of each
    parameter). A neighbor is "on-plateau" if
    ``|score - selected| <= score_tolerance`` (absolute) or
    ``|score - selected| <= score_tolerance * |selected|`` when
    ``relative_tolerance`` is true.
    """
    flags: list[QualityFlag] = []
    empty_meta_params = {
        "radius": radius,
        "score_tolerance": score_tolerance,
        "min_neighbor_fraction": min_neighbor_fraction,
        "min_neighbors": min_neighbors,
        "relative_tolerance": relative_tolerance,
    }

    def _failed(msg_flags: list[QualityFlag]) -> PlateauReport:
        meta = make_meta(
            method="parameter_neighborhood_plateau",
            parameters=empty_meta_params,
            assumptions=_ASSUMPTIONS,
            quality_flags=tuple(msg_flags),
        )
        return PlateauReport(
            selected_trial_id=selected_trial_id,
            selected_score=float("nan"),
            neighbor_trial_ids=(),
            neighbor_scores=(),
            n_neighbors=0,
            n_within_tolerance=0,
            neighbor_fraction_within_tolerance=float("nan"),
            isolated_optimum=True,
            plateau_pass=False,
            quality_flags=tuple(msg_flags),
            meta=meta.to_dict(),
        )

    if radius <= 0 or score_tolerance < 0 or min_neighbor_fraction < 0 or min_neighbors < 1:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "Plateau thresholds are invalid."))
        return _failed(flags)
    if not points:
        flags.append(fail_flag(QualityCode.MISSING_DATA, "No parameter points supplied."))
        return _failed(flags)

    by_id = {p.trial_id: p for p in points}
    if selected_trial_id not in by_id:
        flags.append(
            fail_flag(QualityCode.INVALID_INPUT, f"selected_trial_id {selected_trial_id!r} is not in the grid.")
        )
        return _failed(flags)
    selected = by_id[selected_trial_id]
    if selected.score != selected.score or selected.score in (float("inf"), float("-inf")):
        flags.append(fail_flag(QualityCode.NON_FINITE, "Selected score is non-finite."))
        return _failed(flags)

    keys = tuple(selected.parameters.keys())
    if not keys:
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "Selected point has no numeric parameters."))
        return _failed(flags)
    for p in points:
        if tuple(p.parameters.keys()) != keys:
            flags.append(
                fail_flag(
                    QualityCode.INVALID_INPUT,
                    f"Point {p.trial_id!r} parameter keys do not match the selected point.",
                )
            )
            return _failed(flags)
        for k, v in p.parameters.items():
            if v != v or v in (float("inf"), float("-inf")):
                flags.append(
                    fail_flag(QualityCode.NON_FINITE, f"Point {p.trial_id!r} parameter {k!r} is non-finite.")
                )
                return _failed(flags)
        if p.score != p.score or p.score in (float("inf"), float("-inf")):
            flags.append(fail_flag(QualityCode.NON_FINITE, f"Point {p.trial_id!r} score is non-finite."))
            return _failed(flags)

    mins = {k: min(float(p.parameters[k]) for p in points) for k in keys}
    maxs = {k: max(float(p.parameters[k]) for p in points) for k in keys}
    spans = {k: maxs[k] - mins[k] for k in keys}
    selected_vec = _normalized_vector(selected.parameters, keys, mins, spans)

    neighbors: list[ParameterPoint] = []
    for p in points:
        if p.trial_id == selected.trial_id:
            continue
        vec = _normalized_vector(p.parameters, keys, mins, spans)
        dist = float(np.max(np.abs(vec - selected_vec)))
        if dist <= radius + 1e-12:
            neighbors.append(p)

    n_neighbors = len(neighbors)
    if n_neighbors < min_neighbors:
        flags.append(
            fail_flag(
                QualityCode.INSUFFICIENT_NEIGHBORS,
                f"Found {n_neighbors} neighbors within radius {radius}; need at least {min_neighbors}.",
            )
        )

    if relative_tolerance:
        tol = score_tolerance * max(abs(selected.score), 1e-12)
    else:
        tol = score_tolerance
    within = [p for p in neighbors if abs(p.score - selected.score) <= tol]
    n_within = len(within)
    frac = float(n_within / n_neighbors) if n_neighbors else float("nan")

    isolated = n_neighbors == 0 or (np.isfinite(frac) and frac < min_neighbor_fraction)
    plateau_pass = (not isolated) and n_neighbors >= min_neighbors and not has_fail(flags)

    if isolated and not has_fail(flags):
        flags.append(
            fail_flag(
                "isolated_optimum",
                f"Selected point is an isolated optimum: neighbor fraction within tolerance "
                f"is {frac} < {min_neighbor_fraction}.",
            )
        )
        plateau_pass = False
    elif plateau_pass:
        flags.append(
            ok_flag(
                f"Plateau: {n_within}/{n_neighbors} neighbors within tolerance {tol} of score {selected.score}."
            )
        )

    meta = make_meta(
        method="parameter_neighborhood_plateau",
        parameters={**empty_meta_params, "param_keys": list(keys), "tolerance_used": tol},
        assumptions=_ASSUMPTIONS,
        quality_flags=tuple(flags),
    )
    return PlateauReport(
        selected_trial_id=selected.trial_id,
        selected_score=float(selected.score),
        neighbor_trial_ids=tuple(p.trial_id for p in neighbors),
        neighbor_scores=tuple(float(p.score) for p in neighbors),
        n_neighbors=n_neighbors,
        n_within_tolerance=n_within,
        neighbor_fraction_within_tolerance=frac,
        isolated_optimum=isolated,
        plateau_pass=plateau_pass,
        quality_flags=tuple(flags),
        meta=meta.to_dict(),
    )


_ASSUMPTIONS = (
    "Neighborhood is Chebyshev distance in min-max normalized parameter space.",
    "A plateau requires a minimum neighbor count and a minimum fraction within score tolerance.",
    "An isolated sharp optimum fails; this is a robustness check, not proof of a true edge.",
    "Only numeric parameters supplied on the selected point are used.",
)
