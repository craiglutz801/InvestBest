"""Cost and execution-delay stress scenarios.

Default cost multipliers are baseline (1.0), +50% (1.5), and +100% (2.0).
If a stressed net-return series fails the configured score floor, the
otherwise attractive baseline is vetoed.

Delay stress shifts positions forward by ``delay_bars`` so fills occur later
than the signal. This package does not place orders; it only rewrites
research return streams.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from northstar_promotion.arrays import has_fail, validate_1d
from northstar_promotion.metrics import period_sharpe
from northstar_promotion.quality import QualityCode, QualityFlag, fail_flag, ok_flag, warn_flag
from northstar_promotion.schema import make_meta

DEFAULT_COST_MULTIPLIERS = (1.0, 1.5, 2.0)


@dataclass(frozen=True)
class ScenarioScore:
    name: str
    multiplier: float | None
    delay_bars: int | None
    sharpe: float
    mean_return: float
    passed: bool

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "multiplier": self.multiplier,
            "delay_bars": self.delay_bars,
            "sharpe": self.sharpe,
            "mean_return": self.mean_return,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class StressReport:
    kind: str
    scenarios: tuple[ScenarioScore, ...]
    baseline_sharpe: float
    veto: bool
    quality_flags: tuple[QualityFlag, ...]
    meta: dict

    @property
    def is_usable(self) -> bool:
        return not has_fail(self.quality_flags)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "scenarios": [s.to_dict() for s in self.scenarios],
            "baseline_sharpe": self.baseline_sharpe,
            "veto": self.veto,
            "quality_flags": [f.to_dict() for f in self.quality_flags],
            "is_usable": self.is_usable,
            "meta": self.meta,
        }


def _score_series(net: np.ndarray, min_sharpe: float) -> tuple[float, float, bool, tuple[QualityFlag, ...]]:
    sr, flags = period_sharpe(net)
    mu = float(np.mean(net)) if net.size else float("nan")
    if has_fail(flags) or sr != sr:
        return sr, mu, False, flags
    return sr, mu, bool(sr >= min_sharpe), flags


def cost_stress(
    gross_returns: Sequence[float] | np.ndarray,
    cost_series: Sequence[float] | np.ndarray,
    *,
    multipliers: Sequence[float] = DEFAULT_COST_MULTIPLIERS,
    min_sharpe: float = 0.0,
) -> StressReport:
    flags: list[QualityFlag] = []
    gross, gflags = validate_1d(gross_returns, name="gross_returns")
    costs, cflags = validate_1d(cost_series, name="cost_series")
    flags.extend(gflags)
    flags.extend(cflags)
    if has_fail(flags):
        meta = make_meta(
            method="cost_stress",
            parameters={"multipliers": list(multipliers), "min_sharpe": min_sharpe},
            assumptions=_COST_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return StressReport("cost", (), float("nan"), True, tuple(flags), meta.to_dict())
    if gross.shape != costs.shape:
        flags.append(
            fail_flag(QualityCode.INVALID_INPUT, "gross_returns and cost_series must have the same length.")
        )
    if any(m < 0 or m != m or m in (float("inf"), float("-inf")) for m in multipliers):
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "Cost multipliers must be finite and >= 0."))
    if np.any(costs < 0):
        flags.append(
            warn_flag(
                QualityCode.INVALID_INPUT,
                "cost_series has negative values; costs are expected as non-negative friction.",
            )
        )
    if has_fail(flags):
        meta = make_meta(
            method="cost_stress",
            parameters={"multipliers": list(multipliers), "min_sharpe": min_sharpe},
            assumptions=_COST_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return StressReport("cost", (), float("nan"), True, tuple(flags), meta.to_dict())

    scenarios: list[ScenarioScore] = []
    veto = False
    baseline_sharpe = float("nan")
    for m in multipliers:
        net = gross - float(m) * costs
        sr, mu, passed, sflags = _score_series(net, min_sharpe)
        flags.extend(sflags)
        name = "baseline" if abs(float(m) - 1.0) < 1e-12 else f"cost_x{m}"
        if abs(float(m) - 1.0) < 1e-12:
            baseline_sharpe = sr
        if not passed:
            veto = True
            flags.append(
                fail_flag(
                    "cost_stress_fail",
                    f"Cost multiplier {m}: Sharpe {sr} < min_sharpe {min_sharpe}.",
                )
            )
        scenarios.append(
            ScenarioScore(name=name, multiplier=float(m), delay_bars=None, sharpe=sr, mean_return=mu, passed=passed)
        )
    if not veto:
        flags.append(ok_flag("All cost-stress scenarios cleared the Sharpe floor."))
    meta = make_meta(
        method="cost_stress",
        parameters={"multipliers": list(multipliers), "min_sharpe": min_sharpe},
        assumptions=_COST_ASSUMPTIONS,
        quality_flags=tuple(flags),
    )
    return StressReport("cost", tuple(scenarios), baseline_sharpe, veto, tuple(flags), meta.to_dict())


def execution_delay_stress(
    asset_returns: Sequence[float] | np.ndarray,
    positions: Sequence[float] | np.ndarray,
    *,
    delay_bars: Sequence[int] = (0, 1, 2),
    cost_series: Sequence[float] | np.ndarray | None = None,
    min_sharpe: float = 0.0,
) -> StressReport:
    flags: list[QualityFlag] = []
    rets, rflags = validate_1d(asset_returns, name="asset_returns")
    pos, pflags = validate_1d(positions, name="positions")
    flags.extend(rflags)
    flags.extend(pflags)
    costs = None
    if cost_series is not None:
        costs, cflags = validate_1d(cost_series, name="cost_series")
        flags.extend(cflags)
    if has_fail(flags):
        meta = make_meta(
            method="execution_delay_stress",
            parameters={"delay_bars": list(delay_bars), "min_sharpe": min_sharpe},
            assumptions=_DELAY_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return StressReport("delay", (), float("nan"), True, tuple(flags), meta.to_dict())
    if rets.shape != pos.shape or (costs is not None and costs.shape != rets.shape):
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "asset_returns, positions, and costs must align."))
    if any(int(d) < 0 for d in delay_bars):
        flags.append(fail_flag(QualityCode.INVALID_INPUT, "delay_bars must be >= 0."))
    if has_fail(flags):
        meta = make_meta(
            method="execution_delay_stress",
            parameters={"delay_bars": list(delay_bars), "min_sharpe": min_sharpe},
            assumptions=_DELAY_ASSUMPTIONS,
            quality_flags=tuple(flags),
        )
        return StressReport("delay", (), float("nan"), True, tuple(flags), meta.to_dict())

    scenarios: list[ScenarioScore] = []
    veto = False
    baseline_sharpe = float("nan")
    n = int(rets.size)
    for d in delay_bars:
        d_i = int(d)
        delayed = np.zeros(n, dtype=float)
        if d_i == 0:
            delayed = pos.copy()
        elif d_i < n:
            delayed[d_i:] = pos[: n - d_i]
        net = delayed * rets
        if costs is not None:
            turnover = np.abs(np.diff(delayed, prepend=0.0))
            net = net - turnover * costs
        sr, mu, passed, sflags = _score_series(net, min_sharpe)
        flags.extend(sflags)
        if d_i == 0:
            baseline_sharpe = sr
        if not passed:
            veto = True
            flags.append(
                fail_flag(
                    "delay_stress_fail",
                    f"Delay {d_i} bars: Sharpe {sr} < min_sharpe {min_sharpe}.",
                )
            )
        scenarios.append(
            ScenarioScore(
                name="baseline" if d_i == 0 else f"delay_{d_i}",
                multiplier=None,
                delay_bars=d_i,
                sharpe=sr,
                mean_return=mu,
                passed=passed,
            )
        )
    if not veto:
        flags.append(ok_flag("All execution-delay scenarios cleared the Sharpe floor."))
    meta = make_meta(
        method="execution_delay_stress",
        parameters={"delay_bars": list(delay_bars), "min_sharpe": min_sharpe},
        assumptions=_DELAY_ASSUMPTIONS,
        quality_flags=tuple(flags),
    )
    return StressReport("delay", tuple(scenarios), baseline_sharpe, veto, tuple(flags), meta.to_dict())


_COST_ASSUMPTIONS = (
    "net_returns = gross_returns - multiplier * cost_series.",
    "cost_series is a per-bar friction already expressed in return units.",
    "Default multipliers are 1.0 (baseline), 1.5 (+50%), and 2.0 (+100%).",
    "A single failed scenario vetoes promotion regardless of the baseline Sharpe.",
)

_DELAY_ASSUMPTIONS = (
    "Positions are shifted forward by delay_bars (later fill, no lookahead).",
    "Bars before the delayed position starts contribute zero strategy return.",
    "If cost_series is supplied, friction is applied to absolute position changes after the delay.",
)
