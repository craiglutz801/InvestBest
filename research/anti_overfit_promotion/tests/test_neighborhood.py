from __future__ import annotations

from northstar_promotion.neighborhood import ParameterPoint, evaluate_plateau
from northstar_promotion.quality import QualityLevel


def _grid(scores: dict[int, float]) -> list[ParameterPoint]:
    return [
        ParameterPoint(trial_id=f"p{k}", parameters={"lookback": float(k)}, score=v)
        for k, v in scores.items()
    ]


def test_isolated_sharp_optimum_fails():
    # Spike at lookback=5; neighbors 4 and 6 are far worse.
    points = _grid({k: 0.10 for k in range(1, 10)})
    points = [p if p.trial_id != "p5" else ParameterPoint("p5", {"lookback": 5.0}, 2.0) for p in points]
    report = evaluate_plateau(
        points,
        selected_trial_id="p5",
        radius=0.15,
        score_tolerance=0.25,
        min_neighbor_fraction=0.5,
        min_neighbors=2,
        relative_tolerance=True,
    )
    assert report.isolated_optimum is True
    assert report.plateau_pass is False
    assert any(f.level is QualityLevel.FAIL for f in report.quality_flags)


def test_stable_plateau_passes():
    scores = {k: 0.10 for k in range(1, 10)}
    scores[4] = 0.95
    scores[5] = 1.00
    scores[6] = 0.96
    points = _grid(scores)
    report = evaluate_plateau(
        points,
        selected_trial_id="p5",
        radius=0.15,
        score_tolerance=0.25,
        min_neighbor_fraction=0.5,
        min_neighbors=2,
        relative_tolerance=True,
    )
    assert report.n_neighbors >= 2
    assert report.isolated_optimum is False
    assert report.plateau_pass is True
    assert not any(f.level is QualityLevel.FAIL for f in report.quality_flags)


def test_insufficient_neighbors_fail_closed():
    points = [
        ParameterPoint("a", {"x": 0.0}, 1.0),
        ParameterPoint("b", {"x": 1.0}, 0.9),
    ]
    report = evaluate_plateau(
        points,
        selected_trial_id="a",
        radius=0.05,
        min_neighbors=2,
    )
    assert report.plateau_pass is False
    assert any(f.level is QualityLevel.FAIL for f in report.quality_flags)
